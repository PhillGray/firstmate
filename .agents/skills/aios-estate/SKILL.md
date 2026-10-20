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
The `tg:<chat>:<message>` request id is supplementary detail, read from the JSON `bin/fm-inbox.sh receipts` prints when you need the originating chat or message.
James accepts messages only from the captain's allow-listed Telegram user in a private chat, but it is still a remote relayed channel, so it carries no more authority than firstmate's existing remote channel: apply the escalation rule `fmx-respond` owns under "Public channel, so destructive work still escalates first".
A body that begins `[James/Telegram] [withheld: confidential]` carries no task text by design.
For it, ask the captain on this channel to brief the task directly, and dispatch it only under the confidential-intake rule below.
Answer every handled James note with `bin/fm-inbox.sh reply <id>` before `bin/fm-inbox.sh drain --ack <id>`, because the reply is the only text James relays back to Telegram.
Write the reply as captain-facing outcome language under section 9; one reply per note, so put the whole answer in it.

## Confidential intake

When a brief touches authentication, secrets, tokens, PII, payments, or database migrations, the captain's AIOS policy is to run the work on TEE-declared compute wherever that route is available.
Prefer a matched dispatch profile in `config/crew-dispatch.json` whose model is a TEE route, resolved under `quota-array-dispatch` like any other matched array.
If no TEE-routed candidate is eligible, neither drop the task nor dispatch it on a frontier harness on your own judgment: escalate once to the captain under section 9, name the sensitive trigger the brief touched, and wait for the captain's explicit harness choice for that task.
AIOS cannot verify TEE hardware attestation yet; never describe TEE routing to the captain as verified.

## Outside Judge evidence

An AIOS Outside Judge verdict (`outside-judge-verdict.json`) is supplementary evidence only.
It never replaces this project's selected delivery path, no-mistakes validation, or CI.
Cite it only when `node scripts/outside-judge.js verify <verdict.json>` in the AIOS checkout reports a valid signature, and only if the signing secret was not available to the worker that produced the change.
