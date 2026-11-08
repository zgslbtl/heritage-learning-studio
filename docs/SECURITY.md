# Security notes

## Identity and access

- The current student gate accepts any value containing `polyu`. This is **not**
  authentication and does not verify ownership. Anyone who types a qualifying value can enter
  and, if the email is new, create a participant record. This is accepted temporarily for
  testing; the researcher must monitor accounts manually.
- Email addresses are stored as plaintext by explicit requirement. They are visible to the
  authenticated researcher console and excluded from the research export. Database backups,
  admin sessions and the database volume must be treated as containing personal data.
- Legacy access codes use 8 symbols from a 32-symbol unambiguous alphabet (about 40 bits);
  they are retained for internal tooling and old test records but are no longer the student
  login UI.
  They are stored as HMAC-SHA256 with a server pepper. Plaintext exists only in the protected
  cohort CSV and is never logged or exported in research data.
- Access attempts are limited to 200 per IP per 10 minutes (enough for a shared class NAT
  address); this still makes enumeration infeasible against the code space.
- Student and researcher sessions are opaque random tokens; the database stores only token
  hashes. Cookies are HttpOnly, SameSite=Lax, and Secure in production.
- Researcher login is password based and rate limited. Production startup refuses a missing
  or short admin password and pepper.
- Sessions can be revoked on logout. Expiry is server-checked.
- New class-entry tokens use a versioned, domain-separated HMAC-SHA256 of the
  link UUID and class ID with the existing server `ANON_CODE_PEPPER`. The database
  stores only the token hash and derivation version; authenticated administrators
  can recover active URLs. Public resolution exposes class metadata only. Keep
  the pepper stable across restarts and redeployments, as already required for
  allocation and legacy codes. Random legacy links remain valid but require
  regeneration to become recoverable; revoked links have no URL in the admin list.

## Isolation

- Every student endpoint derives the participant from the session; there are no
  participant-ID path parameters for student reads/writes.
- Image jobs and files use ownership joins. Evidence images are only served to participants
  whose run includes that artifact version, or to a researcher.
- All researcher endpoints require an admin session.
- Postgres, FastAPI and `/data` are not published by Compose. Caddy only proxies `/api/*` and
  serves built static assets.

## Input and transport

- Pydantic validates request shapes and lengths; instrument schemas and answers are validated
  server-side.
- Artifact uploads are size-limited and decoded/verified with Pillow; generated images are
  size/type checked before atomic storage.
- Non-GET browser requests with an `Origin` are checked against configured public origins.
  CORS is not enabled.
- Caddy applies CSP, HSTS, frame denial, MIME sniffing protection, permissions policy and a
  request-size limit, and terminates TLS.
- API keys remain in the API container environment. Test stubs are never a production code
  path and no demo content is permitted in production readiness.

## Data protection

- Research exports are researcher-authenticated and contain no access codes, token hashes or
  secrets.
- CSV cells starting with formula characters are prefixed to reduce spreadsheet injection
  risk; the source value remains available in JSON fields.
- Backups contain identifiable research records (pseudonymous study IDs) and must be
  encrypted, access-controlled and stored off-host.
- Logs omit request bodies and API keys. AI request records are admin/export-only and contain
  the prompts and visible conversation, not authorization headers.

## Known limits

- In-process login limiting assumes the single API process used by this MVP.
- Rate limiting by IP is intentionally generous for classroom NAT; code entropy and admin
  password policies are the primary defenses.
- Formal security review, consent, retention/deletion automation and provider data-processing
  review are outside this MVP and mandatory before real data collection.
