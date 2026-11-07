# Research readiness checklist

> **v1.5 notice (2026-11-06):** readiness now expects K0, K1, K2, K3 and survey instruments plus the T1/T2 product-design flow. See [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md).


This MVP is an engineering shell. It must not be presented as a validated educational
intervention or used for formal data collection until all of the following are completed.

## Content and measurement

- [ ] Two Evidence Packs authored and academically reviewed, including provenance, rights,
      uncertainty and translation decisions.
- [ ] Five instruments finalized: pre-test, R1 assessment, post-test, transfer task and
      questionnaire.
- [ ] Scoring rubrics and inter-rater procedures defined outside the app. The app stores raw
      answers and intentionally does not score.
- [ ] HLSF `hlsf-v1.1.1` prompts reviewed for fidelity to the intended scaffold.
- [ ] Pilot/wording/cognitive interviews completed.

## Ethics and data governance

- [ ] Ethics/IRB approval.
- [ ] Approved participant information and consent process. This MVP has no consent capture
      page, so do not open it to participants until that is added or an approved external
      consent process is in place.
- [ ] Data retention period and deletion procedure defined and testable.
- [ ] Data protection impact assessment covering stored PolyU emails, class/group assignment,
      free-text responses and exported media.
- [ ] Researcher access list and incident response plan.
- [ ] External AI provider data-processing terms, data residency/cross-border transfer, model
      training use and cost limits reviewed.

## Operations

- [ ] Production host, DNS, TLS certificate issuance and firewall validated.
- [ ] Real text and image model calls tested with approved credentials; no stub results used
      in research claims.
- [ ] Initiate and test off-host encrypted backups and a destructive restore drill.
- [ ] Configure monitoring for provider outages, disk exhaustion and failed jobs.
- [ ] Confirm 30-concurrent and full-cohort load behavior under the real provider's rate
      limits.
- [ ] Independent security review and accessibility/usability review.
- [ ] Freeze the protocol before opening email login; confirm no runs exist when activating.

## Participant handling

- [ ] Define how class 0 internal-test accounts are kept out of the formal analysis; use classes 1–4 only for formal participants.
- [ ] On shared devices, sign out/clear the previous session and local drafts before the next
      participant enters.
- [ ] Provide a researcher contact for access issues.
- [ ] Define what happens to incomplete participants before analysis.
