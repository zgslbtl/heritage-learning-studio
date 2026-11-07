# Experimental protocol

> **v1.5 notice (2026-11-06):** the current flow is T1/T2 + K0-K3 + survey + peer assessment + simulated work feed; G1-G4 now mean T1 A/B with fixed artifact order, and T2 is Standard AI for everyone. See [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md). This protocol page documents the earlier v1.0 two-round crossover baseline.


## Conditions and allocation

Formal classes are 1–4; class 0 is an uncapped internal-testing class available only outside
production. Each class has a capacity of 30 in the default configuration.

Each new email-created participant is assigned the next position in a shuffled block of four
groups. Every block contains G1, G2, G3 and G4 exactly once; the order is derived from the
server-side allocation pepper, class ID and block number. This gives exact balance within each
completed block and approximate 8/8/7/7 counts after 30 participants. Allocation is
serialized per class. Email addresses are unique and a re-login resumes the same participant
without consuming another position.

The student UI and API omit group and condition labels. Researcher records and exports retain
the group but not the email.

| Group | Round 1 | Round 2 |
|---|---|---|
| G1 | X + A | Y + B |
| G2 | Y + A | X + B |
| G3 | X + B | Y + A |
| G4 | Y + B | X + A |

The student API and UI omit group and condition labels. Researcher records and exports retain
the group but not the email.

## Round timing and outputs

- Server starts the 14-minute deadline only after the student clicks start.
- The countdown does not pause for network loss.
- The server rejects new writes after expiry and lazily moves the run forward when it next
  sees the run.
- Each round expects one title, one short-video script and one successful keyframe.
  Incomplete work may be submitted; completeness flags remain visible to researchers.
- The R1 assessment follows immediately and has no usable AI or round editing.

## A/B parity

Identical across A and B:

- evidence packs and immutable protocol;
- text and image models, model names, temperature/output limits and timeouts;
- three-column interface, script editor, evidence access and keyframe tool;
- 14-minute server timer;
- one successful keyframe, three total image attempts;
- base factual constraints and language behavior.

Only B receives:

- a persistent four-phase Observe → Explain → Create → Reflect narrative guide;
- one fixed server-authored prompt per phase;
- one optional fixed hint per phase;
- skip controls for each phase;
- B-only narrative-coaching context in the AI request.

The `hlsf-v1.1.1` phase design is:

1. **Observe — story entry point:** find a curiosity-raising detail and a story question.
2. **Explain — knowledge thread:** connect that question to reviewed evidence and decide how
   the audience should understand it.
3. **Create — complete story:** establish theme, perspective, key knowledge and an arc
   (curiosity → exploration → revealed cultural knowledge → return to the artifact), without
   reducing the work to a fact list. Historical Detective, Microhistorical Scenario and Process
   Reconstruction are optional inspirations only, and the prompt now includes a concrete
   example for each mode so students do not have to infer what the labels mean.
4. **Reflect — evaluation:** review the student's actual saved script, prioritise one
   improvement, and distinguish evidence from interpretation and imagination.

Normal B coaching replies are prompted to be 1–3 natural sentences with at most one question.
If the student explicitly asks for a script or revision, the AI may provide it directly and is
not artificially limited to three sentences. The student may accept, reject, or replace any
narrative suggestion and may use a mode of their own.

The B request context additionally carries a derived story seed (the earliest student message
in the round) and, during Create/Reflect, the latest saved script. These are derived at request
time from existing messages/script revisions; no new database field or migration is used.
Condition A keeps the unchanged free-form AI context and receives none of this narrative
guidance.

The fixed prompts and hints do not invoke an extra model or diagnostic agent. Any student
message in either condition invokes the same text model, evidence, tools, timer and quotas.
The guide UI is called “学习引导 / Learning Guide”; condition names are never shown.

`hlsf-v1.1.1` prompt text is in `backend/app/prompts/hlsf.py`. It must be frozen/reviewed before a
formal study and is included in audit documentation.

## AI factuality and failure behavior

The text system prompt restricts claims to supplied facts/evidence and requires uncertainty to
be stated. The image prompt asks for a grounded educational keyframe with no text overlay.
Provider errors are surfaced with an actionable message; no mock success path exists in the
application. Missing model configuration returns an explicit 503.

## Images

- A keyframe requires a saved non-empty script.
- Server builds and stores the image prompt.
- At most one image job may be queued/running per round.
- At most three total attempts per round; after one success, further generation is blocked.
- Jobs persist in PostgreSQL and survive restart. A job that was `running` when the server
  stopped is marked failed with a restart reason and must be manually retried.
- Result bytes are validated with Pillow, normalized to PNG, stored under the participant
  UUID/round path, and served only with ownership/researcher authorization.
