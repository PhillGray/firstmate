---
name: aios-estate
description: >-
  Agent-only bridge to the captain's AIOS estate layer (Telegram "James", confidential compute routing, Outside Judge).
  Use on a captain inbox note whose body begins "[James/Telegram] " before answering or acknowledging it.
  Also use at crewmate or scout intake when the brief touches authentication, secrets, tokens, PII, payments, or database migrations, before choosing a dispatch profile.
  Also use before citing an AIOS Outside Judge certificate as evidence on a PR.
  Loaded only in homes where the captain runs AIOS alongside firstmate.
user-invocable: false
metadata:
  internal: true
---

# aios-estate

AIOS is a separate repository the captain runs next to this home.
It owns a Telegram channel, compute-confidentiality triage, and an outside verification judge.
It never spawns, supervises, or lands crew work; that stays with firstmate.
Nothing here relaxes a hard rule, the merge authority in section 7, or the captain-instruction precedence rule.

## Telegram notes from James

James delivers a captain message through `bin/fm-inbox.sh note --request-id tg:<chat>:<message> --json -`, and begins every note body with the literal prefix `[James/Telegram] `.
That prefix is the trigger: it reaches you in the `check: captain inbox note <id> - <summary>` wake and again in `bin/fm-inbox.sh drain`, so you can tell a James note from any other note on the normal inbox path.
James accepts messages only from the captain's allow-listed Telegram user in a private chat, but it is still a remote relayed channel, so a note carries reversible authority only.
Anything destructive, irreversible, or security-sensitive - merges, discards, credential and permission changes included - is never executed straight from a James note: flag it to the captain in their own session and act only on the captain's word given there.
Normal reversible work proceeds from the note itself - filing backlog, a scout investigation, gated code changes, dispatching a crewmate.
A body that begins `[James/Telegram] [withheld: confidential]` carries no task text by design; ask the captain to brief the task in their own session, and dispatch it only under the confidential-intake rule below.
A note you escalated or asked back that way is still a handled note, and its reply says only that it has been flagged for the captain's own session, nothing more.
Answer every handled James note with `bin/fm-inbox.sh reply <id>` before `bin/fm-inbox.sh drain --ack <id>`, because the reply is the only text James relays back to Telegram.
Write the reply as captain-facing outcome language under section 9; one reply per note, so put the whole answer in it.

## Confidential intake

When a brief touches authentication, secrets, tokens, PII, payments, or database migrations, the captain's AIOS policy is to run the work on TEE-declared compute wherever that route is available.
A TEE route means exactly one thing here: a dispatch profile in `config/crew-dispatch.json` whose model id ends in `-TEE`, the suffix Chutes TEE models carry.
That is the profile's own declaration and not hardware attestation anyone has checked, so never describe TEE routing to the captain as verified.
Prefer such a profile when one matches the brief, resolved under `quota-array-dispatch` like any other matched array.
If no profile meets that test, neither drop the task nor dispatch it on a frontier harness on your own judgment: escalate once to the captain under section 9, name the sensitive trigger the brief touched, and wait for the captain's explicit harness choice for that task.

## Outside Judge evidence

An AIOS Outside Judge verdict (`outside-judge-verdict.json`) is supplementary evidence only.
It never replaces this project's selected delivery path, no-mistakes validation, or CI.
Cite it only when `node scripts/outside-judge.js verify <verdict.json>` in the AIOS checkout reports a valid signature, and only if the signing secret was not available to the worker that produced the change.
