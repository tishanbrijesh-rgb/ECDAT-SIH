# Local authentication setup and security changes

Data endpoints now require signed bearer sessions by default. Health/readiness and
login remain public. Reads are available to authenticated roles; modifications
require admin/security_analyst; audit logs require admin/auditor. Project-level
authorization and tenant isolation are not implemented.

Before login, provision these through the server environment or an untracked `.env`.
The FastAPI entrypoint loads the project-root `.env` for local development, and
Docker Compose reads it for interpolation:

- ECDAT_TOKEN_SECRET: a cryptographically random value of at least 32 characters.
- ECDAT_DB_PASSWORD (Compose): a random 64-character hexadecimal password. Published
  ports bind to localhost. Existing PostgreSQL volumes need explicit password
  rotation; changing this environment variable does not rotate existing accounts.
- ECDAT_USERS_JSON: JSON mapping lowercase usernames to objects with `role` and
  `password`. Roles: admin, security_analyst, auditor, viewer. Each password must be
  at least 16 characters and distinct from other account passwords and the secret.

Example structure only (replace the placeholder with a unique strong password):
`{"analyst":{"role":"security_analyst","password":"<unique password>"}}`

There are no working default credentials or signing keys. Missing/invalid settings
return 503 for session issuance/validation. Compose refuses empty settings. Generate
secrets privately using a password manager; never commit or paste them into chats.
Length checks cannot prove entropy: operators must choose randomly generated values.
Passwords currently reside in process configuration in plaintext; production needs
a proper identity provider or hashed credential store and secret management.

ECDAT_ALLOW_ROLE_HEADER defaults false. The explicit true setting retains an unsafe
legacy local-demo mode for compatibility tests ONLY: it permits impersonation and
anonymous analyst access. Do not enable it on shared or reachable deployments.
Compose fixes this setting to false.

The dashboard now signs in and sends bearer headers for reads, writes and downloads.
Tokens live only in JavaScript memory; reload/sign-out clears them. Sessions expire
after one hour. Expiry or an authenticated 401 returns the UI to login with an
explanation; background-tab timers may be delayed by the browser. Viewer/auditor
write controls are disabled and write-action links hidden. Logout does not revoke an already copied
token server-side. Rotating the signing secret invalidates existing sessions.

Raw snippets, string arguments and requirement lines are removed from scanner/API
evidence. Structured line/algorithm metadata is retained. Historical evidence lists
are sanitized on API reads but old database contents are NOT purged. Redaction is
conservative, not a guarantee that all metadata is secret-free. Review retention and
legacy databases separately; no historical records were deleted by this change.

Input fixes: typed scan paths return 422 instead of crashing; non-ASCII passwords
are compared as UTF-8 bytes; malformed key sizes are retained as conflicts with an
unset key-size field. No dependency versions were changed.

Remaining production blockers include TLS deployment, login throttling, server-side
revocation, robust scan isolation/resource limits, full secret detection, and an
independent security review. PostgreSQL's development Compose credentials/network
exposure also require separate hardening. This patch is not production certification.
