"""Opt-in Finance consumer at the existing raw QQ gate. No agent/model calls."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import hashlib
import re
from urllib.parse import urlsplit

from hermes_finance.auth.transport import RECEIPT_PATH, sign_receipt
from hermes_finance.integrations.hermes_qq_client import HermesQQClient, GatewayClientError
from hermes_finance.integrations.receipt_ocr import MAX_IMAGE_BYTES, validate_image

# Exact platform CDN hosts. No wildcard, redirect, user URL, proxy or URL from OCR.
QQ_IMAGE_HOSTS = frozenset({"multimedia.nt.qq.com", "c2cpicdw.qpic.cn", "gchat.qpic.cn"})


@dataclass(frozen=True, repr=False)
class ImageClaim:
    task_id: str
    token: str = field(repr=False)
    expires: float
    key_tag: str = field(repr=False)


class FinanceIntentRouter(HermesQQClient):
    def __init__(self, adapter, settings, *, image_fetcher=None, **kwargs):
        if (type(settings) is not dict or set(settings)-{"finance", "receipt_enabled"}
                or type(settings.get("receipt_enabled", False)) is not bool):
            raise GatewayClientError("invalid_intent_router")
        super().__init__(adapter, settings.get("finance"), **kwargs)
        self.receipt_enabled = settings.get("receipt_enabled", False)
        self.image_fetcher = image_fetcher
        self.pending = {}  # Secrets are ephemeral; restart drops claims, never resumes image IO.

    @staticmethod
    def _scope(binding, identity):
        return (binding.bot,binding.profile,binding.user,binding.session,str(identity.runtime_home))

    async def _download(self, attachment):
        url = attachment.get("url")
        mime = attachment.get("content_type")
        if mime not in ("image/png", "image/jpeg") or type(url) is not str:
            raise GatewayClientError("invalid_image")
        parsed=urlsplit(url)
        if (parsed.scheme!="https" or parsed.hostname not in QQ_IMAGE_HOSTS or parsed.username
                or parsed.password or parsed.port not in (None,443) or parsed.fragment):
            raise GatewayClientError("untrusted_image_origin")
        if self.image_fetcher is not None:
            raw=await self.image_fetcher(url,mime)
        else:
            import aiohttp
            # aiohttp does not log request URLs/bodies. No HTTPX request INFO
            # containing signed QQ CDN queries, redirects or ambient proxy.
            async with aiohttp.ClientSession(trust_env=False,
                    timeout=aiohttp.ClientTimeout(total=5)) as client:
                async with client.get(url,allow_redirects=False) as response:
                    if response.status!=200 or response.content_type!=mime:
                        raise GatewayClientError("image_unavailable")
                    raw=bytearray()
                    async for part in response.content.iter_chunked(65536):
                        if len(raw)+len(part)>MAX_IMAGE_BYTES:
                            raise GatewayClientError("image_too_large")
                        raw.extend(part)
                    raw=bytes(raw)
        validate_image(raw,mime)
        return raw,mime

    async def _upload(self, client, binding, identity, claim, raw, mime):
        values=asdict(binding)
        values.update(task_id=claim.task_id,upload_token=claim.token,mime=mime)
        headers=sign_receipt(self._key(binding,identity),raw,values,timestamp=int(self.clock()))
        async with client.stream("POST",self.origin+RECEIPT_PATH,content=raw,headers=headers,
                                 timeout=10,follow_redirects=False) as response:
            if response.status_code!=200:
                raise GatewayClientError("image_rejected")
            size=0
            async for part in response.aiter_bytes():
                size+=len(part)
                if size>4096:raise GatewayClientError("invalid_response")
        await self._deliver(client,binding,identity)

    async def __call__(self, event_type, payload):
        try:
            return await asyncio.wait_for(self._consume(event_type,payload),20)
        except asyncio.TimeoutError:
            return False

    async def _consume(self, event_type, payload):
        if type(payload) is not dict:
            return False
        text=payload.get("content","")
        images=payload.get("attachments")
        if not images and text!="记账截图":
            if text=="取消记账":
                try:
                    binding,identity=self._binding(payload)
                    self.pending.pop(self._scope(binding,identity),None)
                except Exception:
                    pass
            return await super().__call__(event_type,payload)
        if not self.receipt_enabled or event_type!="C2C_MESSAGE_CREATE":
            return False
        if payload.get("msg_elements") or payload.get("message_reference"):
            return False
        try:
            binding,identity=self._binding(payload)  # Reuse the one canonical resolver.
            scope=self._scope(binding,identity)
            key_tag=hashlib.sha256(self._key(binding,identity).material).hexdigest()
            if images:
                claim=self.pending.pop(scope,None)  # Consume before any await/download.
                if (claim is None or self.clock()>=claim.expires or claim.key_tag!=key_tag
                        or type(images) is not list or len(images)!=1 or type(images[0]) is not dict
                        or type(text) is not str or text.strip()):
                    return False
                raw,mime=await self._download(images[0])
                # IO may outlive permissions/claim or key rotation.
                if (self.clock()>=claim.expires or not self._local_allowed(binding.user)
                        or hashlib.sha256(self._key(binding,identity).material).hexdigest()!=key_tag):
                    return False
                async with self._connection() as client:
                    await self._upload(client,binding,identity,claim,raw,mime)
            else:
                async with self._connection() as client:
                    result=await self._rpc(client,"command",binding,identity,text="记账截图")
                    task,token,expiry=(result.get(k) for k in ("task_id","upload_token","expires_at"))
                    if (type(task) is not str or not re.fullmatch(r"[0-9a-f]{48}",task)
                            or type(token) is not str or not re.fullmatch(r"[0-9a-f]{64}",token)
                            or type(expiry) not in (int,float) or not self.clock()<expiry<=self.clock()+120):
                        return False
                    self.pending[scope]=ImageClaim(task,token,expiry,key_tag)
                    await self._deliver(client,binding,identity)
        except Exception:
            # No raw body, OCR text, URL, token or exception to logs/models.
            return False
        return False


def create_guard(adapter, settings):
    return FinanceIntentRouter(adapter,settings)
