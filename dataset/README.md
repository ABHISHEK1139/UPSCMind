# Hermes V2 — Training & Knowledge Data
═══════════════════════════════════════════════════════════════
This directory contains all data needed to run Hermes V2.
No additional downloads required — clone and start!

## Directory Structure

```
dataset/
├── README.md                    ← You are here
├── training_data/               ← Generated training data (71 records)
│   ├── trajectories.jsonl       ← Answer generation trajectories
│   ├── chatml_sft.jsonl         ← SFT training data (ChatML format)
│   ├── reward_model.jsonl      ← Reward model training data
│   └── rejected.jsonl           ← Rejected answers for DPO
├── training_data_host/          ← Host-accessible copy
├── training_data_host_backup/   ← Backup copy
├── csat_dataset_all.jsonl        ← CSAT (Prelims) questions dataset
├── mains_gs_all.jsonl           ← Mains GS questions dataset (all subjects)
├── prelims_gs_all.jsonl         ← Prelims GS questions dataset
├── 2011/                        ← Year-wise PYQ data
│   ├── arithmetic.jsonl
│   ├── comprehension.jsonl
│   └── reasoning.jsonl
├── 2012/                        ← Year-wise PYQ data
├── ...
├── 2025/                        ← Year-wise PYQ data
├── metadata/                    ← Dataset metadata
├── human_test_upsc/             ← Human evaluation test results
│   └── results.jsonl            ← 10-question test results
└── results.jsonl                ← Latest test results
```

## Data Files

| File | Size | Description |
|------|------|-------------|
| `training_data/trajectories.jsonl` | 1.3MB | 33 answer generation trajectories |
| `training_data/chatml_sft.jsonl` | 63KB | SFT training data in ChatML format |
| `training_data/reward_model.jsonl` | 49KB | Reward model training data |
| `training_data/rejected.jsonl` | 1.1MB | Rejected answers for DPO training |
| `mains_gs_all.jsonl` | 4.4MB | Mains GS questions (all subjects, 2017-2024) |
| `prelims_gs_all.jsonl` | 1.9MB | Prelims GS questions (2017-2024) |
| `csat_dataset_all.jsonl` | 1.8MB | CSAT dataset (all subjects) |
| `2011-2025/*.jsonl` | ~10MB | Year-wise Previous Year Questions |

## Total Size

- Training data: ~2.5MB
- UPSC question bank: ~8MB
- Year-wise PYQ: ~10MB
- **Total: ~20.5MB**

## How to Use

The system automatically loads data from these files on startup:

1. **Knowledge base ingestion**: `python backend/ingest_knowledge_base.py`
   - Loads `mains_gs_all.jsonl` + `prelims_gs_all.jsonl` into Qdrant
   - Creates 2,370+ knowledge vectors

2. **Training data**: Automatically loaded by the pipeline
   - Trajectories → SFT training
   - Rejected → DPO training
   - Reward → Reward model training

3. **Test data**: `python backend/test_upsc.py`
   - Uses questions from `human_test_upsc/`

## Regenerate Training Data

```bash
# Ingest knowledge base (populates Qdrant)
docker exec hermes_backend python3 /app/ingest_knowledge_base.py

# Run test suite (generates training data)
docker exec hermes_backend python3 /app/test_upsc.py

# View results
cat dataset/human_test_upsc/results.jsonl | python3 -m jsontool
```

## Data Format

### Training Data (JSONL)
```json
{
  "question": "Discuss the salient features of Harappan architecture.",
  "answer": "The Harappan civilization exhibited...",
  "domain": "History",
  "paper": "GS1",
  "year": 2018,
  "type": "factual",
  "score": 0.85,
  "trajectory": [...]
}
```

### Question Bank (JSONL)
```json
{
  "question": "What is fiscal deficit?",
  "domain": "Economy",
  "paper": "GS3",
  "year": 2022,
  "type": "factual",
  "answer": "Fiscal deficit is..."
}
```

## License

Data compiled from UPSC public sources (PYQs, NCERT, government reports).
For educational use only.
