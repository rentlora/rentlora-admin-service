# admin-service

Back-office / operations service — platform stats and user/role management.

## What it does
- `GET /api/admin/stats` — platform metrics (users, properties, bookings counts)
- `GET /api/admin/users` — list users
- `PUT /api/admin/users/{id}/role` — promote/demote (guest/host/admin)
- `GET /api/admin/properties/all` — all-properties view for moderation
- Liveness/readiness: `/healthz`, `/ready`

## AWS resources & why

| Resource | Used for | Why / benefit |
|---|---|---|
| **RDS (PostgreSQL)** | read users/properties/bookings; write role changes | It's a read-mostly view over the shared data, plus a few admin writes. |
| **Secrets Manager** | DB password | IRSA-read, no creds in code. |
| **SSM Parameter Store** | db config | Per-env config. |

**That's it** — no S3, SQS, Bedrock, SES. The leanest service: just DB + config. Its IRSA role
gets *only* the common Secrets/SSM grants (no extra statements).

## Improvements
- **Audit log** — admin actions (role changes, deletions) should be recorded (table or CloudWatch).
- **Fine-grained RBAC** — currently "admin" is all-or-nothing; consider scoped admin permissions.
- **Read replica** — heavy aggregate queries (`/stats`, `/properties/all`) could hit an RDS read
  replica instead of the primary as data grows.
- **Pagination** on `/users` and `/properties/all`.

## Unnecessary / cleanup
- Nothing over-provisioned — it's correctly minimal. The only architectural question is whether a
  service this small justifies its own deployment vs. being a module inside another service; keeping
  it separate is fine for clear ownership and independent scaling/permissions.
