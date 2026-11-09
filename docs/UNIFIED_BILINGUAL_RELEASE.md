# Unified bilingual content release

The source revision `v2.4-bilingual` contains five bilingual background questions (including age and gender) and the knowledge forms. K0 has 11 items, K1/K3 seven, and K2 six, for all M/T × A/B forms. Age and gender each offer “Prefer not to say”; their values are not scored as knowledge. The bilingual experience questionnaire remains `survey-v3.0-review`, 19 items after T2 and K3. The new peer scale is `peer-review-v2.2-bilingual`, with the same Chinese text, score keys and 1–5 anchors as V2.1, plus English reading aids. English wording is a working translation, not independent evidence of measurement validity.

## Source files are not the active database instruments

A deployment can contain the latest JSON while continuing to serve older frozen instruments. Always run the content release after deploying code, using the existing environment and database:

```sh
python -m app.cli release-current-content --dry-run
python -m app.cli release-current-content --activate
python -m app.cli release-current-content --dry-run
```

The last command must report `changed: false`. The mode argument is mandatory. Dry run does not create versions or activate a protocol. Activation uses a transaction lock, compares normalized schemas and scoring keys by SHA-256, creates only changed instruments, reuses identical prior versions, and creates a new active protocol referencing the existing artifacts. Caller-side commit makes the release atomic. The content hash is independent of environment-specific UUIDs, so local and production can compare the same definitions.

Existing runs keep their protocol and question IDs. Existing answer keys, responses, assignments and frozen peer batch snapshots are not rewritten. New peer batches use V2.2; existing V2.1 batches retain V2.1. Research exports keep their raw values and content versions. No participant or image data is part of the source release.

## Deployment invariant

Use one Git commit for local code, GitHub main and the full tracked source package on JD Cloud. Preserve deployment credentials, pepper, model configuration, data volumes and private backups. The source supports local, JD Cloud OSS and Vercel Blob storage; study includes class 0–4 and beta includes class 0 only. On JD Cloud, set the existing Docker build argument `PIP_INDEX_URL` to the desired package mirror instead of maintaining a different Dockerfile.

Back up the database and running API/Caddy images, restore the dump into a disposable database, rehearse release and idempotence, and test with model stubs and isolated storage. Update API/Caddy only; do not recreate the database service. Keep a release receipt with commit, source manifest, image IDs, prior/new protocol IDs and content hash. After activation, compare both the code manifest and active content definition against the release source.

For rollback, start the backed-up images and transactionally deactivate the new protocol and reactivate the recorded prior protocol. Preserve versions and all runs created during the release; do not overwrite the live database with an old dump.

## Initial discrepancy resolved by this release

On November 9, 2026, local/GitHub were at `0bbc273`. Production source already contained bilingual instruments, but all 16 active K0–K3 forms lacked English; K0 contained only B-01–B-03 plus six knowledge items. The local preview database had bilingual K0–K3 but still used the seven-item survey V2.1. Both local preview backends shared one database. Server-only differences were older implementations of bootstrap/class configuration/file delivery and an untranslated original-download label; OSS and other cloud capabilities had already been merged into the repository. Preserve the repository's compatible superset and deploy it consistently.
