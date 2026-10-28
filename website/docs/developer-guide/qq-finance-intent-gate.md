# QQ Finance early intent gate (Pi compatibility branch)

Refs Hermes #3 / Finance #53–54. Review-only, no deployment. Base is
finance/pi-baseline-f97608f at 880cdfcd57e79e4b30d69ed2a16400988cc2246e.
Do not merge this into the fork's newer main or upgrade the running Hermes venv.

The existing adapter raw intake guard runs before body logging, media/quotes,
STT, dedup, busy queue, runner, memory, plugins and ordinary models. Select
gateway.platforms.qqbot.finance_intent_router:create_guard via the existing
config.yaml intake_guard factory. Settings contain finance (the existing
HermesQQClient settings, with explicit natural_intents_enabled), and
receipt_enabled (false by default). No new environment knobs or core tools.

Text uses the existing canonical identity, original DM allowlist, scoped HMAC key
and original C2C sender. Ordinary “帮我确认一下明天的会议时间”, “请确认收到”,
“如何提高收入” and “午饭吃什么” bypass Finance RPC. Sensitive answer/task variants
stay outside ordinary models even on outage, restart or absent pending state.

There is no proven purpose-only no-tool/no-history/no-memory inference interface
in this allowlisted change. General AI intent parsing is BLOCKED/default off.
Use deterministic Finance text candidates, explicit account questions and
Finance-owned confirmation. Do not invoke the ordinary agent as a fallback.

Receipt route is opt-in. “记账截图” obtains a restricted Finance upload claim;
only the next C2C JPEG/PNG for the same canonical bot/profile/user/session/home,
within 120 seconds, is eligible. Ephemeral claim is consumed before IO, dropped
on restart and key change, and never sent to the model or persisted in history.
Quoted, multi-file, arbitrary images, other CDN hosts and redirects are denied.
Only exact QQ CDN hosts multimedia.nt.qq.com, c2cpicdw.qpic.cn, gchat.qpic.cn
are accepted. aiohttp download uses no ambient proxies, 5-second total timeout,
8MiB bound; Finance validates image decoding/pixels again and runs optional OCR.
Upload uses a separate authenticated binary route; JSON remains limited to 8KiB.
Finance rechecks authorization after OCR; only its saved candidate summary is sent
by the original Hermes QQ adapter. No image can confirm or post a transaction.

Local OCR dependencies and actual QQ/CDN shape are not production-tested. Missing
dependencies stay disabled and ask for manual entry; no automatic installation.
Unknown send/ACK or image-processing outcome is not retried. Users should inspect
the original task in Web before issuing another transaction.

Run scripts/run_tests.sh for the three Issue-listed test files in a separate
development environment. Tests use real gateway/Finance sources and synthetic
SQLite/image/QQ transports, including canonical A→B→A homes and scope/key denial.
This is not real QQ or Pi acceptance. Deployment requires separately reviewed
release SHAs, backups, configuration/CA/allowlist verification and manual tests.
Rollback disables the selected factory/receipt setting and restores the reviewed
Gateway pointer, without DB downgrade, deletion or unrelated service changes.
