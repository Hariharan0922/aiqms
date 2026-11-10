# Environment Setup and Configuration Guide

This guide details the complete environment configuration and local setup instructions for **AiDocMaker**.

---

## 1. Prerequisites

Ensure the following tools are installed on your host machine:

| Component | Minimum Version | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11+ | 3.12 / 3.13 | Virtual environment recommended |
| **Node.js** | 20.x+ | LTS (v20 or v22) | Includes npm |
| **Git** | 2.x+ | Latest | Version control |
| **NVIDIA API Key** | — | Active Key | Required for hosted NIM generation |

> [!NOTE]
> Local LLM runtimes (Ollama, PyTorch local weights, CUDA local runtimes) are **no longer required**. All AI inference is executed over HTTPS via the NVIDIA NIM hosted API.

---

## 2. Environment Variables Configuration

Copy the template from `.env.example` in both the project root and `apps/api/.env`:

```bash
cp .env.example .env
cp .env.example apps/api/.env
```

### Complete Environment Specification:

```ini
# --- Application Branding & Identity ---
APP_NAME="AiDocMaker - Intelligent Document Automation"
APP_ENV=development
APP_SECRET=replace-with-a-secure-random-secret-in-production
DEV_AUTH_ENABLED=true

# --- Database Storage ---
# Default: SQLite in WAL mode
DATABASE_URL=sqlite:///./aiqms.db
# For PostgreSQL in staging/production:
# DATABASE_URL=postgresql://user:password@localhost:5432/aiqms

# --- NVIDIA NIM Hosted API (Primary Inference Engine) ---
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=poolside/laguna-xs-2.1
NVIDIA_TIMEOUT=120
NVIDIA_MAX_RETRIES=2

# --- Storage Directories ---
STORAGE_DIR=./data
EVIDENCE_DIR=./data/evidence
EXPORTS_DIR=./data/exports
CHROMA_PERSIST_DIR=./data/chroma

# --- Web Frontend Configuration ---
VITE_API_BASE_URL=http://localhost:8000
```

---

## 3. Step-by-Step Installation

### Step A: Backend Setup (`apps/api`)

1. Open PowerShell / Bash and navigate to the API directory:
   ```bash
   cd apps/api
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Verify database migrations and schema initialization:
   ```bash
   python -c "from app.db.session import engine; from app.db.migrations import run_migrations; run_migrations(engine); print('Database ready!')"
   ```

5. Launch the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Confirm availability by browsing to `http://localhost:8000/api/v1/system/diagnostics`.

---

### Step B: Frontend Setup (`apps/web`)

1. Open a second terminal and navigate to the Web directory:
   ```bash
   cd apps/web
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Launch Vite development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

---

## 4. Troubleshooting Common Issues

### Issue 1: `NVIDIA_API_KEY is not configured`
- **Cause:** The environment variable is missing or empty.
- **Fix:** Set `NVIDIA_API_KEY=nvapi-...` in `apps/api/.env` and restart the FastAPI server. You can verify connection readiness using the `POST /api/v1/system/test-nvidia` endpoint or the Settings page in the web UI.

### Issue 2: SQLite database lock (`[WinError 32]`)
- **Cause:** Multiple concurrent processes accessing SQLite without WAL mode enabled.
- **Fix:** Ensure all previous test runner or background processes are stopped (`manage_task` or Task Manager). SQLite WAL mode is enabled automatically on startup.
