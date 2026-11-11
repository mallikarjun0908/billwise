# BillWise

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Firebase](https://img.shields.io/badge/Firebase-Hosting%20%26%20App%20Hosting-FFA611.svg?style=flat&logo=firebase)](https://firebase.google.com)
[![Google Cloud Run](https://img.shields.io/badge/Google%20Cloud-Cloud%20Run-4285F4.svg?style=flat&logo=googlecloud)](https://cloud.google.com/run)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI-assisted electricity bill auditing and energy savings coach supporting **UN Sustainable Development Goals 7 (Affordable and Clean Energy)** and **9 (Industry, Innovation, and Infrastructure)**.

Upload a BESCOM / Indian DISCOM electricity bill photo or PDF &rarr; Tesseract OCR extracts billing metadata &rarr; Tariff rules engine recomputes charges to the paisa &rarr; Actionable plain-language savings recommendations.

---

## Architecture Overview

BillWise is architected as a hybrid serverless system on **Google Cloud / Firebase**:

```
                  ┌──────────────────────────────────────────────┐
                  │           Firebase Global CDN Edge           │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
          Static Assets (`/`, `*.js`, `*.css`)        API Rewrites (`/api/**`, `/health`)
                 │                                               │
                 ▼                                               ▼
     ┌───────────────────────┐                    ┌───────────────────────────────┐
     │   Firebase Hosting    │                    │       Google Cloud Run        │
     │   (public/ directory) │                    │        (billwise-api)         │
     └───────────────────────┘                    │    FastAPI + Tesseract OCR    │
                                                  └───────────────┬───────────────┘
                                                                  │
                                      ┌───────────────────────────┴───────────────────────────┐
                                      │                                                       │
                                      ▼                                                       ▼
                       ┌───────────────────────────────┐                       ┌───────────────────────────────┐
                       │  Database (Multi-Engine)      │                       │  Storage (Optional)           │
                       │  - Cloud SQL (PostgreSQL)     │                       │  - Firebase Cloud Storage     │
                       │  - Google Cloud Firestore     │                       │  - Local ephemeral disk       │
                       │  - SQLite (Local fallback)    │                       │  - Privacy mode (not stored)  │
                       └───────────────────────────────┘                       └───────────────────────────────┘
```

- **Frontend**: Single-page modern application in `public/` (and mirrored in `backend/app/static/`) served with sub-50ms latency via Firebase Hosting CDN.
- **Backend**: Containerized FastAPI service on Google Cloud Run with automatic scaling from 0 to 10 instances.
- **Modern App Hosting**: Pre-configured `apphosting.yaml` for next-generation Firebase App Hosting.
- **Zero Lock-In Storage & Database**: Supports PostgreSQL (Cloud SQL / Supabase), Google Cloud Firestore, or SQLite fallback.

---

## Getting Started Locally

### 1. Run with Python & Uvicorn (No Docker)

```bash
# Clone the repository
git clone https://github.com/your-username/billwise.git
cd billwise/backend

# Create virtual environment and activate
python3 -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows

# Install dependencies (requires Tesseract OCR on system)
pip install -r requirements.txt

# Start backend server
uvicorn app.main:app --reload --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

> [!NOTE]
> Photo scanning requires Tesseract OCR installed on your host system:
> - **Ubuntu/Debian**: `sudo apt install tesseract-ocr tesseract-ocr-eng`
> - **macOS**: `brew install tesseract`
> - **Windows**: Download installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

Run backend tests:
```bash
pytest -v
```

### 2. Run with Docker Compose (PostgreSQL + API)

```bash
docker compose up --build
```
This spins up:
- PostgreSQL 16 on port `5432`
- BillWise API + Tesseract container on port `8000` at [http://localhost:8000](http://localhost:8000)

### 3. Run with Firebase Emulators

To test Firebase Hosting rewrites locally:
```bash
# Install Firebase CLI if not already installed
npm install -g firebase-tools

# Start emulators
firebase emulators:start
```
The Hosting emulator will be available at [http://localhost:5000](http://localhost:5000) and the Firebase Emulator UI at [http://localhost:4000](http://localhost:4000).

---

## Deploying to Firebase & Cloud Run

### Prerequisites

1. Install the [Firebase CLI](https://firebase.google.com/docs/cli):
   ```bash
   npm install -g firebase-tools
   firebase login
   ```
2. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install):
   ```bash
   gcloud auth login
   gcloud config set project <YOUR_PROJECT_ID>
   ```

### Step 1: Configure Your Project

Link your Firebase project:
```bash
firebase use --add <YOUR_PROJECT_ID>
```
Verify or update `.firebaserc`:
```json
{
  "projects": {
    "default": "<YOUR_PROJECT_ID>"
  }
}
```

### Step 2: Deploy Backend Container to Google Cloud Run

Build and deploy the container image directly to Cloud Run:
```bash
# Enable required Google Cloud services
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# Build and submit container image
gcloud builds submit --tag gcr.io/<YOUR_PROJECT_ID>/billwise-api .

# Deploy to Cloud Run
gcloud run deploy billwise-api \
  --image gcr.io/<YOUR_PROJECT_ID>/billwise-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars STORE_UPLOADS=false
```

### Step 3: Deploy Frontend to Firebase Hosting

Once Cloud Run is live, deploy Firebase Hosting. It automatically connects static assets and proxies `/api/**` and `/health` requests to Cloud Run according to `firebase.json`:

```bash
firebase deploy --only hosting
```

Your app will be live at:
`https://<YOUR_PROJECT_ID>.web.app` and `https://<YOUR_PROJECT_ID>.firebaseapp.com`

---

## Modern Firebase App Hosting Support

BillWise includes full configuration for [Firebase App Hosting](https://firebase.google.com/docs/app-hosting) via [`apphosting.yaml`](file:///home/atomic/billwise/apphosting.yaml).

To initialize App Hosting with GitHub integration:
```bash
firebase apphosting:backends:create --project <YOUR_PROJECT_ID>
```
App Hosting will build your container from the root `Dockerfile` and manage rolling revisions, custom domains, and compute scaling automatically.

---

## Environment Variables & Configuration

All configuration is managed through environment variables (or `.env` file):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `8080` | Port listened to by the web server (Cloud Run injects this) |
| `STORE_UPLOADS` | `true` (local) / `false` (prod) | When `false`, photos are processed in memory and discarded (privacy-first) |
| `DATABASE_URL` | `sqlite:///./billwise.db` | Database connection string (PostgreSQL, Cloud SQL, or SQLite) |
| `CLOUD_SQL_CONNECTION_NAME` | `""` | Cloud SQL instance connection name (e.g. `project:region:instance`) |
| `FIREBASE_STORAGE_BUCKET` | `""` | Firebase Cloud Storage bucket (e.g. `app.appspot.com`) for uploads |
| `USE_FIRESTORE` | `false` | Enable Firestore mode instead of relational SQL |
| `FIRESTORE_PROJECT_ID` | `""` | Google Cloud project ID for Firestore client |
| `ANTHROPIC_API_KEY` | `""` | Claude API key for enhanced AI energy savings coach advice |
| `LLM_MODEL` | `claude-sonnet-4-6` | Anthropic model identifier |
| `MAX_UPLOAD_MB` | `10` | Maximum allowed bill upload size in megabytes |

---

## CI/CD Automated Deployment

Automated CI/CD is configured in [`.github/workflows/firebase-deploy.yml`](file:///home/atomic/billwise/.github/workflows/firebase-deploy.yml).

### Required GitHub Repository Secrets

Configure the following secrets under **Repository Settings &rarr; Secrets and variables &rarr; Actions**:

1. `GCP_PROJECT_ID`: Your Google Cloud / Firebase project ID.
2. `GCP_SA_KEY`: Base64 or plain JSON key for a Google Cloud Service Account with `Cloud Run Admin`, `Storage Admin`, and `Artifact Registry Writer` roles.
3. `FIREBASE_TOKEN`: Firebase CI token generated via `firebase login:ci`.

Every push to `main` runs pytest unit tests, builds the optimized Docker container, updates Cloud Run, and deploys Firebase Hosting without downtime.

---

## Render to Firebase Migration Notes

BillWise previously deployed to Render via `render.yaml`. The platform was migrated to Firebase and Google Cloud Run for key architectural benefits:

- **No 30-Day Database Expiry**: Render's free PostgreSQL databases expire and delete data after 30 days. Google Cloud SQL / Firestore have persistent lifecycle management.
- **Zero Cold Starts for Web Assets**: Static HTML, CSS, and JS are served globally from Firebase's multi-region edge caches rather than waiting for a backend container to wake up.
- **Integrated Identity & Storage**: Direct integration with Firebase Storage and Firebase Authentication if user accounts are added in the future.
- **Cost Efficiency**: Cloud Run scales to zero instances when idle, incurring zero compute cost during inactivity while remaining instantly responsive.

The original Render configuration is preserved in [`render.yaml`](file:///home/atomic/billwise/render.yaml) with deprecation markers for reference.

---

## Project Structure

```
billwise/
├── .firebaserc                          # Firebase project alias definition
├── firebase.json                        # Firebase Hosting rewrites & CDN headers
├── apphosting.yaml                      # Modern Firebase App Hosting configuration
├── Dockerfile                           # Multi-stage container for Cloud Run & App Hosting
├── docker-compose.yml                   # Local development with PostgreSQL
├── render.yaml                          # Legacy Render deployment blueprint (deprecated)
├── .env.example                         # Environment variables template
├── public/                              # Standalone frontend assets for Firebase CDN
│   └── index.html                       # Modern Tailwind UI with dark mode & live preview
├── frontend/                            # Developer frontend copy
│   └── index.html
├── backend/
│   ├── Dockerfile                       # Backend container definition
│   ├── requirements.txt                 # Python dependencies (FastAPI, GCS, Firestore)
│   ├── pytest.ini                       # Test suite runner settings
│   ├── app/
│   │   ├── main.py                      # FastAPI application entry point
│   │   ├── config.py                    # Cloud-aware settings (Pydantic)
│   │   ├── db.py                        # Resilient connection pool (Postgres, SQLite, Firestore)
│   │   ├── models.py                    # SQLAlchemy database models (Premises, Bill)
│   │   ├── api/
│   │   │   └── bills.py                 # REST endpoints (/scan, /premises, /verify)
│   │   ├── services/
│   │   │   ├── storage.py               # Firebase Cloud Storage & local storage handler
│   │   │   ├── tariff_engine.py         # Rules-as-data electricity tariff computation
│   │   │   ├── ocr.py                   # Tesseract OCR engine & regex parser
│   │   │   └── coach.py                 # Plain-language energy savings coach
│   │   └── static/                      # FastAPI embedded static assets
│   │       └── index.html
│   └── tests/                           # Pytest unit & integration tests
│       ├── test_api.py
│       ├── test_coach.py
│       ├── test_extraction.py
│       ├── test_ocr.py
│       └── test_tariff_engine.py
├── tariffs/                             # Tariff specification rules
│   └── sample_domestic.json             # BESCOM LT-1 Domestic slab rates & rules
└── .github/
    └── workflows/
        └── firebase-deploy.yml          # GitHub Actions CI/CD for Cloud Run & Hosting
```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
