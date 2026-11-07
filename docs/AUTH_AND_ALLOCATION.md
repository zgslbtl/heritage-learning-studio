# Email login and per-class allocation

> **v1.5 notice (2026-11-06):** class/email/login/allocation are unchanged, but G1-G4 now mean G1/G2 = T1 A, G3/G4 = T1 B; T2 is Standard AI. See [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md).


Updated: 2026-11-05

## Student login

The student entry page now asks for a PolyU email address and a class. The server accepts any
non-empty, lower-normalized value containing the substring `polyu` (case-insensitive). This is
a **demo access gate, not real identity verification**: it does not prove that the person owns
the address, and anyone who types a qualifying address can enter.

Operational safeguards implemented in the application:

- email is normalized (trimmed and lower-cased) and stored as plaintext in PostgreSQL, as
  requested for internal use;
- email is unique: one email maps to one participant record;
- re-entering the same email and class resumes the same participant/run;
- entering an existing email with a different class is rejected (`email_class_mismatch`);
- the entry page states that the email is stored for login and internal use;
- email is shown only in the authenticated researcher console and is not included in the
  research ZIP export;
- the class 0 test class is available only outside production and is hidden from the
  production frontend build;
- production rejects class 0 server-side.

Because addresses are not verified, a person can create multiple accounts with different
qualifying addresses. This is intentionally left to manual researcher control, as agreed.

## Assignment within a class

Formal classes are 1–4. Class 0 is reserved for internal testing and has no participant cap.
The formal capacity is `PARTICIPANTS_PER_CLASS` (default 30) per class.

Each new email-created participant is assigned the next position in a **shuffled block of four
groups**. A block contains G1, G2, G3 and G4 exactly once. The order of each block is derived
from:

- the server-side `ANON_CODE_PEPPER`;
- the class ID;
- the block number.

The result is stable for all four positions in the block, is random-looking, and cannot be
predicted without the pepper. The allocation is serialized with a row lock on the class row,
so concurrent registrations cannot receive the same position. Re-login does not consume a
position.

The live local check produced the first block `G2, G3, G4, G1`; every block in the automated
test contains all four groups. The class-level counts become approximately 8/8/7/7 after 30
formal participants, depending on where the last block stops.

## Classes and test data

- Classes 1–4: formal classes.
- Class 0: internal testing, available only outside production.
- Existing engineering/test participants were migrated to class 0 on 2026-11-05.
- The legacy access-code API remains available for internal tooling and old test records, but
  the student UI no longer accepts codes. In email mode the protected code CSV download is
  disabled.

## Database changes

Migration `0002_email_login` adds nullable `participants.email` with a unique constraint,
indexes it, and makes the legacy access-code columns nullable. Existing participants remain
valid; email-created participants have no access-code HMAC/last-4.

## Production notes

- Set `AUTH_MODE=email`.
- Deploy a fresh production database. Do not reuse the migrated local test database.
- The production Vite build hides class 0; the backend also rejects class 0.
- Formal classes start at 1.
- Email is personal data: update ethics/consent, retention/deletion and access-control
  documentation before real collection.
- The export remains pseudonymous by participant UUID; the internal admin view shows the
  email. Treat backups and admin sessions as containing personal data.
