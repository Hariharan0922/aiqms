# Production Deployment Guide – AiDocMaker

This guide provides operational specifications, containerization procedures, and security best practices for deploying **AiDocMaker** in production and staging environments.

---

## 1. Production Architecture

```
Internet / Corporate Intranet
              │
              ▼
Reverse Proxy (NGINX / Traefik / AWS ALB)
  - TLS Termination (HTTPS / Port 443)
  - Strict Rate Limiting
  - Security Headers (HSTS, CSP, X-Frame-Options)
              │
       ┌──────┴──────┐
       ▼             ▼
Vite Static Build   FastAPI Backend (Gunicorn + Uvicorn Workers)
(Port 80/443)       (Port 8000)
                     │
            ┌────────┴────────┐
            ▼                 ▼
   PostgreSQL 16 Database   NVIDIA NIM Hosted API (HTTPS Outbound)
   (Persistent Storage)     (integrate.api.nvidia.com)
```

---

## 2. Docker & Container Deployment

### 2.1. Containerized Stack

The project root includes `docker-compose.yml`. Update it with production environment variables:

```yaml
version: '3.8'

services:
  api:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    environment:
      - APP_ENV=production
      - DEV_AUTH_ENABLED=false
      - APP_SECRET=${APP_SECRET}
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - NVIDIA_API_KEY=${NVIDIA_API_KEY}
      - NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
      - NVIDIA_MODEL=poolside/laguna-xs-2.1
      - NVIDIA_TIMEOUT=120
      - NVIDIA_MAX_RETRIES=2
    depends_on:
      - db
    ports:
      - "8000:8000"
    restart: always

  web:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - api
    restart: always

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-aiqms}
      POSTGRES_USER: ${POSTGRES_USER:-aiqms_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: always

volumes:
  pgdata:
```

### 2.2. Launching Stack

```bash
docker compose up -d --build
```

---

## 3. Production Security Checklist

- [ ] **Disable Development Authentication:** Set `DEV_AUTH_ENABLED=false`. Integrate an enterprise OIDC/OAuth2 provider (Okta, Azure AD, Keycloak) to enforce real identity and role assignments.
- [ ] **Secret Isolation:** Store `NVIDIA_API_KEY` in AWS Secrets Manager, HashiCorp Vault, or encrypted container environment secrets. Never hardcode keys in Dockerfiles or source repositories.
- [ ] **Outbound Firewall Rule:** Ensure the host or container network allows outbound HTTPS connections to `integrate.api.nvidia.com:443`.
- [ ] **Database Backup:** Schedule daily automated WAL archiving and backups for the PostgreSQL database.
- [ ] **Storage Persistence:** Mount durable network storage (AWS EBS / EFS / Azure Managed Disk) to `./data/evidence` and `./data/exports`.
- [ ] **HTTPS Enforced:** All browser traffic must terminate on TLS 1.3 with HSTS enabled.
