# Layer 07 — Testing & Production Deployment Strategy

## 1. Multi-Stage Deployment Architecture

Layer 07 establishes the continuous integration, testing, containerization, and production deployment pipeline for the multi-tenant SaaS platform.

```
[ Git Push to Main ]
         |
         v
+----------------------------------------------------------------------------------------------------+
| CI/CD Pipeline (GitHub Actions / GitLab CI)                                                        |
| 1. Code Quality & Formatting: ruff check backend/, eslint frontend/                                |
| 2. Static Type Verification: mypy backend/, tsc --noEmit frontend/                                |
| 3. Automated Test Suite: pytest -v backend/tests (Unit + 12-Step Integration Test)                 |
| 4. Security Vulnerability Scan: trivy / bandit                                                      |
+----------------------------------------------------------------------------------------------------+
                                         |
                                         | (All Checks Green)
                                         v
+----------------------------------------------------------------------------------------------------+
| Container Build & Image Registry                                                                   |
| - Docker build: saas_backend:latest, saas_frontend:latest                                           |
| - Pushed to Private Container Registry (GitHub Packages / AWS ECR / GCP Artifact Registry)         |
+----------------------------------------------------------------------------------------------------+
                                         |
                                         v
+----------------------------------------------------------------------------------------------------+
| Production Infrastructure (Docker Compose / Managed Kubernetes / Cloud Run)                        |
| - Multi-AZ PostgreSQL 16 with pgvector                                                             |
| - High-Availability Redis 7 Cluster                                                                |
| - Stateless FastAPI Backend Pods (Autoscaling: 2 to 10 instances)                                  |
| - Next.js Frontend Edge CDN (Vercel / Cloudflare Pages / Standalone Node)                          |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Docker Compose Production Configuration

The local development and staging environments use the standardized `docker-compose.yml`:

```bash
# 1. Start all containers in background
docker compose up -d

# 2. Inspect container status & health
docker compose ps

# 3. View live application logs
docker compose logs -f backend
```

---

## 3. Production Health Probes & Monitoring

- **Liveness Probe:** `GET /health` -> Returns `HTTP 200 OK` when the FastAPI server is running.
- **Readiness Probe:** `GET /api/v1/health/aggregated` -> Verifies live connectivity to PostgreSQL database and Redis before directing customer traffic to the pod.
- **Graceful Shutdown:** Implements 30-second SIGTERM drain allowing in-flight Gemini API responses and active chat turns to complete.

