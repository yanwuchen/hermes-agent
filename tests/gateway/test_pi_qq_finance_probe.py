"""Hermes #5: metadata safety and real-source, fictitious QQ release handoff."""
import asyncio
import importlib
import os
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from scripts import pi_qq_finance_probe as probe
from gateway.platforms.qqbot.intake_guard import IntakeGuard


def test_pointer_probe_never_executes_repository_filters(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    marker = tmp_path / "filter-marker"
    helper = tmp_path / "fake_filter.py"
    helper.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[1]).touch()\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n")
    command = " ".join(shlex.quote(str(x).replace("\\", "/")) for x in (sys.executable, helper, marker))
    subprocess.run(["git", "-C", str(repo), "config", "filter.fake.clean", command], check=True)
    (repo / ".gitattributes").write_text("payload filter=fake\n")
    (repo / "payload").write_text("fictitious\n")
    subprocess.run(["git", "-C", str(repo), "add", "payload"], check=True, capture_output=True)
    assert marker.exists()  # Positive control: the external filter really executes.
    marker.unlink()
    (repo / "payload").write_text("changed fictitious\n")
    (repo / ".git/HEAD").write_text(probe.EXPECTED_HERMES + "\n")
    factory = repo / "gateway/platforms/qqbot/finance_intent_router.py"
    factory.parent.mkdir(parents=True)
    factory.write_text("raise RuntimeError('must not import')\n")
    before = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k: pytest.fail("probe executed Git/code"))
    rows = probe.inspect_source(repo)
    assert ("PASS", "gateway_source_pointer", "REVIEWED_POINTER") in rows
    assert ("UNVERIFIED", "intake_factory", "SOURCE_PRESENT_NOT_LOADED") in rows
    assert ("UNVERIFIED", "source_integrity", "WORKTREE_NOT_ATTESTED") in rows
    assert not marker.exists()
    assert before == {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    monkeypatch.setattr(probe, "collect", lambda: (_ for _ in ()).throw(OSError("private-path-password-QQ-ID")))
    assert probe.main([]) == 2
    assert capsys.readouterr().out == "UNVERIFIED tool PROBE_UNAVAILABLE\n"
    assert probe.main(["private-secret"]) == 3
    assert capsys.readouterr().out == "BLOCKED tool NO_ARGUMENTS_ALLOWED\n"


@pytest.mark.parametrize("kind", ["loose", "packed", "mismatch", "traversal", "oversized", "missing"])
def test_pointer_metadata_is_bounded_and_not_runtime_attestation(tmp_path, kind):
    git = tmp_path / ".git"
    git.mkdir()
    ref = "refs/heads/fake"
    (git / "HEAD").write_text("ref: " + ref + "\n")
    if kind == "loose":
        (git / "refs/heads").mkdir(parents=True)
        (git / ref).write_text(probe.EXPECTED_HERMES + "\n")
    elif kind == "packed":
        (git / "packed-refs").write_text(probe.EXPECTED_HERMES + " " + ref + "\n")
    elif kind == "mismatch":
        (git / "HEAD").write_text("a" * 40)
    elif kind == "traversal":
        (git / "HEAD").write_text("ref: refs/heads/../../private")
    elif kind == "oversized":
        (git / "HEAD").write_text("x" * 4097)
    rows = probe.inspect_source(tmp_path)
    expected = "PASS" if kind in ("loose", "packed") else "BLOCKED" if kind == "mismatch" else "UNVERIFIED"
    assert rows[0][0] == expected
    assert rows[-1] == ("UNVERIFIED", "source_integrity", "WORKTREE_NOT_ATTESTED")


@pytest.mark.linux_only
@pytest.mark.parametrize("kind", ["symlink", "parent_link", "fifo", "directory"])
def test_metadata_special_files_are_never_followed_or_blocking(tmp_path, kind):
    target = tmp_path / "metadata"
    if kind == "symlink":
        private = tmp_path / "private"
        private.write_text("not metadata")
        target.symlink_to(private)
    elif kind == "parent_link":
        real = tmp_path / "real"
        real.mkdir()
        (real / "HEAD").write_text("not metadata")
        target.symlink_to(real, target_is_directory=True)
        target = target / "HEAD"
    elif kind == "fifo":
        os.mkfifo(target)
    else:
        target.mkdir()
    with pytest.raises(ValueError):
        probe.read_regular(target)


@pytest.mark.linux_only
@pytest.mark.parametrize("state", ["running", "inactive", "malformed", "changed", "timeout"])
def test_service_snapshot_has_no_private_output_or_optimistic_claims(tmp_path, monkeypatch, capsys, state):
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert argv[0] == "/usr/bin/systemctl" and "show" in argv
        assert "--property=ActiveState,SubState,MainPID" in argv
        assert "SECRET" not in kwargs["env"]
        if state == "timeout":
            raise subprocess.TimeoutExpired("private-argv", 5)
        raw = b"ActiveState=active\nSubState=running\nMainPID=123\n"
        if state == "inactive": raw = b"ActiveState=inactive\nSubState=dead\nMainPID=0\n"
        if state == "malformed": raw = b"Private=secret\n"
        if state == "changed" and len(calls) % 2 == 0: raw = raw.replace(b"123", b"124")
        return SimpleNamespace(returncode=0, stdout=raw)
    monkeypatch.setenv("SECRET", "must-not-inherit")
    monkeypatch.setattr(probe.subprocess, "run", run)
    monkeypatch.setattr(probe, "process_metadata", lambda pid: ("/private/python3.12", tmp_path, b"900"))
    rc = probe.main([])
    output = capsys.readouterr().out
    assert rc in (2, 3) and "private" not in output and "secret" not in output
    assert all(len(line.split()) == 3 and line.split()[0] in {"PASS", "BLOCKED", "UNVERIFIED"} for line in output.splitlines())
    assert "UNVERIFIED companion RUNNING_IMPORT_NOT_ATTESTED" in output
    assert ("PASS gateway_service" in output) == (state == "running")


def test_missing_companion_factory_cannot_be_activated_safely(monkeypatch):
    def absent(name):
        raise ModuleNotFoundError("fictitious missing companion")
    monkeypatch.setattr(importlib, "import_module", absent)
    guard = IntakeGuard(None, {"factory": "gateway.platforms.qqbot.finance_intent_router:create_guard"})
    assert guard.consumer is None
    # Explicit handoff STOP condition. Never fix by failing open for secrets.
    assert asyncio.run(guard.allow("C2C_MESSAGE_CREATE", {"content": "你好"})) is False


# Optional companion lane: probe safety still runs in standalone Hermes installs.
try:
    import hermes_finance
except ImportError:
    HAS_COMPANION = False
else:
    HAS_COMPANION = True
    from tests.gateway.test_qq_finance_intent_router import rig, packet
    from gateway.platforms.qqbot.finance_intent_router import FinanceIntentRouter
    from hermes_finance import Ledger
    from hermes_finance.api import create_app
    from hermes_finance.api.dependencies import Principal
    from hermes_finance.integrations.finance_intents import AccountPreferences


@pytest.mark.skipif(not HAS_COMPANION, reason="requires exact Finance companion in handoff lane")
@pytest.mark.parametrize("finish", ["confirm", "cancel", "restart", "revoke", "expiry", "unknown"])
def test_real_adapter_web_defaults_and_scoped_confirmation(rig, finish):
    r = rig
    AccountPreferences(r.finance).put(Principal("fake-owner", 1), {
        "approved_default_source": None, "aliases": {}, "categories": {}})
    app = create_app(auth=r.auth, finance=r.finance, queries=r.queries, bridge=r.bridge, dashboard=True)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(r.qq)) as qq, httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://fake.test") as finance:
            r.adapter._http_client = qq
            settings = {**r.settings, "receipt_enabled": False}
            consumer = FinanceIntentRouter(r.adapter, settings, http_client=finance, clock=lambda:r.now[0])
            outer = IntakeGuard(r.adapter, None)
            outer.enabled = True
            outer.consumer = consumer
            r.adapter._intake_guard = outer
            door = AsyncMock()
            setattr(r.adapter, r.adapter._INBOUND_HANDLERS["C2C_MESSAGE_CREATE"], door)
            async def send(text, event):
                await r.adapter._on_message("C2C_MESSAGE_CREATE", packet(text, event))
            await send("你好", "ordinary")
            assert door.await_count == 1
            await send("记账 午饭 25 元", "no-default")
            assert "待补充" in r.sent[-1]
            await send("选择 来源 bank", "choose-source")
            await send("选择 目标 food", "choose-target")
            assert "[bank]" in r.sent[-1] and "[food]" in r.sent[-1]
            await send("取消记账", "cancel-first")
            login = await finance.post("/auth/login", headers={"Origin":"https://fake.test"},
                json={"username":"fake-owner", "password":"fake-password-only"})
            assert login.status_code == 200
            headers = {"Origin":"https://fake.test", "X-CSRF-Token": login.json()["csrf_token"]}
            response = await finance.put("/dashboard/api/account-preferences", headers=headers,
                json={"approved_default_source":"bank", "aliases":{}, "categories":{"午饭":"food"}})
            assert response.status_code == 200
            await send("记账 午饭 25 元", "new-candidate")
            await send("记账 午饭 25 元", "new-candidate")
            summary = r.sent[-1]
            assert "25.00 元" in summary and "午饭" in summary
            assert summary.index("[bank]") < summary.index("[food]")
            with Ledger(r.database) as ledger: assert not ledger.list_transactions()
            if finish == "restart":
                outer.consumer = FinanceIntentRouter(r.adapter, settings, http_client=finance, clock=lambda:r.now[0])
            elif finish == "cancel": await send("取消记账", "cancel-current")
            elif finish == "revoke": r.store.revoke("fake-owner")
            elif finish == "expiry": r.now[0] += 600
            elif finish == "unknown":
                original_rpc = consumer._rpc
                async def response_lost(client, operation, *args, **kwargs):
                    result = await original_rpc(client, operation, *args, **kwargs)
                    if operation == "command" and kwargs.get("text") == "确认":
                        raise httpx.ReadTimeout("fictitious response lost after commit")
                    return result
                consumer._rpc = response_lost
            await send("确认", "confirmation")
            await send("确认", "confirmation")
            await send("确认", "confirmation-again")
            with Ledger(r.database) as ledger:
                assert len(ledger.list_transactions()) == (0 if finish in {"cancel","revoke","expiry"} else 1)
            assert door.await_count == 1
    asyncio.run(run())


@pytest.mark.linux_only
def test_process_snapshot_reads_only_own_executable_cwd_and_starttime():
    executable, cwd, stamp = probe.process_metadata(os.getpid())
    assert Path(executable).is_absolute()
    assert cwd == Path.cwd().resolve()
    assert stamp.isdigit()
    assert probe.process_metadata(os.getpid()) == (executable, cwd, stamp)
