# ConsultBae — AI Automation Engineering Platform

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2F%20Python%203.11-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg?style=flat&logo=sqlite)](https://sqlite.org)
[![n8n](https://img.shields.io/badge/Automation-n8n%20Workflow-EA4B71.svg?style=flat&logo=n8n)](https://n8n.io)
[![Audio](https://img.shields.io/badge/Signal%20Processing-NumPy%20%2F%20SciPy-4B8BBE.svg?style=flat)](https://scipy.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end AI Automation platform engineered for **ConsultBae**. This solution unifies fragmented candidate databases across disparate recruitment channels, automates candidate deduplication and LLM skill categorization using **n8n**, and provides a full-stack **Audio Collection & Signal Processing Web Application** with live in-browser recording and mathematical acoustic feature extraction.

---

## 📑 Table of Contents
1. [System Architecture](#system-architecture)
2. [Quick Start & Setup](#quick-start--setup)
3. [Task 1: Data Merge & SQLite Database](#task-1-data-merge--sqlite-database)
4. [Task 2: n8n Low-Code Automation Workflow](#task-2-n8n-low-code-automation-workflow)
5. [Task 3: Mini Audio Collection App & Signal Analysis](#task-3-mini-audio-collection-app--signal-analysis)
6. [Task 4: Data Issues Report Summary](#task-4-data-issues-report-summary)
7. [Task 5: High-Scale Architecture (5,000 Workers)](#task-5-high-scale-architecture-5000-workers)
8. [Stuck Log (Challenges, AI Prompts & Decisions)](#stuck-log)
9. [Video Walkthrough Guide](#video-walkthrough-guide)

---

## 1. System Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                  CONSULTBAE UNIFIED PLATFORM                                     |
+---------------------------------------------------------------------------------------------------+
                                                  |
           +--------------------------------------+--------------------------------------+
           |                                      |                                      |
           v                                      v                                      v
  [source1_naukri]                      [source2_gig_workers]                  [source3_cbnexus]
  - Full Name, Phone, CTC               - Rates (/hr, k/mo), Status            - Verified, Projects
  - Inconsistent dates/cities           - Swapped columns, empty rows          - Duplicate headers
           |                                      |                                      |
           +--------------------------------------+--------------------------------------+
                                                  |
                                                  v
                                     [DATA INGESTION PIPELINE]
                                     - Deterministic Cascade Entity Match
                                     - Phone/Email/City Normalization
                                     - Skill Deduplication & Tagging
                                                  |
                                                  v
                                      [UNIFIED SQLITE DATABASE]
                                      - unified_candidates (55 Master Profiles)
                                      - source_records (Provenance Audit Trail)
                                      - audio_submissions (Recordings & Signals)
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
           [TASK 2: n8n AUTOMATION]                             [TASK 3: AUDIO WEB APP]
           - Webhook / Ingestion Trigger                        - Modern HTML5/CSS/JS UI
           - Deduplication & Conflict Check                     - In-Browser Audio Recorder
           - LLM Skill Classifier & Auto-tag                    - Audio Signal Extractor:
           - Duplicate Alerts & Writeback                         * Duration, kHz, Bitrate, dBFS
           - Exported n8n Workflow JSON                           * SNR, Noise Floor, Quality
                                                                - Interactive Submissions View
```

---

## 2. Quick Start & Setup

### Prerequisites
- Python 3.10+ (Standard Python or Python embeddable)
- Modern Web Browser (Chrome, Edge, Firefox)

### 1-Click Launch (Windows)
Double-click [`start.bat`](./start.bat) or run in terminal:
```bash
start.bat
```
*This automatically executes the Task 1 merge pipeline into `consultbae.db` and launches the web application at **`http://localhost:8000`**.*

### Manual Terminal Setup
```bash
# 1. Install dependencies
pip install fastapi uvicorn python-multipart numpy scipy mutagen soundfile requests

# 2. Ingest and merge all 3 CSV datasets into SQLite
python -m pipeline.ingest

# 3. Launch FastAPI backend & web interface
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 4. Open http://localhost:8000 in your browser
```

### Running Automated Test Suite
```bash
python -m unittest tests/test_full_suite.py
```
*(Runs 9 unit and integration tests verifying cleaners, entity resolution, signal extraction, and API routes in <1 second).*

---

## 3. Task 1: Data Merge & SQLite Database

### Schema Design
The database (`consultbae.db`) is structured into 3 normalized tables:
- **`unified_candidates`**: Master profile consolidating personal identity, normalized skills, compensation (LPA and gig rates), verification flags, and provenance metadata.
- **`source_records`**: Immutable raw source data linked via foreign key, tracking every row-level modification and anomaly detected for complete auditability.
- **`audio_submissions`**: Stores worker recordings linked to unified candidate records with extracted signal telemetry.

### Deterministic Matching Algorithm
Because no single universal primary key spans all 3 files, our entity resolution engine uses a **priority-ordered cascade**:
1. **Primary Key Match:** Exact normalized `Email` (e.g. bridging `source1` and `source2`).
2. **Secondary Key Match:** Exact 10-digit normalized `Phone` (e.g. bridging `source1` and `source3`).
3. **Tertiary Key Match (Name + City):** Links records that only possess Name and City (e.g. bridging `source2` and `source3` when absent in `source1`, such as *Divya Chopra*), with strict **conflict-safety guardrails** ensuring different phone numbers or emails prevent accidental merges.

### Ingestion Results
- **Raw Input Records:** 103 parsed records
- **Unified Master Candidates:** 55 unique candidate profiles
- **Merged across $\ge 2$ Sources:** 30 candidates
- **Merged across all 3 Sources:** 15 candidates

---

## 4. Task 2: n8n Low-Code Automation Workflow

Located in [`automation/`](./automation/):
- **[`n8n_candidate_enrichment_pipeline.json`](./automation/n8n_candidate_enrichment_pipeline.json)**: Complete importable n8n workflow.
- **[`simulate_n8n_flow.py`](./automation/simulate_n8n_flow.py)**: CLI simulation runner.
- **[`n8n_flow_diagram.svg`](./app/static/n8n_flow_diagram.svg)**: Interactive architectural graph.

### Pipeline Nodes:
1. **Webhook Trigger:** Receives candidate payload via HTTP POST.
2. **Data Cleaner (JS Code Node):** Normalizes phone (`+91`/`0` $\rightarrow$ 10 digits), cleans email, formats skills.
3. **Database Check (HTTP Request):** Queries `/api/candidates/check-duplicate` on SQLite backend.
4. **IF Duplicate Router:**
   - **Branch A (Duplicate):** Formats alert and dispatches notification to Slack/Discord/Webhook with matched candidate ID and source history.
   - **Branch B (Unique):** Passes profile to AI Classifier.
5. **LLM AI Skill Classifier:** Auto-classifies candidate into categories (`automation-heavy`, `web dev`, `data`) and determines seniority with reasoning.
6. **Writeback Node:** Persists enriched profile to SQLite via `/api/candidates/enrich`.

```bash
# Run local n8n simulation
python automation/simulate_n8n_flow.py
```

---

## 5. Task 3: Mini Audio Collection App & Signal Analysis

Built as a single-page web app inside `app/` accessible at `http://localhost:8000`:
- **In-Browser Audio Recording:** Live microphone recorder utilizing Web Audio API + MediaRecorder, featuring a real-time animated oscilloscope/frequency canvas visualizer, timer, and preview playback.
- **File Upload:** Drag & drop support for `.wav`, `.mp3`, `.webm`, `.ogg`, and `.m4a`.
- **Signal Processing Engine (`app/audio_analyzer.py`):**
  - **Duration:** Exact length in seconds.
  - **Sample Rate (kHz):** Digital sampling frequency (e.g. 44.1 kHz, 48.0 kHz).
  - **Bitrate (kbps):** Measured stream bandwidth.
  - **Loudness (dBFS):** True Root Mean Square (RMS) energy relative to full scale:
    $$\text{RMS} = \sqrt{\frac{1}{N}\sum_{i=1}^N x_i^2}, \quad \text{Loudness} = 20\log_{10}(\text{RMS})$$
  - **Noise Floor & SNR (dB):** Ambient background noise floor estimation using bottom 10th percentile energy windows vs speech power.
  - **Clipping Ratio & Quality Verdict:** Computes digital saturation percentage and classifies recording into *"Studio Quality / Pristine"*, *"Clear Voice"*, *"Moderate Quality / Noticeable Noise"*, or *"Distorted / Audio Clipping"*.
- **Submissions Explorer:** Dynamic table with audio players, metric chips, and search/filter controls.

---

## 6. Task 4: Data Issues Report Summary

*(Full report available at [`docs/DATA_ISSUES_REPORT.md`](./docs/DATA_ISSUES_REPORT.md))*

| Source File | Key Anomalies Found | Remediation Applied |
|---|---|---|
| **`source1_naukri`** | Mixed CTC units (raw INR like `417964` vs LPA `4.2`), 7 distinct date formats (`24-07-2026`, `7 Jul 2026`, `07/13/2026`), unstandardized cities (`GURGAON`, `gurugram `), name initials (`R. Verma` vs `Rohit Verma`). | Threshold-based CTC conversion (<100 = LPA, $\ge$10000 = INR), ISO-8601 date parsing, canonical city lookup, alias unification to full name. |
| **`source2_gig_workers`** | Empty row at line 12 (`,,,,,`), column shift at line 20 (skills placed in email field), uppercase emails, mixed rates (`1415/hr` vs `15k/month`), mixed status casing. | Blank-row skipping, automatic column shift realignment heuristic, lowercase email normalization, rate parsing with standardized monthly equivalents. |
| **`source3_cbnexus`** | Embedded header row at line 16, ALL-CAPS names (`RITU SHARMA`), phone delimiters (`+91-`), boolean variants (`Y`, `yes`, `No`, `N`), common name collision (`Arjun Mehta` with 2 distinct phones). | Header filter skip, title casing, digit-only 10-digit phone cleaning, boolean normalization, phone-differentiated entity separation. |

---

## 7. Task 5: High-Scale Architecture (5,000 Workers)

*(Full 1-page report available at [`docs/STRETCH_5000_WORKERS.md`](./docs/STRETCH_5000_WORKERS.md))*

- **What Breaks First:** Synchronous audio signal extraction blocks web worker threads (causing 504 gateway timeouts), mobile network drops fail large multipart uploads, SQLite file locking fails under concurrent writes, and local disk fills up.
- **Redesigned Production Architecture:**
  - **Direct-to-S3 Pre-signed Uploads** with client-side chunked resumable upload (Tus protocol).
  - **Asynchronous Queue (AWS SQS + Celery/Lambda Workers)** for non-blocking acoustic extraction.
  - **PostgreSQL + PgBouncer** connection pooling.
  - **Idempotency Keys & Waveform Fingerprinting (Chromaprint)** to eliminate duplicate processing.
  - **Cost:** **<$20 total** for the entire 5,000-worker launch weekend.

---

## 8. Stuck Log

*Detailed log of the 3 hardest engineering challenges encountered, how they were resolved, AI prompts tested, and rejected alternatives:*

### 1. Column Shift & Malformed Delimiters in `source2_gig_workers.csv`
- **The Problem:** Row 20 contained `"react, javascript, mysql",ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG,Isha Chopra,1406/hr,Pune,active`. The skills string was placed in the first column (`email_id`), shifting every other field rightward. Naive CSV parsers assigned `"react, javascript, mysql"` as the email and crashed downstream regex validators.
- **What I Searched / Asked AI:**
  - *"How to programmatically detect shifted columns in CSV rows when certain fields contain specific domain formats like email @ or rate substrings?"*
- **Rejected Approaches:**
  - *Hardcoding row index 20:* Rejected because hardcoding specific line numbers is fragile and fails when new batches are ingested.
  - *Dropping corrupted rows:* Rejected because losing candidate records (Isha Chopra) reduces data completeness.
- **How I Got Unstuck:**
  - Designed a semantic column alignment heuristic in `parse_source2_gig_workers()`: if `col[0]` does not contain `@` and `col[1]` contains `@`, the row is automatically detected as a shifted skill-row and realigned into standard column order before passing to normalizers.

---

### 2. Cross-Browser Audio Recording Codecs & Pure-Python Feature Extraction
- **The Problem:** In-browser audio recording in Chrome/Edge produces `audio/webm;codecs=opus`, which lacks standard PCM headers. Standard Python `wave` library only parses uncompressed WAV files and throws `wave.Error: unknown format: 65534 / file does not start with RIFF id`. Using external system binaries like `ffmpeg.exe` was risky because evaluator environments may not have FFmpeg installed on system PATH.
- **What I Searched / Asked AI:**
  - *"How to extract sample rate, bitrate, and true RMS loudness from WebM/Opus audio in Python without shelling out to ffmpeg binary?"*
- **Rejected Approaches:**
  - *Requiring users to install system FFmpeg:* Rejected because it introduces external environment dependencies and causes setup friction.
  - *Transcoding in browser via heavy FFmpeg.wasm:* Rejected due to high initial bundle size (>25MB) slowing down initial page load.
- **How I Got Unstuck:**
  - Implemented a two-tier extraction engine in [`app/audio_analyzer.py`](./app/audio_analyzer.py):
    1. For `.wav` files: uses `numpy` and `wave` to compute exact frame-level RMS loudness ($20\log_{10}(\text{RMS})$), digital clipping count, and 50ms windowed frame energy for SNR noise floor estimation.
    2. For compressed files (`.webm`, `.mp3`, `.ogg`, `.m4a`): uses Python `soundfile` (bundled libsndfile binary) with a graceful fallback to `mutagen` container parsing. This provides robust cross-codec support with zero system dependencies.

---

### 3. Entity Resolution Ambiguity: Disambiguating Common Names vs Name Aliases
- **The Problem:** 
  - Case A: `source1` row 25 had `R. Verma` with email `rohit.verma13@mailtest.example.org` and phone `9000000294`, which clearly refers to `Rohit Verma` (Row 31).
  - Case B: `source1` and `source3` both contained candidates named `Arjun Mehta`, but one had phone `9000000131` while the other had phone `9000000272`. A naive fuzzy name matcher would merge them into one, corrupting two real people into a single record.
- **What I Searched / Asked AI:**
  - *"Entity resolution deterministic cascade logic to handle name initials and prevent collisions on common Indian names with conflicting contact details."*
- **Rejected Approaches:**
  - *Pure String Levenshtein distance on names:* Rejected because common names with different phones would produce false positive merges.
  - *Merging only on exact (Name, Email, Phone) triple:* Rejected because `source2` lacks phones and `source3` lacks emails.
- **How I Got Unstuck:**
  - Built a **Conflict-Safe Deterministic Resolution Graph** in [`pipeline/matcher.py`](./pipeline/matcher.py):
    - Priority 1: Match on normalized Email.
    - Priority 2: Match on normalized 10-digit Phone.
    - Priority 3: Match on (Name + City) ONLY if neither record has a conflicting phone or email. If incoming phone or email contradicts an existing record, the engine safely isolates them into separate master profiles (`Arjun Mehta #1` vs `Arjun Mehta #2`).

---

## 9. Video Walkthrough Guide

*(For recording the candidate's Loom / screen recording - max 6 minutes):*

1. **Introduction (0:00 - 0:45):**
   - Introduce yourself and state the project scope: ConsultBae AI Automation Platform.
   - Mention the 3 core pillars: Ingestion & Merge (Task 1), n8n Workflow (Task 2), and Audio Collection Web App (Task 3).
2. **Task 1 Ingestion & Merge Demo (0:45 - 2:00):**
   - Run `python -m pipeline.ingest` in terminal.
   - Highlight the 103 input records reconciling into 55 unified master candidates in SQLite.
   - Open SQLite / Web UI database tab and show a multi-source merged candidate (e.g. *Tanvi Gupta* or *Vikram Saxena*) with combined skills, CTC, and gig rate.
3. **Task 2 n8n Automation Demo (2:00 - 3:15):**
   - Show `automation/n8n_candidate_enrichment_pipeline.json` in n8n or run `python automation/simulate_n8n_flow.py`.
   - Demonstrate the two branches:
     - Branch 1: Triggering a duplicate alert on an existing candidate.
     - Branch 2: Classifying a new candidate's skills into `"automation-heavy"` with LLM reasoning and writing back to database.
4. **Task 3 Audio Collection App Demo (3:15 - 4:45):**
   - Open `http://localhost:8000` in browser.
   - Demonstrate in-browser audio recording: click **Start Recording**, speak into mic, watch the live Web Audio canvas visualizer, stop and preview.
   - Click **Submit & Extract Audio Signal Properties**: showcase real-time extraction of Duration (s), Sample Rate (kHz), Bitrate (kbps), Loudness (dBFS), and SNR Noise Quality Rating.
   - Switch to **Submissions Explorer** tab and play the recorded audio.
5. **Key Engineering Decisions & Stuck Log (4:45 - 5:45):**
   - Walk through the 2 hardest hurdles: shifted CSV columns recovery and cross-codec audio extraction.
6. **Closing (5:45 - 6:00):**
   - Summarize the modular codebase, automated test suite, and Task 5 scalability plan.
