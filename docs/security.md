# Security review

Checklist-style review of how PulseDesk handles the standard risk areas for a backend
service. Where something is explicitly out of scope for this project, that's stated as
a deliberate decision, not an oversight.

## Authentication & authorization

- **Passwords**: hashed with bcrypt (`passlib[bcrypt]`) via `app/core/security.py`;
  never stored or logged in plaintext. Verified by
  `tests/unit/test_auth_service.py::test_password_is_hashed_not_stored_plain`.
- **Tokens**: stateless JWTs, HS256, with distinct `access` (15 min) and `refresh`
  (7 day) types encoded in the `type` claim so a refresh token can't be replayed as an
  access token and vice versa (`test_refresh_token_rejected_as_access_token`,
  `test_refresh_rejects_access_token_used_as_refresh`). Tampered and expired tokens are
  rejected (`test_tampered_token_rejected`, `test_expired_token_rejected`).
- **Authorization**: every route that needs a role declares it via
  `require_role(...)` (`app/api/deps.py`), resolved through FastAPI's dependency
  injection -- deny-by-default, since a route with no `require_role`/`get_current_user`
  dependency simply has no access to `request.user` at all. RBAC-scoped visibility
  (customers see only their own tickets; agents see tickets unassigned or assigned to
  them; admins see everything) is enforced in `TicketService`, not just at the route
  layer, so it can't be bypassed by calling the service directly.

## Input handling

- All request bodies are Pydantic models with explicit types/length constraints
  (`app/schemas/`) -- malformed input is rejected before it reaches business logic.
- All database queries go through SQLAlchemy's parameterized query builder; there is no
  raw string-interpolated SQL anywhere in the codebase (the one hand-written SQL string,
  the HNSW/ivfflat index DDL in the migrations, takes no user input).
- **File upload**: not implemented in v1. There is no endpoint that accepts arbitrary
  file content, so the usual upload-based attack surface (path traversal, content-type
  spoofing, storage exhaustion) doesn't exist here.

## Prompt injection (the RAG-specific risk)

Ticket text is user-controlled and flows into an LLM prompt (`build_grounded_prompt` in
`app/services/llm/base.py`, shared by every `LLMProvider` implementation). It is
treated as **untrusted data**, not as instructions:

- The ticket text is wrapped in an explicit `<ticket>...</ticket>` delimiter inside the
  prompt template, with an instruction that its contents are data to summarize/ground a
  reply from, never commands to follow.
- The model (real or mock) is never given tool/action access from ticket content --
  it can only produce a draft reply string that a human agent reviews before it reaches
  a customer.
- Verified by `test_grounded_prompt_treats_ticket_text_as_untrusted_data`.

## Abuse prevention

- **Rate limiting**: Redis token-bucket (`app/core/rate_limit.py`) on ticket creation,
  keyed per authenticated user, so one account can't starve others.
- **Idempotency**: `Idempotency-Key` + a unique DB constraint prevent duplicate ticket
  creation from client retries (`app/services/ticket_service.py`,
  `test_duplicate_idempotency_key_*`).

## Secrets

- `.env` (and any `.env.*` except `.env.example`) is git-ignored; nothing in this repo
  contains a real secret. `docker-compose.yml` passes secrets via `env_file: .env`,
  never bakes them into the image.
- Logs are structured JSON (`app/core/logging.py`) built from an explicit allowlist of
  fields (method, path, status, latency, request ID) -- there is no code path that logs
  a full request body or header set, so passwords/tokens can't leak into logs by
  accident.

## Dependency scanning

- CI runs `pip-audit` against `requirements.txt` and Trivy against the built image
  (`.github/workflows/ci.yml`). Trivy is currently report-only (`exit-code: "0"`) for
  this portfolio project rather than blocking on every base-image CVE, since patching
  the Debian base image is a `docker pull`+rebuild away and isn't meaningful signal
  about the application code itself; pip-audit blocks the build (default exit code) since
  a vulnerable direct dependency is directly actionable (bump the pin).

## Explicitly out of scope for v1

- Multi-tenancy beyond the customer/agent/admin role model.
- File uploads (see above).
- A CDN/WAF in front of the API -- irrelevant at demo scale.
