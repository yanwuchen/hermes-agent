"""Real gateway source + Finance ASGI. Fictitious keys, homes, images and QQ only."""
import asyncio
import binascii
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock
import zlib

import httpx
import pytest

from gateway.config import PlatformConfig
from gateway.platforms.qqbot.adapter import QQAdapter
from gateway.platforms.qqbot.intake_guard import IntakeGuard
from gateway.platforms.qqbot.finance_intent_router import FinanceIntentRouter
from hermes_finance import Ledger, AccountType
from hermes_finance.api import create_app
from hermes_finance.api.dependencies import Principal
from hermes_finance.auth.store import AuthStore
from hermes_finance.auth.sessions import WebAuth
from hermes_finance.auth.passwords import hash_password
from hermes_finance.auth.query_grants import QueryService
from hermes_finance.auth.transport import TransportAuth, TransportKey
from hermes_finance.services.finance import FinanceService
from hermes_finance.integrations.finance_intents import AccountPreferences
from hermes_finance.integrations.qq_commands import QQBridge
from hermes_finance.integrations.qq_delivery import HermesDelivery
from hermes_finance.integrations.receipt_ocr import extract_fields


def packet(text="",event="fake-event",**extra):
    return dict(id=event,content=text,author={"user_openid":"fake-user"},**extra)

def png():
    def c(k,v):return struct.pack(">I",len(v))+k+v+struct.pack(">I",binascii.crc32(k+v)&0xffffffff)
    return b"\x89PNG\r\n\x1a\n"+c(b"IHDR",struct.pack(">IIBBBBB",1,1,8,2,0,0,0))+c(b"IDAT",zlib.compress(b"\0"*4))+c(b"IEND",b"")

@pytest.fixture
def rig(tmp_path,monkeypatch):
    now=[1000.]
    database=tmp_path/"fake-ledger.sqlite3"
    with Ledger(database) as ledger:
        for name,kind in [("bank",AccountType.ASSET),("food",AccountType.EXPENSE)]:
            ledger.create_account("虚构"+name,kind,account_id=name)
    store=AuthStore(tmp_path/"fake-identity.sqlite3")
    store.provision("fake-owner",hash_password("fake-password-only"))
    auth=WebAuth(store,origin="https://fake.test",clock=lambda:now[0])
    finance=FinanceService(auth,lambda:Ledger(database),account_ids={"bank","food"})
    queries=QueryService(auth,secret_provider=lambda _:"16",
             allowed_subjects={("fake-bot",p,"fake-user") for p in ("A","B")},account_ids={"bank"})
    keys={p:TransportKey("key-"+p,"fake-bot",p,(p*32).encode()) for p in ("A","B")}
    verifier=TransportAuth(store,key_provider=lambda kid:next((k for k in keys.values() if k.identifier==kid),None),clock=lambda:now[0])
    bridge=QQBridge(queries,finance,verifier,HermesDelivery(queries,verifier),allow_writes=True)
    AccountPreferences(finance).put(Principal("fake-owner",1),{
        "approved_default_source":"bank","aliases":{},"categories":{"午饭":"food"}})
    ocr_calls=[]
    def fake_ocr(raw,mime):
        ocr_calls.append((len(raw),mime))
        return extract_fields("支付成功\n实付 25 元\n商户：虚构午饭")
    app=create_app(bridge=bridge,receipt_ocr=fake_ocr)
    adapter=QQAdapter(PlatformConfig(enabled=True,extra={
        "app_id":"fake-bot","client_secret":"fake","dm_policy":"allowlist","allow_from":["fake-user"],
        "markdown_support":False}))
    runner=SimpleNamespace(config=SimpleNamespace(multiplex_profiles=False),_primary_profile_name="A")
    runner._transport_owner=lambda source:(adapter,runner._primary_profile_name)
    runner._owning_profile=lambda a,p:(a,runner._primary_profile_name)
    runner._profile_name_for_source=lambda source,adapter_profile=None:None
    adapter.gateway_runner=runner
    adapter._running=True;adapter._ws=SimpleNamespace(closed=False)
    adapter._ensure_token=AsyncMock(return_value="fictitious-platform-token")
    homes={p:tmp_path/("home-"+p) for p in ("A","B")}
    for p,home in homes.items():
        directory=home/"finance";directory.mkdir(parents=True);directory.chmod(0o700)
        key=directory/"hmac.key";key.write_text(keys[p].material.hex());key.chmod(0o600)
    monkeypatch.setenv("HERMES_HOME",str(homes["A"]))
    settings={"finance":{"base_url":"https://fake.test","natural_intents_enabled":True,
        "profiles":{p:{"key_id":"key-"+p,"secret_file":"finance/hmac.key"} for p in ("A","B")}},
        "receipt_enabled":True}
    sent=[];rpc=[]
    async def qq(request):
        data=json.loads(request.content);sent.append(data["content"])
        return httpx.Response(200,json={"id":"fake-platform-"+str(len(sent))})
    async def observe(request):rpc.append(request.url.path)
    async def fetch(url,mime):return png()
    yield SimpleNamespace(**locals())
    store.close()


def test_real_early_gate_chat_and_durable_confirmation(rig,caplog):
    r=rig
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(r.qq)) as qq, httpx.AsyncClient(
            transport=httpx.ASGITransport(r.app),event_hooks={"request":[r.observe]}) as finance:
            r.adapter._http_client=qq
            guard=FinanceIntentRouter(r.adapter,r.settings,http_client=finance,clock=lambda:r.now[0])
            r.adapter._intake_guard=IntakeGuard(r.adapter,None)
            r.adapter._intake_guard.enabled=True;r.adapter._intake_guard.consumer=guard
            door=AsyncMock()
            r.adapter._on_c2c_message=door
            # _on_message uses _INBOUND_HANDLERS: install the actual named door.
            setattr(r.adapter,r.adapter._INBOUND_HANDLERS["C2C_MESSAGE_CREATE"],door)
            r.adapter._active_sessions["busy"]=True;r.adapter._pending_messages["busy"]=[]
            for text in ("帮我确认一下明天的会议时间","请确认收到","如何提高收入","午饭吃什么"):
                await r.adapter._on_message("C2C_MESSAGE_CREATE",packet(text,"chat-"+str(door.await_count)))
            assert door.await_count==4 and not r.rpc
            for text in ("4000","4 0 0 0","请确认收到 ４０００","x "+"ab"*24):
                await r.adapter._on_message("C2C_MESSAGE_CREATE",packet(text))
            assert door.await_count==4
            await r.adapter._on_message("C2C_MESSAGE_CREATE",packet("记账 午饭 25 元","intent"))
            assert "25.00 元" in r.sent[-1] and "[bank]" in r.sent[-1]
            with Ledger(r.database) as ledger:assert not ledger.list_transactions()
            for _ in range(2):
                await r.adapter._on_message("C2C_MESSAGE_CREATE",packet("确认","confirmation"))
            with Ledger(r.database) as ledger:assert len(ledger.list_transactions())==1
            assert door.await_count==4 and r.adapter._pending_messages=={"busy":[]}
    asyncio.run(run())
    assert "4000" not in caplog.text


def test_canonical_home_a_b_a_uses_own_file_and_no_fallback(rig,monkeypatch):
    r=rig
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(r.qq)) as qq, httpx.AsyncClient(
                transport=httpx.ASGITransport(r.app)) as finance:
            r.adapter._http_client=qq
            guard=FinanceIntentRouter(r.adapter,r.settings,http_client=finance,clock=lambda:r.now[0])
            for profile in ("A","B","A"):
                monkeypatch.setenv("HERMES_HOME",str(r.homes[profile]))
                r.runner._primary_profile_name=profile
                binding,identity=guard._binding(packet("hello"))
                assert binding.profile==profile and Path(identity.runtime_home)==r.homes[profile]
                assert guard._key(binding,identity)==r.keys[profile]
                await guard("C2C_MESSAGE_CREATE",packet("记账 午饭 1 元","intent-"+profile))
            monkeypatch.setenv("HERMES_HOME",str(r.homes["B"]))
            r.runner._primary_profile_name="B"
            (r.homes["B"]/"finance/hmac.key").unlink()
            before=len(r.sent)
            assert await guard("C2C_MESSAGE_CREATE",packet("记账 午饭 2 元","missing-key")) is False
            assert len(r.sent)==before
    asyncio.run(run())


@pytest.mark.parametrize("failure",["none","expired","restarted","other_profile","cancelled","bad_host","quote","multi","group","revoked"])
def test_image_is_one_shot_scoped_and_never_agent_input(rig,monkeypatch,failure):
    r=rig
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(r.qq)) as qq, httpx.AsyncClient(
                transport=httpx.ASGITransport(r.app)) as finance:
            r.adapter._http_client=qq
            guard=FinanceIntentRouter(r.adapter,r.settings,http_client=finance,image_fetcher=r.fetch,clock=lambda:r.now[0])
            assert await guard("C2C_MESSAGE_CREATE",packet("记账截图","trigger")) is False
            if failure=="expired":r.now[0]+=120
            elif failure=="restarted":guard=FinanceIntentRouter(r.adapter,r.settings,http_client=finance,image_fetcher=r.fetch,clock=lambda:r.now[0])
            elif failure=="other_profile":
                monkeypatch.setenv("HERMES_HOME",str(r.homes["B"]));r.runner._primary_profile_name="B"
            elif failure=="cancelled":await guard("C2C_MESSAGE_CREATE",packet("取消记账","cancel"))
            elif failure=="revoked":r.store.revoke("fake-owner")
            image={"content_type":"image/png","url":"https://c2cpicdw.qpic.cn/fictitious.png"}
            if failure=="bad_host":image["url"]="https://example.invalid/fictitious.png"
            payload=packet(event="image",attachments=[image]*(2 if failure=="multi" else 1))
            if failure=="quote":payload["message_reference"]={"id":"private"}
            assert await guard("GROUP_AT_MESSAGE_CREATE" if failure=="group" else "C2C_MESSAGE_CREATE",payload) is False
            with Ledger(r.database) as ledger:assert not ledger.list_transactions()
            if failure=="none":
                assert r.ocr_calls==[(len(png()),"image/png")]
                assert "25.00 元" in r.sent[-1]
                assert await guard("C2C_MESSAGE_CREATE",payload) is False
                assert len(r.ocr_calls)==1
                await guard("C2C_MESSAGE_CREATE",packet("确认","confirm"))
                with Ledger(r.database) as ledger:assert len(ledger.list_transactions())==1
            elif failure!="revoked":assert r.ocr_calls==[]
    asyncio.run(run())


def test_unconfigured_and_outage_chat_pass_sensitive_closed(rig):
    r=rig
    async def transport(request):raise httpx.ConnectError("private failure")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            guard=FinanceIntentRouter(r.adapter,r.settings,http_client=client,clock=lambda:r.now[0])
            for text in ("请确认收到","如何提高收入"):
                assert await guard("C2C_MESSAGE_CREATE",packet(text)) is True
            for text in ("记账 午饭 25 元","4000","确认 "+"ab"*24):
                assert await guard("C2C_MESSAGE_CREATE",packet(text)) is False
    asyncio.run(run())
