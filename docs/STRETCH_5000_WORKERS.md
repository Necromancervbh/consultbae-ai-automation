# Task 5 — High-Scale System Architecture: 5,000 Gig Workers Launch

## 1. Traffic & Ingestion Modeling

Launching our audio collection platform to **5,000 gig workers** over a 48-hour weekend involves:
- **Total Submissions:** ~12,500 audio recordings (averaging 2.5 submissions per worker).
- **Peak Concurrency:** 250–500 simultaneous uploads during high-engagement evening windows (6:00 PM – 10:00 PM).
- **Data Volume:** ~15 GB to 40 GB of compressed/uncompressed audio ingress.

---

## 2. What Breaks First in the Miniature Architecture?

If the current lightweight prototype were deployed directly without architectural changes, the following critical failures would occur in chronological order:

```
[500 Concurrent Mobile Uploads]
             │
             ├──► (1) Web Worker Starvation: Synchronous signal analysis holds HTTP connections open
             │         └──► Result: 504 Gateway Timeouts & connection pool exhaustion.
             │
             ├──► (2) Mobile Network Drops: Flaky 3G/4G connections drop multi-megabyte multipart uploads
             │         └──► Result: 35%+ submission failure rate without chunked resumable upload.
             │
             ├──► (3) Database Lock Contention: SQLite file locks under simultaneous writes
             │         └──► Result: `sqlite3.OperationalError: database is locked`.
             │
             └──► (4) Ephemeral Storage Overflow: Local disk fills up or loses recordings on container restart.
```

---

## 3. Production Architecture Redesign

To guarantee zero downtime, 99.99% upload reliability, and sub-second UI responsiveness, we transition to a decoupled, cloud-native architecture:

```
[Gig Worker (Mobile/Web)]
           │
           │ (1) Request Pre-signed Upload URL
           ▼
[FastAPI Gateway (ECS / Cloud Run)] ──► [PostgreSQL + PgBouncer]
           │
           │ (2) Returns S3 Presigned URL + Idempotency Key
           ▼
[Direct-to-S3 / Cloudflare R2] (Tus.io Resumable Multipart Upload)
           │
           │ (3) S3 ObjectCreated Event
           ▼
[AWS SQS / Redis Queue]
           │
           │ (4) Dequeues Audio Processing Job
           ▼
[Worker Pool (Celery / AWS Lambda)]
   - Audio Signal Extraction (Duration, kHz, Bitrate, Loudness, SNR)
   - Audio Fingerprinting (Chromaprint / De-duplication)
   - Transcoding (Opus/AAC 64kbps archive)
           │
           │ (5) Updates Record & Dispatches WebSocket Notification
           ▼
[PostgreSQL Database] ──► [WebSocket Gateway] ──► [Worker Live UI]
```

### Key Architectural Improvements:

1. **Direct-to-Object-Storage Uploads via Pre-signed URLs:**
   - Audio files never touch backend application servers.
   - The web app requests an authenticated pre-signed URL from S3/Cloudflare R2 and streams the audio directly from the worker's browser to the cloud bucket.
   - Removes memory and bandwidth bottlenecks from the API tier entirely.

2. **Chunked Resumable Uploads (Tus Protocol):**
   - For mobile workers with unstable network connectivity, audio is uploaded in 512 KB chunks. If the connection drops at 90%, the client resumes from byte offset rather than restarting from zero.

3. **Asynchronous Signal Extraction Workers:**
   - Audio mathematical analysis (RMS loudness, FFT, SNR, noise floor) is offloaded to an asynchronous worker pool (Celery / AWS Lambda) triggered by SQS events.
   - FastAPI response time drops from 2,500ms to **<40ms**.

4. **PostgreSQL with PgBouncer Connection Pooling:**
   - Replaces SQLite with Amazon Aurora PostgreSQL / Supabase, utilizing PgBouncer to multiplex hundreds of incoming transactions into a tight pool of persistent connections.

5. **Audio Fingerprinting & Idempotency:**
   - Every submission generates a client-side UUID idempotency token and an audio waveform hash (e.g. Chromaprint). Duplicate button presses or resubmissions of the exact same audio are immediately detected and de-duplicated without re-running compute.

---

## 4. Financial & Cloud Infrastructure Cost Modeling

Estimated total infrastructure cost to support **5,000 gig workers over the weekend**:

| Component | Service / Configuration | Weekend Usage Estimate | Total Cost (USD) |
|---|---|---|---|
| **Object Storage** | Cloudflare R2 / AWS S3 Standard | 35 GB stored + Zero Egress fees (R2) | **$0.55** |
| **API Web Tier** | AWS App Runner / 2x t4g.small instances | 48 hours runtime with auto-scaling | **$7.20** |
| **Async Processing** | AWS Lambda / Celery Spot Instances | 12,500 audio executions @ 2s each | **$3.80** |
| **Managed Database** | Amazon RDS PostgreSQL `db.t4g.micro` | 48 hours + automated backups | **$4.50** |
| **Edge CDN & DDoS** | Cloudflare Pro / Free Tier | SSL, caching, rate limiting | **$0.00** |
| **Total Weekend Cost** | | | **~$16.05** |

> **Conclusion:** By leveraging direct-to-S3 uploads and serverless asynchronous audio workers, the platform scales linearly to 5,000+ gig workers with zero server bottlenecks at an operating cost of **less than $20 for the entire launch**.
