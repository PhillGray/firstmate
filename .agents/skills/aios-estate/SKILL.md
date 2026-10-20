---
name: aios-estate
description: >-
  Agent-only bridge to the captain's AIOS estate layer (Telegram "James", confidential compute routing, Outside Judge, Ditto memory).
  Use on a captain inbox note whose request_id starts with "tg:" before answering or acknowledging it.
  Also use at crewmate or scout intake when the brief touches authentication, secrets, tokens, PII, payments, or database migrations, before choosing a dispatch profile.
  Also use before citing an AIOS Outside Judge certificate as evidence on a PR.
  Loaded only in homes where the captain runs AIOS alongside firstmate.
user-invocable: false
metadata:
  internal: true
---

# aios-estate

AIOS is a separate repository the captain runs next to this home.
It owns a Telegram channel, compute-confidentiality triage, an outside verification judge, and a memory store.
It never spawns, supervises, or lands crew work; that stays with firstmate.
Nothing here relaxes a hard rule, the merge authority in section 7, or the captain-instruction precedence rule.

## Telegram notes from James

James delivers a captain message through `bin/fm-inbox.sh note --request-id tg:<chat>:<message> --json -`.
James accepts messages only from the captain's allow-listed Telegram user in a private chat, so treat the note as a captain instruction exactly as written.
A note body that begins `[withheld: confidential]` carries no task text by design.
For it, ask the captain on this channel to brief the task directly, and dispatch it only under the confidential-intake rule below.
Answer every handled James note with `bin/fm-inbox.sh reply <id>` before `bin/fm-inbox.sh drain --ack <id>`, because the reply is the only text James relays back to Telegram.
Write the reply as captain-facing outcome language under section 9; one reply per note, so put the whole answer in it.

## Confidential intake

When a brief touches authentication, secrets, tokens, PII, payments, or database migrations, the captain's AIOS policy is that the work runs on TEE-declared compute or not at all.
Prefer a matched dispatch profile whose model is a TEE route, such as a Chutes `-TEE` model through the `pi` harness in `config/crew-dispatch.json`.
If no TEE-routed candidate is eligible under `quota-array-dispatch`, report the task as blocked on confidential compute rather than dispatching it on a frontier harness.
The captain's current explicit instruction to use a specific harness for that task overrides this preference within its exact scope.
AIOS cannot verify TEE hardware attestation yet; never describe TEE routing to the captain as verified.

## Outside Judge evidence

An AIOS Outside Judge verdict (`outside-judge-verdict.json`) is supplementary evidence only.
It never replaces this project's selected delivery path, no-mistakes validation, or CI.
Cite it only when `node scripts/outside-judge.js verify <verdict.json>` in the AIOS checkout reports a valid signature, and only if the signing secret was not available to the worker that produced the change.

## Ditto memory

Ditto is reachable through the AIOS MCP server's `aios_query_memory` tool.
It becomes an authoritative memory tier only if the captain declares it in this home's `Memory layering` section (`docs/configuration.md` owns the schema); without that declaration, local `data/` files remain the only memory owners.
