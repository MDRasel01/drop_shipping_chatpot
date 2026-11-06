# Layer 06 — Security & Reliability Engine: Specification & Audit Protocol

## 1. Multi-Tenant Security Architecture

Layer 06 enforces end-to-end security, data sovereignty, and reliability across the entire SaaS platform.

### 1.1 Defense-in-Depth Security Matrix
1. **Perimeter Layer (Cloudflare / Reverse Proxy):** SSL/TLS termination, DDoS mitigation, and global WAF.
2. **Gateway Layer (Port 8000 / FastAPI Middleware):**
   - JWT signature verification & expiry validation.
   - Origin verification for chat widget requests (`X-Widget-Key`).
   - Rate limiting: 60 requests/minute per IP, 1000 requests/minute per tenant.
3. **Application Layer (FastAPI Routers & Services):**
   - 6-Tier Role-Based Access Control (RBAC): `Platform Owner`, `Company Admin`, `Support Agent`, `Knowledge Manager`, `Billing Admin`, `Viewer`.
   - XML Boundary Prompt Isolation: Inputs to Google Gemini API are encapsulated within `<context>` and `<customer_question>` tags with prompt injection guardrails.
4. **Database Layer (PostgreSQL 16 + pgvector):**
   - Strict Row-Level Security (RLS) on all multi-tenant tables (`tenants`, `instructions`, `knowledge_chunks`, `conversations`, `messages`, `custom_questions`, `notifications`).
   - Mandatory session constraint: `SET LOCAL app.current_tenant_id = :tenant_id` executed at transaction start.

---

## 2. Automated Tenant Isolation Audit Protocol

To mathematically prove zero cross-tenant data leakage, the test suite executes an automated tenant isolation audit:
1. Initialize Tenant A (`tenant_alpha`) with private instruction: *"Secret Alpha Discount: 50%"*.
2. Initialize Tenant B (`tenant_beta`) with private instruction: *"Secret Beta Strategy: Project Pegasus"*.
3. Execute retrieval from Tenant A context:
   - Query: *"What is the secret strategy?"*
   - Expected: Empty result or 0 matching chunks. (Tenant B's data is completely invisible to Tenant A).
4. Direct SQL cross-tenant select without `SET LOCAL`:
   - Returns 0 rows due to default-deny RLS policy.

---

## 3. Reliability, Backup & Disaster Recovery

### 3.1 Database Backup Strategy
- **Continuous Archiving:** PostgreSQL Write-Ahead Logging (WAL) enabled.
- **Automated Snapshots:** Nightly `pg_dump` executed via cron/Celery worker, compressed with gzip, and uploaded to encrypted off-site cloud storage.
- **RTO (Recovery Time Objective):** < 15 minutes.
- **RPO (Recovery Point Objective):** < 5 minutes.

### 3.2 Redis Persistence
- **AOF (Append-Only File):** Configured with `appendfsync everysec` for durable message queue state and active conversation session tracking.
