from __future__ import annotations

import json
from typing import Any

import requests

from .config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
from .prompt import SYSTEM_PROMPT, build_user_prompt


class QwenClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None) -> None:
        self.api_key = (api_key or QWEN_API_KEY).strip()
        self.base_url = (base_url or QWEN_BASE_URL).rstrip("/")
        self.model = model or QWEN_MODEL

    def generate(self, context: dict) -> str:
        if not self.api_key:
            return build_local_report(context, reason="qwen_api_key_missing")
        try:
            return self._generate_remote(context)
        except Exception:
            return build_local_report(context, reason="qwen_request_failed")

    def _generate_remote(self, context: dict) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(context)},
            ],
            "temperature": 0.2,
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def build_local_report(context: dict, reason: str) -> str:
    plan = context.get("physician_plan", {})
    evidence = context.get("rag_evidence", {})
    support = context.get("support_assessment", {})
    primary = plan.get("primary_syndrome", {})
    formula = plan.get("formula", {})
    syndrome_evidence = evidence.get("syndrome_evidence", [])
    formula_evidence = evidence.get("formula_evidence", [])
    herb_evidence = evidence.get("herb_mechanism_evidence", [])

    return "\n".join([
        "一、患者与医生方案摘要",
        f"患者信息：{context.get('patient', {}).get('text', '')}",
        f"医生主证：{primary.get('std_name') or primary.get('raw_name') or '未提供'}",
        f"医生方剂：{formula.get('std_name') or formula.get('raw_name') or '未提供'}",
        "二、证型评判",
        str(syndrome_evidence) if syndrome_evidence else "本消融层未启用该类 RAG 证据。",
        "三、方剂评判",
        str(formula_evidence) if formula_evidence else "本消融层未启用该类 RAG 证据。",
        "四、药味配伍评判",
        str(plan.get("herbs", [])) if plan.get("herbs") else "本消融层未启用该类 RAG 证据。",
        "五、靶点与通路机制解释",
        str(herb_evidence) if herb_evidence else "本消融层未启用该类 RAG 证据。",
        "六、方证一致性与证据链闭合",
        str(evidence.get("reflection")) + " / " + str(evidence.get("chain_assessment")),
        "七、医生方案总体评价",
        f"说明：{reason}",
        "八、本层证据来源说明",
        str(support),
        "本输出仅用于科研原型验证，不能替代医生诊疗；不得自行推荐新证型、新方剂、新药味。",
    ])
