# rentlora-admin-service

> Back-office operations service for the Rentlora platform — platform statistics and user/role management.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-RDS-336791?logo=postgresql&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-IRSA-FF9900?logo=amazonaws&logoColor=white)

---

## Overview

`admin-service` is the leanest of the Rentlora backend services. It provides a read-heavy back-office view over the shared PostgreSQL database — surfacing platform-wide statistics, listing all users, and allowing administrators to promote or demote user roles. It has no message queues, no object storage, and no AI integrations; it is intentionally minimal.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/admin/stats` | Platform metrics — total users, properties, and bookings |
| `GET` | `/api/admin/users` | List all registered users |
| `PUT` | `/api/admin/users/{id}/role` | Promote or demote a user (`guest` / `host` / `admin`) |
| `GET` | `/api/admin/properties/all` | Full property list for content moderation |
| `GET` | `/healthz` | Liveness probe — returns `{"status":"ok"}` |
| `GET` | `/ready` | Readiness probe — checks database connectivity |

All non-health routes require a valid JWT with `admin` role, validated locally from the shared signing secret.

---

## AWS Resources

| Service | Purpose |
|---|---|
| **RDS (PostgreSQL)** | Read users, properties, and bookings; write role changes |
| **Secrets Manager** | DB password — fetched at startup via IRSA, never stored in code |
| **SSM Parameter Store** | DB endpoint, user, name — per-environment non-sensitive config |

This service does **not** use S3, SQS, SES, SNS, or Bedrock. Its IRSA role carries only the minimum Secrets Manager and SSM read grants.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Framework | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2 (async) + asyncpg |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | PyJWT (HS256) — validates tokens issued by user-service |
| AWS SDK | boto3 |
| Logging | python-json-logger (structured JSON) |
| Container | Docker (multi-stage, non-root) |

---

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL (or use the project-level `docker-compose.yml` in the `rentlora` repo)

### Run Locally

```bash
# From the rentlora repo root (starts all services including admin-service)
docker-compose up --build admin-service

# Or run standalone
cd rentlora-admin-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8004
```

With `ENV=local` the service skips all AWS lookups and uses its fallback defaults.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENV` | `local` | Environment name (`local`, `dev`, `prod`) |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region for SDK calls |
| `DATABASE_URL` | _(from SSM/fallback)_ | Async PostgreSQL connection string |

For local dev without AWS, you can set `DATABASE_URL` directly.

---

## Deployment

This service is deployed on **Amazon EKS** as part of the Rentlora platform.

- **Container image**: built by GitHub Actions, scanned by Trivy, pushed to ECR
- **Helm chart**: `rentlora-helm/charts/admin-service`
- **GitOps**: Argo CD reconciles chart changes automatically
- **Port**: `8004`
- **Replicas**: 2 minimum (HPA max 6, target 70% CPU)
- **AWS credentials**: IRSA — the pod's ServiceAccount is annotated with an IAM role ARN; no K8s Secrets needed

---

## Health Probes

| Probe | Path | Notes |
|---|---|---|
| Liveness | `GET /healthz` | Fast, dependency-free — no DB call |
| Readiness | `GET /ready` | Checks DB connectivity; returns HTTP 503 if unreachable |

---

## Project Context

This service is part of the Rentlora microservices platform:

| Repository | Role |
|---|---|
| [`rentlora`](../rentlora) | Application source — all services + frontend |
| [`rentlora-infra`](../rentlora-infra) | Terraform — AWS infrastructure |
| [`rentlora-helm`](../rentlora-helm) | Helm charts + Argo CD GitOps |
