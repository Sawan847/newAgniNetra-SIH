# Security status - local prototype

No security certification or compliance assessment has been completed. The application is intended for a controlled local SIH demonstration.

Implemented components include Pydantic input validation, SQLAlchemy queries, bcrypt password hashes, signed expiring JWTs and role dependencies for some authentication/user endpoints. Authentication is **not enforced across all data and mutation endpoints**, and the frontend does not yet provide a complete authenticated operator session. A development administrator is seeded only in development mode; it uses a known test credential in source and must never be reused for deployment.

`SECRET_KEY` and `POSTGRES_PASSWORD` are required by the local staging Compose template. That template binds the frontend only to loopback and does not publish database/backend ports. These controls do not make it production ready. The development Compose file is for local development only.

FIRMS request errors are redacted to keep MAP_KEY URLs out of ordinary logs. Credentials belong in uncommitted environment configuration; never include real keys in a submission archive. Password handling still needs a migration from bcrypt's input length limit to a validated password policy. There is no independently verified immutable audit log, rate limiting, backup recovery exercise, TLS deployment or penetration test.

Before a public deployment: complete endpoint authorization and identity handling, remove development defaults, add rate limits and request-size enforcement, configure HTTPS and secret management, review dependency advisories, and exercise database backup/restore. The in-process SSE feed is an invalidation stream, not durable event delivery or a cross-worker broker. The provided CI and unit tests are not a security audit.
