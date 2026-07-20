# Docker Deployment Guide — ChemPlant Dynamics

> A step-by-step guide to build, run, and maintain the app with Docker and Docker Compose.

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Docker Desktop / Docker Engine | 24+ | `docker --version` |
| Docker Compose (bundled with Docker Desktop) | 2.20+ | `docker compose version` |
| Git | any | `git --version` |

---

## 1 — Clone the repository

```bash
git clone <your-repo-url>
cd chemplant-dynamics
```

---

## 2 — Create the `.env` file

The app needs a secret key for NiceGUI session storage.
**Never commit `.env` to git** — it's already in `.gitignore`.

```bash
# Copy the template
cp .env.example .env
```

Then open `.env` and replace the placeholder with a real secret:

```bash
# Generate a cryptographically strong secret (run in your terminal)
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output into `.env`:

```dotenv
STORAGE_SECRET=<paste-your-generated-secret-here>
```

> **Important:** Using the default placeholder value in production is a security risk.
> Any real deployment must use a unique, randomly-generated secret.

---

## 3 — Build the Docker image

```bash
docker compose build
```

This triggers the **multi-stage build** defined in `Dockerfile`:

```
Stage 1 — builder   (ghcr.io/astral-sh/uv:python3.13-bookworm-slim)
  └─ Installs Python dependencies into .venv using uv

Stage 2 — runtime   (python:3.13-slim)
  └─ Copies only .venv + app source → smaller final image
```

> **Tip:** Layer caching is optimised — if only source code changes (not `pyproject.toml` / `uv.lock`),
> Docker skips the dependency install step and the build is nearly instant.

---

## 4 — Run the app

### Development (foreground, see logs)

```bash
docker compose up
```

Open **http://localhost:8080** in your browser.

### Production (detached / background)

```bash
docker compose up -d
```

Check it's running:

```bash
docker compose ps
```

Expected output:

```
NAME               STATUS          PORTS
cpdynamics-app    Up (healthy)    0.0.0.0:8080->8080/tcp
```

---

## 5 — Verify the health check

The app exposes a `/health` endpoint used by Docker's built-in health probe.

```bash
# Should return: ok
curl http://localhost:8080/health
```

Or check the health status directly:

```bash
docker inspect --format='{{.State.Health.Status}}' cpdynamics-app
# → healthy
```

> The container will show `starting` for ~30 seconds while the app boots,
> then transition to `healthy`. If it stays `unhealthy`, check the logs (step 6).

---

## 6 — View logs

```bash
# Follow live logs
docker compose logs -f

# Last 100 lines only
docker compose logs --tail=100
```

Logs are also persisted by Docker's JSON file driver and auto-rotated
(max 10 MB × 3 files) as configured in `docker-compose.yml`.

---

## 7 — Stop the app

```bash
# Stop containers (keeps volumes)
docker compose down

# Stop AND remove volumes (WARNING: deletes persistent data)
docker compose down -v
```

---

## 8 — Update the app (redeploy)

```bash
git pull                    # get latest code
docker compose build        # rebuild image
docker compose up -d        # restart with new image
```

Or in one command:

```bash
docker compose up -d --build
```

---

## 9 — Persistent data

Two named Docker volumes keep data across container restarts:

| Volume | Mounted at | Purpose |
|--------|-----------|---------|
| `cpdynamics-data` | `/app/data` | Application data files |
| `cpdynamics-logs` | `/app/logs` | Application log files |

Inspect a volume:

```bash
docker volume inspect chemplant-dynamics_cpdynamics-data
```

> **Warning:** Running `docker compose down -v` will permanently delete these volumes.
> Back up important data before doing so.

---

## 10 — Useful Docker commands

```bash
# Open a shell inside the running container (for debugging)
docker compose exec cpdynamics-app bash

# Rebuild from scratch (no cache)
docker compose build --no-cache

# Remove dangling images to free disk space
docker image prune

# Check resource usage (CPU, memory)
docker stats cpdynamics-app
```

---

## Code quality — linting, formatting & type checking

The project uses **Ruff** (linting + formatting) and **Pyright** (static type checking),
configured in [`pyproject.toml`](file:///c:/Research%20Project/chemplant-dynamics/pyproject.toml).
**Pre-commit hooks** run both automatically before every `git commit`.

### One-time setup

```bash
# Install dev dependencies (ruff, pyright, pre-commit)
uv sync --group dev

# Install the git pre-commit hook
uv run pre-commit install
```

### Run manually

```bash
# Lint: check for errors
uv run ruff check .

# Lint: auto-fix all fixable issues
uv run ruff check --fix .

# Format: apply code style (like Black)
uv run ruff format .

# Type check
uv run pyright
```

### What each tool does

| Tool | Role | Config key |
|------|------|-----------|
| `ruff check` | Linting — catches bugs, bad imports, deprecated patterns | `[tool.ruff.lint]` |
| `ruff format` | Formatting — consistent code style (replaces Black) | `[tool.ruff.format]` |
| `pyright` | Static type checking — catches type mismatches before runtime | `[tool.pyright]` |
| `pre-commit` | Runs ruff automatically on staged files before each commit | `.pre-commit-config.yaml` |

> Pre-commit hooks only run on **staged files**. To run against the whole codebase:
> ```bash
> uv run pre-commit run --all-files
> ```

---

## Troubleshooting

### Container exits immediately

```bash
docker compose logs cpdynamics-app
```

Common causes:

- **Missing `.env`** — the file doesn't exist. Run `cp .env.example .env` and fill in values.
- **Port conflict** — port 8080 is already in use. Change the host port in `docker-compose.yml`:
  ```yaml
  ports:
    - "9000:8080"   # host:container
  ```

### Health check stays `unhealthy`

```bash
# Test the endpoint manually from inside the container
docker compose exec cpdynamics-app \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health').read())"
```

If it fails, the app hasn't started correctly — check logs for Python exceptions.

### Permission errors on volumes

```bash
# Fix ownership on the mounted directories
docker compose exec cpdynamics-app chown -R 1000:1000 /app/data /app/logs
```

---

## Azure Container Registry (ACR) & Container Apps Deployment

To deploy this application to Azure, the recommended approach is to push your Docker image to **Azure Container Registry (ACR)** and then host it on **Azure Container Apps (ACA)**.

### 1 — Push the image to ACR

You can build and push your image directly using standard Docker commands. Replace `<username>` and `<password>` with your ACR credentials.

```bash
# 1. Log in to your ACR
docker login cpdynamicsacr.azurecr.io -u <username> -p <password>

# 2. Build and tag the image
docker build -t cpdynamicsacr.azurecr.io/cpdynamics-app:latest .

# 3. Push the image to ACR
docker push cpdynamicsacr.azurecr.io/cpdynamics-app:latest
```

### 2 — Deploy to Azure Container Apps (ACA)

When configuring your Container App in the Azure Portal to use this image:

1. **Networking / Ingress:** Enable ingress and set the target port to `8080`. You do not need the `ports` mapping from `docker-compose.yml` since ACA ingress handles external traffic.
2. **Environment Variables:** Set `STORAGE_SECRET` as a secret in your ACA environment variables to ensure it is secure.
3. **Persistent Storage:** If you want to persist the `/app/data` and `/app/logs` volumes, mount an **Azure Files** share to your Container App instead of using Docker's local named volumes.
