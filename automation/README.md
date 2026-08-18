# Task 2: No-Code Automation with n8n

This directory contains the production-ready **n8n Workflow** for ConsultBae's candidate ingestion, deduplication alerting, and AI/LLM skill auto-categorization.

## Workflow Overview

```
 [Webhook Trigger]
         │
         ▼
 [Data Cleaner & Normalizer] (JS Code Node)
         │
         ▼
 [Query Database for Duplicate] (HTTP Request to /api/candidates/check-duplicate)
         │
         ▼
    [Is Duplicate?] (IF Node)
      ├─── True  ──► [Send Duplicate Alert (Slack/Webhook)]
      └─── False ──► [LLM / AI Skill Classifier]
                           │
                           ▼
                     [Write Enriched Candidate to DB]
                           │
                           ▼
                     [Format Final Response]
```

## Included Deliverables

1. **`n8n_candidate_enrichment_pipeline.json`**: Full export of the n8n workflow. Ready to copy-paste or import into any n8n instance (Self-Hosted Docker, Desktop app, or n8n Cloud).
2. **`simulate_n8n_flow.py`**: Local CLI test runner that simulates the exact execution graph of all n8n nodes against our SQLite database.

## How to Import into n8n

1. Open your n8n dashboard (e.g. `http://localhost:5678` or your n8n cloud instance).
2. In the top-right corner, click **... (Workflow menu)** $\rightarrow$ **Import from File...** or simply copy the entire content of [`n8n_candidate_enrichment_pipeline.json`](./n8n_candidate_enrichment_pipeline.json) and press `Ctrl+V` on the n8n canvas.
3. The complete 7-node visual pipeline will immediately appear on the canvas.
4. Click **Execute Workflow** or activate the webhook trigger.

## Test Payload for Webhook

Send a POST request to your n8n Webhook URL:
```json
{
  "full_name": "Karan Bhatia",
  "email": "karan.bhatia32@mailtest.example.org",
  "phone": "+919000000211",
  "city": "Noida",
  "skills": ["SQL", "MongoDB", "Selenium", "Zapier", "Web Scraping", "JavaScript"],
  "experience_years": 4.7,
  "current_ctc_lpa": 8.27
}
```

## Running the Simulation Locally

You can verify the entire workflow execution in your terminal:
```bash
python automation/simulate_n8n_flow.py
```
