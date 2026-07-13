from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .config import DEFAULT_TOP_K_FORMULAS, DEFAULT_TOP_K_SYNDROMES, FORMULA_ALIAS_MAP, HERB_ALIAS_MAP
from .llm_client import QwenClient, build_local_report
from .rag_pipeline import OPRagPipeline
from .reflection import check_formula_consistency


@dataclass
class AblationCaseInput:
    case_id: str
    patient_text: str
    primary_syndrome_id: str | None = None
    primary_syndrome_name_raw: str | None = None
    secondary_syndrome_ids: list[str] | None = None
    secondary_syndrome_names_raw: list[str] | None = None
    accepted_syndrome_ids: list[str] | None = None
    reference_main_formula_name: str | None = None
    reference_formula_name_raw: str | None = None
    reference_formula_id: str | None = None
    accepted_formula_ids: list[str] | None = None
    reference_herb_set: list[str] | None = None
    reference_herb_names_raw: list[str] | None = None
    core_herbs: list[str] | None = None
    core_herbs_raw: list[str] | None = None
    reference_syndrome_id: str | None = None
    use_llm: bool = True
    top_k_syndromes: int = DEFAULT_TOP_K_SYNDROMES
    top_k_formulas: int = DEFAULT_TOP_K_FORMULAS


@dataclass
class AblationCaseOutput:
    case_id: str
    mode: str
    context: dict[str, Any]
    report: str
    metrics: dict[str, Any] = field(default_factory=dict)
    support_assessment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(self.context.get("case_results", {}))
        return data


class AblationRunner:
    MODES = ("g0", "g1", "g2", "g3", "g4")

    def __init__(self, kb: dict[str, Any], pipeline: OPRagPipeline | None = None) -> None:
        self.kb = kb
        self.pipeline = pipeline or OPRagPipeline(kb)
        self.syndrome_by_id = {item.get("syndrome_id"): item for item in kb.get("syndromes", [])}
        self.formula_by_id = {item.get("formula_id"): item for item in kb.get("formulas", [])}
        self.herb_by_name = {item.get("herb_name"): item for item in kb.get("herbs", [])}

    def run_all(self, case: AblationCaseInput) -> dict[str, dict[str, Any]]:
        return {mode: self.run_case(case, mode).to_dict() for mode in self.MODES}

    def run_case(self, case: AblationCaseInput, mode: str) -> AblationCaseOutput:
        mode = (mode or "g4").strip().lower()
        if mode not in self.MODES:
            raise ValueError(f"不支持的消融模式：{mode}")
        if not case.patient_text.strip():
            raise ValueError("患者症状输入为空，无法评估。")

        physician_plan = self._build_physician_plan(case)
        rag_evidence = self._build_rag_evidence(case, mode, physician_plan)
        support_assessment = self._build_support_assessment(case, mode, physician_plan, rag_evidence)
        context = self._build_context(case, mode, physician_plan, rag_evidence, support_assessment)
        report = self._generate_report(context, case.use_llm, f"{mode.upper()} physician-plan support evaluation")
        metrics = self._compute_metrics(case, physician_plan, rag_evidence, support_assessment)
        context["case_results"] = self._build_case_results(case, mode, physician_plan, rag_evidence, metrics)
        return AblationCaseOutput(case.case_id, mode, context, report, metrics, support_assessment)

    def _build_physician_plan(self, case: AblationCaseInput) -> dict[str, Any]:
        primary = self._resolve_primary_syndrome(case)
        secondary = self._resolve_secondary_syndromes(case)
        formula = self._resolve_doctor_formula(case)
        return {
            "tcm_diagnosis_raw": case.primary_syndrome_name_raw,
            "western_diagnosis_raw": None,
            "treatment_principle_raw": None,
            "primary_syndrome": primary,
            "secondary_syndromes": secondary,
            "all_syndrome_ids": [sid for sid in [primary.get("id"), *[s.get("id") for s in secondary]] if sid],
            "formula": formula,
            "herbs": list(case.reference_herb_set or []),
            "core_herbs": list(case.core_herbs or []),
        }

    def _resolve_primary_syndrome(self, case: AblationCaseInput) -> dict[str, Any]:
        sid = case.primary_syndrome_id or case.reference_syndrome_id
        item = self.syndrome_by_id.get(sid, {}) if sid else {}
        return {"id": sid, "raw_name": case.primary_syndrome_name_raw or item.get("name"), "std_name": item.get("name") or case.primary_syndrome_name_raw}

    def _resolve_secondary_syndromes(self, case: AblationCaseInput) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        ids = case.secondary_syndrome_ids or []
        raws = case.secondary_syndrome_names_raw or []
        for i, sid in enumerate(ids):
            item = self.syndrome_by_id.get(sid, {})
            out.append({"id": sid, "raw_name": raws[i] if i < len(raws) else item.get("name"), "std_name": item.get("name") or (raws[i] if i < len(raws) else None)})
        return out

    def _resolve_doctor_formula(self, case: AblationCaseInput) -> dict[str, Any]:
        raw = case.reference_main_formula_name or case.reference_formula_name_raw
        if case.reference_formula_id and case.reference_formula_id in self.formula_by_id:
            item = self.formula_by_id[case.reference_formula_id]
            return {"id": case.reference_formula_id, "raw_name": raw or item.get("name"), "std_name": item.get("name"), "kb_status": "mapped"}
        if raw:
            target = raw.strip()
            normalized_target = self._normalize_formula_name(target)
            for item in self.kb.get("formulas", []):
                name = str(item.get("name") or "")
                if normalized_target == name or normalized_target in name or name in normalized_target:
                    return {"id": item.get("formula_id"), "raw_name": raw, "std_name": name, "kb_status": "mapped"}
                if target == name or target in name or name in target:
                    return {"id": item.get("formula_id"), "raw_name": raw, "std_name": name, "kb_status": "mapped"}
        return {"id": None, "raw_name": raw, "std_name": raw, "kb_status": "unmapped"}

    def _build_rag_evidence(self, case: AblationCaseInput, mode: str, physician_plan: dict[str, Any]) -> dict[str, Any]:
        if mode == "g0":
            return {"syndrome_evidence": [], "formula_evidence": [], "herb_mechanism_evidence": [], "reflection": None, "chain_assessment": None}
        syndrome_evidence = [self._syndrome_evidence(physician_plan["primary_syndrome"], "primary")]
        syndrome_evidence.extend(self._syndrome_evidence(s, "secondary") for s in physician_plan["secondary_syndromes"])
        evidence = {"syndrome_evidence": syndrome_evidence, "formula_evidence": [], "herb_mechanism_evidence": [], "reflection": None, "chain_assessment": None}
        if mode in {"g2", "g3", "g4"}:
            evidence["formula_evidence"] = [self._formula_evidence(case)]
        if mode in {"g3", "g4"}:
            evidence["herb_mechanism_evidence"] = self._herb_mechanism_evidence(case)
        if mode == "g4":
            evidence["reflection"] = self._reflection_result(case, physician_plan, evidence)
            evidence["chain_assessment"] = self._chain_assessment(case, physician_plan, evidence)
        if mode == "g1":
            evidence["formula_evidence"] = []
            evidence["herb_mechanism_evidence"] = []
        return evidence

    def _syndrome_evidence(self, syndrome: dict[str, Any], role: str) -> dict[str, Any]:
        item = self.syndrome_by_id.get(syndrome.get("id"), {}) if syndrome.get("id") else {}
        return {"syndrome_id": syndrome.get("id"), "name": syndrome.get("std_name") or syndrome.get("raw_name") or item.get("name"), "core_symptoms": item.get("core_symptoms", []), "secondary_symptoms": item.get("secondary_symptoms", []), "tongue": item.get("tongue", ""), "pulse": item.get("pulse", ""), "text_description": item.get("description", ""), "role": role}

    def _formula_evidence(self, case: AblationCaseInput) -> dict[str, Any]:
        formula = self._resolve_doctor_formula(case)
        if formula.get("kb_status") == "unmapped":
            return {"formula_id": None, "name": formula.get("raw_name"), "kb_status": "unmapped", "message": "该方暂未纳入结构化方剂知识库"}
        item = self.formula_by_id.get(formula.get("id"), {})
        return {"formula_id": formula.get("id"), "name": formula.get("std_name"), "composition": item.get("composition", []), "indication_syndrome": item.get("indication_syndrome", []), "classical_source": item.get("classical_source", {}), "modern_evidence": item.get("modern_evidence", []), "notes": item.get("notes", ""), "kb_status": "mapped"}

    def _herb_mechanism_evidence(self, case: AblationCaseInput) -> list[dict[str, Any]]:
        records = []
        for herb in case.reference_herb_set or []:
            item = self.herb_by_name.get(HERB_ALIAS_MAP.get(herb, herb))
            if not item:
                continue
            records.append({"herb_name": herb, "tcm_function": item.get("tcm_function", ""), "targets_op_related": item.get("targets_op_related", []), "pathways": item.get("pathways", []), "evidence_papers": item.get("evidence_papers", []), "text_description": item.get("description", "")})
        return records

    def _reflection_result(self, case: AblationCaseInput, physician_plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        primary = physician_plan.get("primary_syndrome") or {}
        formula = physician_plan.get("formula") or {}
        primary_consistency = self._formula_consistency(primary.get("id"), formula.get("id")) if primary.get("id") and formula.get("id") and primary.get("id") in self.kb.get("syndrome_formula_map", {}) and formula.get("kb_status") == "mapped" else None
        any_consistency = None
        if formula.get("kb_status") == "mapped":
            for syndrome in [primary, *physician_plan.get("secondary_syndromes", [])]:
                result = self._formula_consistency(syndrome.get("id"), formula.get("id")) if syndrome.get("id") else None
                if result is True:
                    any_consistency = True
                    break
                if result is False:
                    any_consistency = False if any_consistency is None else any_consistency
        return {"formula_consistent_with_primary": primary_consistency, "formula_consistent_with_any_syndrome": any_consistency, "message": "医生证型-方剂映射已评估" if formula.get("kb_status") == "mapped" else "医生方剂未映射到知识库，无法评估一致性"}

    def _formula_consistency(self, syndrome_id: str | None, formula_id: str | None) -> bool | None:
        if not syndrome_id or not formula_id:
            return None
        allowed = self.kb.get("syndrome_formula_map", {}).get(syndrome_id)
        if allowed is None:
            return None
        return formula_id in allowed

    def _chain_assessment(self, case: AblationCaseInput, physician_plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        formula = physician_plan.get("formula") or {}
        primary = physician_plan.get("primary_syndrome") or {}
        core = self._normalize_herb_set(set(case.core_herbs or []))
        ref = self._normalize_herb_set(set(case.reference_herb_set or []))
        mech = self._normalize_herb_set({h.get("herb_name") for h in evidence.get("herb_mechanism_evidence", [])})
        core_cov = (len(core & mech) / len(core)) if core else None
        ref_cov = (len(ref & mech) / len(ref)) if ref else None
        any_consistent = evidence.get("reflection", {}).get("formula_consistent_with_any_syndrome") is True
        primary_consistent = evidence.get("reflection", {}).get("formula_consistent_with_primary") is True
        formula_mapped = formula.get("kb_status") == "mapped"
        has_mech = bool(mech)
        chain_any = bool(any(evidence.get("syndrome_evidence", [])) and formula_mapped and any_consistent and has_mech)
        chain_core60 = True if chain_any and core_cov is not None and core_cov >= 0.6 else False if chain_any and core_cov is not None else None
        chain_strict = True if primary.get("id") and formula_mapped and primary_consistent and core_cov is not None and core_cov >= 0.8 and ref_cov is not None and ref_cov >= 0.8 else False if primary.get("id") and formula_mapped else None
        return {"chain_closed_any": chain_any, "chain_closed_core60": chain_core60, "chain_closed_strict": chain_strict}

    def _build_support_assessment(self, case: AblationCaseInput, mode: str, physician_plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        formula = physician_plan.get("formula") or {}
        core = self._normalize_herb_set(set(case.core_herbs or []))
        ref = self._normalize_herb_set(set(case.reference_herb_set or []))
        mech = self._normalize_herb_set({h.get("herb_name") for h in evidence.get("herb_mechanism_evidence", [])})
        return {"mode": mode, "doctor_syndrome_supported": bool(evidence.get("syndrome_evidence")) if mode in {"g1", "g2", "g3", "g4"} else None, "doctor_formula_supported": formula.get("kb_status") == "mapped" if mode in {"g2", "g3", "g4"} else None, "formula_in_accepted_set": None, "formula_consistent_with_syndrome": evidence.get("reflection") if mode == "g4" else None, "core_herbs": sorted(core), "core_herbs_with_mechanism": sorted(core & mech), "reference_herbs_with_mechanism": sorted(ref & mech), "mechanism_target_count": sum(len(h.get("targets_op_related", [])) for h in evidence.get("herb_mechanism_evidence", [])) if mode in {"g3", "g4"} else None, "mechanism_pathway_count": sum(len(h.get("pathways", [])) for h in evidence.get("herb_mechanism_evidence", [])) if mode in {"g3", "g4"} else None, **(evidence.get("chain_assessment") or {})}

    def _build_context(self, case: AblationCaseInput, mode: str, physician_plan: dict[str, Any], evidence: dict[str, Any], support_assessment: dict[str, Any]) -> dict[str, Any]:
        return {"task": "evaluate_physician_plan", "mode": mode, "patient": {"text": case.patient_text}, "physician_plan": physician_plan, "rag_evidence": evidence, "support_assessment": support_assessment, "output_requirements": {"same_structure_across_modes": True, "must_include": ["患者与医生方案摘要", "证型评判", "方剂评判", "药味配伍评判", "靶点与通路机制解释", "方证一致性与证据链闭合", "医生方案总体评价", "本层证据来源说明"]}}

    def _build_case_results(self, case: AblationCaseInput, mode: str, physician_plan: dict[str, Any], evidence: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
        formula = physician_plan.get("formula") or {}
        primary = physician_plan.get("primary_syndrome") or {}
        secondary = physician_plan.get("secondary_syndromes") or []
        matched = {self._normalize_name(h.get("herb_name")) for h in evidence.get("herb_mechanism_evidence", [])}
        herbs = list(case.reference_herb_set or [])
        return {"case_id": case.case_id, "mode": mode, "primary_syndrome_id": primary.get("id"), "primary_syndrome_name": primary.get("std_name"), "secondary_syndrome_ids": [s.get("id") for s in secondary if s.get("id")], "secondary_syndrome_names": [s.get("std_name") for s in secondary if s.get("std_name")], "all_syndrome_ids": physician_plan.get("all_syndrome_ids", []), "reference_formula_id": case.reference_formula_id, "reference_formula_name": formula.get("raw_name"), "formula_kb_status": formula.get("kb_status"), "reference_herb_count": len(herbs), "herbs_with_mechanism_count": len(evidence.get("herb_mechanism_evidence", [])), "herbs_without_mechanism": [h for h in herbs if self._normalize_name(h) not in matched], "formula_consistent_with_primary": evidence.get("reflection", {}).get("formula_consistent_with_primary") if evidence.get("reflection") else None, "formula_consistent_with_any_syndrome": evidence.get("reflection", {}).get("formula_consistent_with_any_syndrome") if evidence.get("reflection") else None, "herb_jaccard": metrics.get("herb_jaccard"), "core_herb_mechanism_coverage": metrics.get("core_herb_mechanism_coverage"), "mechanism_coverage_over_reference_herbs": metrics.get("mechanism_coverage_over_reference_herbs"), "chain_closed_any": metrics.get("chain_closed_any"), "chain_closed_core60": metrics.get("chain_closed_core60"), "chain_closed_strict": metrics.get("chain_closed_strict")}

    def _compute_metrics(self, case: AblationCaseInput, physician_plan: dict[str, Any], evidence: dict[str, Any], support_assessment: dict[str, Any]) -> dict[str, Any]:
        ref = self._normalize_herb_set(set(case.reference_herb_set or []))
        mech = self._normalize_herb_set({h.get("herb_name") for h in evidence.get("herb_mechanism_evidence", [])})
        core = self._normalize_herb_set(set(case.core_herbs or []))
        herb_jaccard = None if not case.reference_herb_set else self._jaccard(mech, ref)
        core_cov = (len(core & mech) / len(core)) if core else None
        ref_cov = (len(ref & mech) / len(ref)) if ref else None
        formula = physician_plan.get("formula") or {}
        primary = physician_plan.get("primary_syndrome") or {}
        return {"primary_syndrome_mapping_rate": 1.0 if primary.get("id") else None, "formula_kb_support_rate": 1.0 if formula.get("kb_status") == "mapped" else 0.0 if formula.get("kb_status") == "unmapped" else None, "formula_syndrome_consistency_rate_primary": evidence.get("reflection", {}).get("formula_consistent_with_primary") if evidence.get("reflection") else None, "formula_syndrome_consistency_rate_any": evidence.get("reflection", {}).get("formula_consistent_with_any_syndrome") if evidence.get("reflection") else None, "mean_herb_jaccard": herb_jaccard, "mean_core_herb_mechanism_coverage": core_cov, "mean_mechanism_coverage_over_reference_herbs": ref_cov, "chain_closed_any_rate": 1.0 if support_assessment.get("chain_closed_any") else 0.0 if support_assessment.get("chain_closed_any") is False else None, "chain_closed_core60_rate": 1.0 if support_assessment.get("chain_closed_core60") else 0.0 if support_assessment.get("chain_closed_core60") is False else None, "chain_closed_strict_rate": 1.0 if support_assessment.get("chain_closed_strict") else 0.0 if support_assessment.get("chain_closed_strict") is False else None, "herb_jaccard": herb_jaccard, "core_herb_mechanism_coverage": core_cov, "mechanism_coverage_over_reference_herbs": ref_cov, "chain_closed_any": support_assessment.get("chain_closed_any"), "chain_closed_core60": support_assessment.get("chain_closed_core60"), "chain_closed_strict": support_assessment.get("chain_closed_strict")}

    @staticmethod
    def _generate_report(context: dict[str, Any], use_llm: bool, reason: str) -> str:
        return QwenClient().generate(context) if use_llm else build_local_report(context, reason=reason)

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    @staticmethod
    def _normalize_herb_set(herbs: set[str]) -> set[str]:
        return {HERB_ALIAS_MAP.get(h, h) for h in herbs if h}

    @staticmethod
    def _normalize_name(name: str | None) -> str | None:
        return HERB_ALIAS_MAP.get(name, name) if name else None

    @staticmethod
    def _normalize_formula_name(name: str | None) -> str | None:
        if not name:
            return None
        target = name.strip()
        if target in FORMULA_ALIAS_MAP:
            return FORMULA_ALIAS_MAP[target]
        for alias, standard in FORMULA_ALIAS_MAP.items():
            if alias in target:
                return standard
        return target
