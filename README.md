<img
  align="right"
  src="assets/13428411883569884.png"
  alt="Osteoporosis TCM Evaluation logo"
  width="250"
/>

<p align="left">
  <img src="https://img.shields.io/github/license/aaah-min/OP-RAG-open?style=flat-square&color=2F7D78&label=License" alt="MIT License">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11">
  <img src="https://img.shields.io/badge/scikit--learn-1.5.2-F7931E?style=flat-square&logo=scikitlearn&logoColor=white" alt="scikit-learn 1.5.2">
  <img src="https://img.shields.io/github/stars/aaah-min/OP-RAG-open?style=flat-square&color=E3B341" alt="GitHub Stars">
  <br>
  <img src="https://img.shields.io/badge/Model-Qwen--Plus-CF3A5B?style=flat-square" alt="Qwen-Plus">
  <img src="https://img.shields.io/badge/Field-TCM%20AI-9B59B6?style=flat-square" alt="TCM AI">
  <img src="https://img.shields.io/badge/Ablation-G0--G4-168AAD?style=flat-square" alt="G0-G4 Ablation Workflow">
  <img src="https://img.shields.io/badge/Data-Synthetic%20Demo-607D8B?style=flat-square" alt="Synthetic Demonstration Data">
</p>

# OP-RAG Reproducibility Package

**A three-layer RAG workflow for evidence-aware evaluation of traditional Chinese medicine prescriptions in primary osteoporosis.**

OP-RAG connects three structured knowledge layers to assess a clinician-provided TCM regimen:

🩺 **Syndrome layer** · standardized syndrome evidence  
🌿 **Formula layer** · syndrome-formula mappings and composition  
🧬 **Mechanism layer** · herb-target-pathway annotations

The system reports formula-syndrome consistency, mechanism coverage, and evidence-chain closure. This repository releases the cleaned source code, synthetic examples, and the complete `G0-G4` ablation workflow for transparent reproduction and reuse.

> [!IMPORTANT]
> OP-RAG is a research workflow, not a diagnosis, prescription, or clinical decision system.

<br clear="right">

## 🔎 Scope and reproducibility

This repository reproduces the public **method workflow**: three-layer knowledge-base loading, `G0-G4` ablation logic, metric calculation, optional Qwen-Plus report generation, and paper-result aggregation.

The original 50-case clinical evaluation set is restricted and is not distributed. Its published results are included only as aggregate records in [`data/paper_results/`](data/paper_results/). The synthetic demonstration set contains no patient data and reproduces the complete software workflow, but it cannot independently reconstruct the manuscript's patient-level results.

| Resource | Availability | Purpose |
| :--- | :---: | :--- |
| 🧠 Three-layer knowledge base | ✅ Included | Syndrome, formula, and mechanism retrieval |
| 🧪 Synthetic demonstration cases | ✅ Included | Safe end-to-end workflow testing |
| 📊 Deterministic `G0-G4` evaluation | ✅ Included | Ablation and metric reproduction |
| 🤖 Qwen-Plus report generation | ⚙️ Optional | Structured natural-language explanation |
| 📄 Aggregated manuscript results | ✅ Included | Transparent comparison with reported results |
| 🔒 Patient-level inputs and reports | ❌ Restricted | Excluded for privacy and data governance |

## 🚀 Quick start

### 1. Create the environment

```bash
conda env create -f environment.yml
conda activate op-rag-open
```

### 2. Run the complete public workflow

```bash
python scripts/run_ablation.py
```

Results are written to:

```text
outputs/demo_ablation/
├── g0/
├── g1/
├── g2/
├── g3/
├── g4/
└── all_modes_summary.json
```

The default command uses local deterministic reports and makes no API request.

## 🤖 Optional Qwen-Plus reports

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

Add your own DashScope API key:

```dotenv
QWEN_API_KEY=your_dashscope_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

Run with remote report generation enabled:

```bash
python scripts/run_ablation.py --use-qwen
```

> [!NOTE]
> The client uses `qwen-plus` with `temperature=0.2`. Provider-side revisions may change generated wording. Quantitative metrics are calculated locally and never inferred from LLM text.

## 🧩 Ablation design

| Setting | Knowledge configuration | Evaluation focus |
| :---: | :--- | :--- |
| **G0** | ⬜ No retrieval evidence | Unaugmented baseline |
| **G1** | 🟦 Syndrome | Syndrome evidence support |
| **G2** | 🟦 Syndrome + 🟩 Formula | Formula knowledge support |
| **G3** | 🟦 Syndrome + 🟩 Formula + 🟪 Mechanism | Herb-target-pathway coverage |
| **G4** | 🟦 Syndrome + 🟩 Formula + 🟪 Mechanism + 🟧 Reflection | Consistency and evidence-chain closure |

```mermaid
flowchart LR
    A[Clinical regimen] --> B[🩺 Syndrome layer]
    B --> C[🌿 Formula layer]
    C --> D[🧬 Herb-target-pathway layer]
    D --> E[🔍 Consistency reflection]
    E --> F[📊 Evidence-aware report]

    style A fill:#EAF4F4,stroke:#2F7D78,color:#173F3C
    style B fill:#DCEEFF,stroke:#3776AB,color:#173F3C
    style C fill:#E6F4EA,stroke:#3C8C5A,color:#173F3C
    style D fill:#F1E6F7,stroke:#9B59B6,color:#173F3C
    style E fill:#FFF0DC,stroke:#F7931E,color:#173F3C
    style F fill:#E2F3F5,stroke:#168AAD,color:#173F3C
```

### 📐 Evaluation metrics

| Metric | Definition |
| :--- | :--- |
| **Formula KB support** | Whether the reference formula maps to the formula layer |
| **Herb-set Jaccard** | Overlap between reference herbs and herbs with mechanism annotations |
| **Core-herb coverage** | Fraction of designated core herbs with mechanism evidence |
| **Any-level closure** | Syndrome evidence, mapped formula, compatible pairing, and mechanism evidence are present |
| **Core60 closure** | Any-level closure with core-herb coverage ≥ 0.60 |
| **Strict closure** | Primary consistency and both required mechanism-coverage thresholds are satisfied |

## 🗂️ Repository layout

```text
OP-RAG-open/
├── assets/                 # Project logo and visual assets
├── data/
│   ├── kb/                 # Curated knowledge layers and provenance
│   ├── demo/               # Synthetic educational cases only
│   └── paper_results/      # Aggregate manuscript outputs
├── scripts/
│   └── run_ablation.py     # End-to-end G0-G4 workflow
├── src/op_rag/             # Retrieval, evaluation, prompting, and LLM client
├── tests/                  # Schema and workflow checks
└── outputs/                # Generated outputs, ignored by Git
```

## 📚 Knowledge provenance and limitations

Source records are documented in [`data/kb/references.json`](data/kb/references.json). The knowledge base supports reproducible computational evaluation and is not an exhaustive clinical resource. Mechanistic annotations summarize curated network-pharmacology evidence; they do not establish clinical efficacy or causality.

## 📝 Citation

If you use this implementation, cite the associated OP-RAG manuscript. Replace the record below with the final citation or repository DOI after publication:

```bibtex
@article{oprag,
  title   = {OP-RAG: A Three-Layer Traditional Chinese Medicine Knowledge-Enhanced Evaluation and Explanation System for Primary Osteoporosis},
  author  = {Authors},
  journal = {Journal},
  year    = {Year}
}
```

## 🔐 Ethics and data governance

This package contains no patient-level data, clinical narratives, individual reports, or potentially identifying records. The source clinical dataset remains restricted and is not distributed through this repository.

## 📄 License

Code and project-owned documentation are released under the [MIT License](LICENSE). The project logo is distributed under the same license. Third-party knowledge sources remain subject to their own terms and citation requirements.

## ⚕️ Disclaimer

> [!WARNING]
> This software is for research and educational use only. It must not replace professional medical judgment, diagnosis, treatment planning, or prescription decisions.
