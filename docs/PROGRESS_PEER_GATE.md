# Progress-based peer opening

Formal classes 1–4 use `progress-10-60-90-v1` only while their gate is still
collecting. Class 0 and already-open historical batches retain their behavior.

The tenth distinct round-1 start establishes an immutable class clock, using
the actual tenth timestamp even for starts before deployment. The active
denominator includes entered runs except administrator-stopped runs. Readiness
requires valid, finished works in both rounds and submitted K3 and survey
responses. Everyone ready opens immediately (including classes below ten);
otherwise elapsed time must reach 3600 seconds and `ready * 10 >= active * 9`.
Zero active students never opens a formal gate.

Opening freezes active member run IDs, ready reviewer IDs and exact work
revision IDs. Main assignments keep the existing two-round equal allocation,
up to six works per round without self or cross-class reviews. Existing class
entry links remain unchanged; existing accounts resume after opening, while
new accounts follow the existing closed-class restriction.

Late, non-stopped members must finish their own tasks before receiving an
idempotent supplemental snapshot of up to six frozen works per round. Lower
supplemental assignment counts take priority, then condition balance and a
stable ordering. Main assignments are never replaced or extended. Late works
appear in the dynamic two-round gallery, but are not added to the review pool.
`allocation_kind` is `main` or `supplemental`; legacy rows default to `main`.
`peer_work_scores.csv`, analysis rows and researcher main summaries exclude
supplemental ratings. Raw assignment/rating exports identify allocation kind;
`peer_supplemental_work_scores.csv` reports supplemental aggregates separately.
Received-main-rating equality is an assignment target, not a guarantee that
every assigned reviewer ultimately submits.

Authenticated administrators use `POST /api/admin/participants/{id}/stop` or
`/restore`, supplying a nonblank `reason` (up to 1000 characters). Only unfinished
formal participants can be stopped before the gate opens. Stopping retains
the original stage, answers and media and excludes the run from readiness
calculations. Restoring before opening retains original round deadlines.
If a stop immediately opens the gate it can no longer be undone. A zero-work
review is accepted only when there genuinely is no other frozen author, with
the reason recorded in the snapshot. Polling never counts as an actual operation;
old operation timestamps are unknown rather than inferred from polling.

Enrollment, opening, stop/restore and student request authorization use a
class-first transaction lock. Pending requests accepted before a stop may
finish their existing provider response; subsequent student task requests are
blocked. Stops do not delete or cancel previously accepted media jobs.
Administrative events retain the authenticated admin session ID, reason,
original stage and before/after counts. Exports include stops and frozen gate
metadata. Student views do not expose other students' membership identifiers.

Deployment requires additive migration `0018_progress_peer_gate`. Back up the
database/source/images, rehearse migration and old-image compatibility on a
restore, deploy the same commit to API and frontend, and leave database/data
volumes intact. An operational rollback retains the additive schema, snapshots,
ratings and answers; never restore an old database over newer submissions.
The old image does not enforce the new stop policy: use it only as an emergency
compatibility fallback with the researcher informed; do not downgrade/drop the
schema or claim stopped-account enforcement is retained under old code.
