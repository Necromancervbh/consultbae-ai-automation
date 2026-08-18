# ConsultBae — Task 4: Comprehensive Data Issues Report

## 1. Executive Summary

This report documents every data quality anomaly, syntactic corruption, and schema inconsistency discovered across the 3 provided datasets:
- `source1_naukri_applicants.csv` (Naukri recruitment applicants)
- `source2_gig_workers.csv` (Gig worker registry)
- `source3_cbnexus_contacts.csv` (CBNexus partner contact list)

A total of **103 input records** were processed. Through our automated cleaning and deterministic identity resolution pipeline, these were reconciled into **55 unified master candidates** (with 30 candidates merged across $\ge 2$ sources and 15 appearing in all 3 sources).

---

## 2. Dataset-by-Dataset Forensic Audit

### 2.1. File 1: `source1_naukri_applicants.csv`

| # | Anomaly / Issue Identified | Concrete Example in Data | Root Cause & Risk | Applied Engineering Remediation |
|---|---|---|---|---|
| **1.1** | **Mixed CTC Representation Units** | Row 2: `417964`<br>Row 6: `4.2`<br>Row 8: `8.3`<br>Row 13: `1195422` | Some values are recorded in raw annual INR (e.g. `417964`), while others are expressed in Lakhs Per Annum (`4.2` LPA). Direct aggregation would yield massive errors. | Heuristic normalization: values $< 100.0$ are treated as LPA (e.g. `4.2` $\rightarrow$ 4.20 LPA = 420,000 INR); values $\ge 10,000$ are converted from INR to LPA (`417964` $\rightarrow$ 4.18 LPA). Both `current_ctc_lpa` (float) and `current_ctc_raw_inr` (int) are stored. |
| **1.2** | **Heterogeneous Date Formatting** | Row 2: `24-07-2026`<br>Row 3: `2026-08-08`<br>Row 5: `7 Jul 2026`<br>Row 7: `07/13/2026`<br>Row 8: `19 Jul 2026` | 7 distinct date format strings used interchangeably across rows. Prevents SQL range queries and temporal sorting. | Implemented multi-format regex & strptime parser mapping all valid date variations to standard ISO-8601 (`YYYY-MM-DD`). |
| **1.3** | **Unstandardized City Names & Trailing Spaces** | Row 3: `GURGAON`<br>Row 6: `pune`<br>Row 10: `gurugram `<br>Row 12: `new delhi`<br>Row 25: `Bangalore` | Mixed casing (`GURGAON` vs `gurugram`), trailing whitespace (`gurugram `), and regional synonyms (`Bangalore` vs `Bengaluru`, `Delhi` vs `Delhi NCR` vs `New Delhi`). | Created canonical city mapping table: `gurgaon`/`gurugram` $\rightarrow$ `Gurugram`, `bangalore`/`bengaluru` $\rightarrow$ `Bengaluru`, `delhi`/`new delhi`/`delhi ncr` $\rightarrow$ `Delhi NCR`. |
| **1.4** | **Inconsistent Phone Prefixes** | Row 2: `+919000000254`<br>Row 3: `9000000237`<br>Row 4: `09000000287` | Mixed international dialing codes (`+91`), trunk prefixes (`0`), and raw 10-digit formats prevent direct string matching. | Stripped all non-digits, removed leading `91` (if 12 digits) or leading `0` (if 11 digits), validating a canonical 10-digit string. |
| **1.5** | **Name Abbreviation & Aliasing** | Row 25: `R. Verma`<br>Row 31: `Rohit Verma` | Row 25 and Row 31 share the identical email (`rohit.verma13@mailtest.example.org`) and phone (`9000000294`), but Row 25 used an abbreviated initial. | Ingestion engine links by primary email/phone key and upgrades the name from abbreviated `R. Verma` to full `Rohit Verma`. |
| **1.6** | **Secondary Email Alias** | Row 27: `alt.nikhil.chopra70@example.com`<br>Row 37: `nikhil.chopra70@example.com` | Same candidate (`Nikhil Chopra`, phone `9000000103`) submitted two applications with different email addresses. | Phone-first resolution links both records to the single candidate identity. |

---

### 2.2. File 2: `source2_gig_workers.csv`

| # | Anomaly / Issue Identified | Concrete Example in Data | Root Cause & Risk | Applied Engineering Remediation |
|---|---|---|---|---|
| **2.1** | **Corrupted Empty Row** | Row 12: `,,,,,` | Blank delimiter line in CSV. Standard CSV readers generate empty objects or crash type casting. | Added row-level blank check `if not any(field.strip() for field in row): continue`. |
| **2.2** | **CRITICAL: Shifted Columns / Field Misalignment** | Row 20: `"react, javascript, mysql",ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG,Isha Chopra,1406/hr,Pune,active` | Skills were mistakenly placed in the 1st column (`email_id`), shifting Email to `worker_name`, Name to `rate`, Rate to `location`, and Location to `status`. | Built an intelligent anomaly detector: if `col[0]` contains commas or lacks `@` and `col[1]` contains `@`, automatically realign columns to their true semantic positions before normalization. |
| **2.3** | **UPPERCASE Email Addresses** | Row 7: `ISHA.CHOPRA95@...`<br>Row 13: `VARUN.SAXENA21@...`<br>Row 15: `DEEPAK.NAIR44@...` | Mixed casing breaks standard case-sensitive database index lookups. | Enforced `.strip().lower()` normalization across all email ingestion paths. |
| **2.4** | **Mixed Compensation Rate Formats** | Row 2: `1415/hr`<br>Row 6: `15k/month`<br>Row 10: `72k/month` | Hourly freelance rates vs monthly retainer contracts cannot be compared directly without conversion. | Parsed rates into explicit fields: `rate_type` (`hourly` vs `monthly`), `rate_amount`, and calculated standardized monthly equivalent (`hourly * 160 hrs/mo`). |
| **2.5** | **Inconsistent Status Casing** | Row 4: `active`<br>Row 5: `ACTIVE`<br>Row 9: `Active`<br>Row 10: `Inactive`<br>Row 11: `paused` | Inconsistent enum casing prevents categorical grouping. | Normalized to canonical title case: `Active`, `Inactive`, `Paused`. |

---

### 2.3. File 3: `source3_cbnexus_contacts.csv`

| # | Anomaly / Issue Identified | Concrete Example in Data | Root Cause & Risk | Applied Engineering Remediation |
|---|---|---|---|---|
| **3.1** | **Duplicate Header Row Inside Data** | Row 16: `Name,Phone Number,City,Verified,Projects Completed` | Header was accidentally copy-pasted into the middle of the CSV payload during concatenation. | Added header detection filter: if row matches header labels, skip ingestion and log anomaly. |
| **3.2** | **ALL-CAPS Names** | Row 3: `RITU SHARMA`<br>Row 7: `RAHUL MALHOTRA`<br>Row 9: `SAHIL MALHOTRA`<br>Row 14: `KARAN BHATIA` | Data entered in uppercase shouting format. | Normalized with title casing while preserving abbreviations (e.g. `Ritu Sharma`, `Rahul Malhotra`). |
| **3.3** | **Phone Number Delimiters & Dial Codes** | Row 4: `919000000231`<br>Row 5: `+91-9000000131`<br>Row 10: `+91-9000000227` | Hyphenated strings (`+91-`) and raw `91` prefixes. | Cleaned using digit extraction and standard 10-digit formatting. |
| **3.4** | **Inconsistent Verification Flags** | Row 2: `Y`<br>Row 3: `yes`<br>Row 4: `No`<br>Row 9: `N`<br>Row 25: `Yes` | Mixed boolean representations (`Y`, `yes`, `Yes`, `No`, `N`). | Normalized to strict boolean `True` / `False` / `None`. |
| **3.5** | **Disambiguation of Common Names** | Row 5: `Arjun Mehta` (Phone `9000000131`)<br>Row 28: `Arjun Mehta` (Phone `9000000272`) | Two distinct individuals sharing the common name "Arjun Mehta". A naive name-only merge would incorrectly corrupt their records into one. | Enforced conflict safety: if incoming phone differs from existing candidate's phone, they are maintained as separate distinct master candidates. |

---

## 3. Entity Resolution Decision Architecture

```
[Incoming Source Record]
          │
          ├──► (1) Exact match on normalized Email?  ──────────► Merge into Candidate
          │
          ├──► (2) Exact match on normalized 10-digit Phone? ──► Merge into Candidate
          │
          ├──► (3) Match on (Name + City)?
          │          │
          │          ├── If Email/Phone CONFLICTS with existing record ──► Create NEW Candidate
          │          └── If No conflicting Email/Phone                 ──► Merge into Candidate
          │
          └──► (4) No match found ──────────────────────────────► Create NEW Candidate
```
