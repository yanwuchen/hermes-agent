---
title: QQ trusted intake guard
---

This user fork targets the Pi-compatible commit
`f97608f178d1ffeca59860195ab7da295f7c8e5f`. Its PR base is
`finance/pi-baseline-f97608f`, not the newer upstream/fork main. Review and
merge on that compatibility branch; do not replace a newer main with this tree.

QQ remains connected to Hermes. A single trusted external consumer may handle
restricted input before the adapter's normal message handlers, body logs,
attachment/STT/quote ingestion, adapter busy queue, runner busy dispatch, ordinary
plugins, observers, model and history. This is an operator-installed code boundary,
not a plugin observation broadcast or a model-controlled callback.

The optional `platforms.qq.extra.intake_guard` configuration selects a
`module:factory`. The synchronous factory receives `(adapter, settings)` and
returns an async callable `(event_type, raw_payload) -> bool`. Only literal
`True` permits ordinary intake. All other values consume the event. Loading,
processing, timeout and malformed configuration fail closed for **all** message
intake while enabled. No configuration retains existing behavior. A factory must
be quick, trusted and side-effect free; installing arbitrary code grants that
code the gateway process's privileges. Do not populate this setting from a chat.

Example only; this PR does not edit runtime configuration or provision secrets:

```yaml
platforms:
  qq:
    extra:
      intake_guard:
        factory: hermes_finance.integrations.hermes_qq_client:create_guard
        timeout_seconds: 15
        settings:
          base_url: https://finance.invalid
          request_timeout_seconds: 2
          profiles:
            default:
              key_id: replace-reviewed-id
              secret_name: FINANCE_TRANSPORT_KEY
```

The factory's package is provided by yanwuchen/hermes-finance#41, not vendored
into Hermes. A scoped secret name is a reference, never a key value. Finance
service activation, private address/TLS, scoped key provisioning, owner setup and
live acceptance require their own reviewed steps. The current Finance production
runtime does not expose the QQ bridge. Do not enable this example against it.

`send_private_c2c` uses the **receiving** Hermes QQ adapter, one original QQ
REST send, a bounded timeout, no automatic retry, no body-bearing error logs and
no invented platform ID. It preserves normal QQ sending for ordinary chat.
Restricted content is not split or reformatted through generic send middleware.
A failed/uncertain reply returns a fixed error, never a remote body. A real QQ
response with a valid non-local platform ID is required for acceptance. A timeout
may have sent the message: record UNKNOWN, do not blindly resend.

The external client decides the protected syntax and independently checks the
canonical routing identity plus local ACL. The first Finance client requires
explicit QQ dm_policy=allowlist; ordinary pairing intake is not financial
authorization. Pairing/open modes refuse Finance calls while preserving the
existing ordinary chat/handshake behavior. Finance validates the signed scope,
owner/epoch, permissions, current query and durable delivery. The client must
check original binding and deadline, claim, obtain a permit immediately before
sending, and return a signed receipt. Hermes does not recreate Finance's
authorization state machine.

The first Finance consumer reserves strict English financial commands,
authentication-like numeric input and confirmation. Its conservative fence also
reserves embedded four-digit strings (including years). While enabled it
suppresses attachments and quoted messages because this version cannot prove
their safety before STT/vision. Ordinary **text** chat remains on Hermes's
existing path; natural-language Finance tool registration and safe multimedia
routing remain separate work. Passing these offline tests does not establish
real QQ, real model, deployed TLS or target ARM runtime acceptance.

Validation uses `scripts/run_tests.sh` with a temporary Hermes home, fake QQ
HTTP transport and real adapter imports:

```bash
scripts/run_tests.sh tests/gateway/test_qq_intake_guard.py tests/gateway/test_qqbot.py
```

The Finance cross-repository demonstration additionally uses the real canonical
identity resolver, existing Finance ASGI endpoints/HMAC/SQLite and fake
platform/model IO. No listeners, login, live state or credentials are involved.

Rollback is a separate revert PR before any runtime activation. After activation,
stop Finance interaction before removing its guard: simply disabling a guard
could expose late authentication answers to ordinary chat. No schema, online
service or configuration is changed by this PR.
