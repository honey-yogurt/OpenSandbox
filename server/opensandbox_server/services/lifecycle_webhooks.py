# Copyright 2026 The OpenSandbox Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Lifecycle webhook registration, delivery, and sandbox state observation."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import logging
from typing import Deque, Optional, Protocol
from uuid import uuid4

import httpx

from opensandbox_server.api.schema import (
    ListSandboxesRequest,
    ListWebhooksResponse,
    RegisterWebhookRequest,
    Sandbox,
    SandboxLifecycleEvent,
    WebhookEventType,
    WebhookRegistration,
)

logger = logging.getLogger(__name__)


class WebhookResponse(Protocol):
    def raise_for_status(self) -> None: ...


class WebhookClient(Protocol):
    async def post(self, url: str, *, content: bytes, headers: dict) -> WebhookResponse: ...

    async def aclose(self) -> None: ...


@dataclass
class _StoredWebhook:
    registration: WebhookRegistration
    secret: str


@dataclass
class _ObservedSandbox:
    state: str
    expires_at: Optional[datetime]
    terminal: bool = False


class LifecycleWebhookService:
    """Registry and asynchronous HMAC-signed event delivery service."""

    def __init__(
        self,
        *,
        client: Optional[WebhookClient] = None,
        retry_delays: tuple[float, ...] = (0.25, 0.5, 1.0),
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=5.0)
        self._owns_client = client is None
        self._retry_delays = retry_delays
        self._webhooks: dict[str, _StoredWebhook] = {}
        self._emitted: set[tuple[str, str]] = set()
        self._emitted_order: Deque[tuple[str, str]] = deque()
        self._tasks: set[asyncio.Task[None]] = set()

    def register(self, request: RegisterWebhookRequest) -> WebhookRegistration:
        registration = WebhookRegistration(
            id=f"wh_{uuid4()}",
            url=request.url,
            events=request.events,
            status="active",
            createdAt=datetime.now(timezone.utc),
        )
        self._webhooks[registration.id] = _StoredWebhook(
            registration=registration,
            secret=request.secret.get_secret_value(),
        )
        return registration

    def list(self) -> ListWebhooksResponse:
        return ListWebhooksResponse(
            items=[stored.registration.model_copy() for stored in self._webhooks.values()]
        )

    def get(self, webhook_id: str) -> WebhookRegistration:
        stored = self._webhooks.get(webhook_id)
        if stored is None:
            raise KeyError(webhook_id)
        return stored.registration.model_copy()

    def delete(self, webhook_id: str) -> None:
        if webhook_id not in self._webhooks:
            raise KeyError(webhook_id)
        del self._webhooks[webhook_id]

    def emit(self, event: SandboxLifecycleEvent) -> None:
        event_key = (event.type, event.sandbox_id)
        if event_key in self._emitted:
            return
        self._remember_event(event_key)
        task = asyncio.create_task(self._deliver_event(event))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def sign_payload(self, secret: str, timestamp: int, payload: bytes) -> str:
        signed_payload = str(timestamp).encode("ascii") + b"." + payload
        digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    async def wait_for_deliveries(self) -> None:
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    async def close(self) -> None:
        for task in tuple(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        if self._owns_client:
            await self._client.aclose()

    def _remember_event(self, event_key: tuple[str, str]) -> None:
        self._emitted.add(event_key)
        self._emitted_order.append(event_key)
        while len(self._emitted_order) > 4096:
            self._emitted.discard(self._emitted_order.popleft())

    async def _deliver_event(self, event: SandboxLifecycleEvent) -> None:
        recipients = [
            stored
            for stored in self._webhooks.values()
            if stored.registration.status == "active" and event.type in stored.registration.events
        ]
        if not recipients:
            return
        await asyncio.gather(
            *(self._deliver_to_webhook(stored, event) for stored in recipients),
            return_exceptions=True,
        )

    async def _deliver_to_webhook(
        self,
        stored: _StoredWebhook,
        event: SandboxLifecycleEvent,
    ) -> None:
        payload = event.model_dump_json(by_alias=True).encode("utf-8")
        delivery_id = str(uuid4())
        for attempt in range(len(self._retry_delays) + 1):
            timestamp = int(datetime.now(timezone.utc).timestamp())
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "OpenSandbox-Webhook/1.0",
                "X-OpenSandbox-Delivery-ID": delivery_id,
                "X-OpenSandbox-Event": event.type,
                "X-OpenSandbox-Signature": self.sign_payload(stored.secret, timestamp, payload),
                "X-OpenSandbox-Timestamp": str(timestamp),
                "X-OpenSandbox-Webhook-ID": stored.registration.id,
            }
            try:
                response = await self._client.post(
                    stored.registration.url,
                    content=payload,
                    headers=headers,
                )
                response.raise_for_status()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if attempt == len(self._retry_delays):
                    stored.registration.status = "unavailable"
                    logger.warning(
                        f"Webhook {stored.registration.id} marked unavailable after delivery failures: {exc}"
                    )
                    return
                await asyncio.sleep(self._retry_delays[attempt])
                continue
            return


class SandboxLifecycleWebhookMonitor:
    """Observe sandbox states and emit lifecycle transitions without coupling them to requests."""

    def __init__(
        self,
        sandbox_service,
        webhook_service: LifecycleWebhookService,
        *,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._sandbox_service = sandbox_service
        self._webhook_service = webhook_service
        self._poll_interval_seconds = poll_interval_seconds
        self._observed: dict[str, _ObservedSandbox] = {}
        self._initialized = False
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self._webhook_service.close()

    def observe_created(self, sandbox_id: str, expires_at: Optional[datetime]) -> None:
        self._observed[sandbox_id] = _ObservedSandbox(state="Pending", expires_at=expires_at)
        self._emit("sandbox.created", sandbox_id)

    def observe_deleted(self, sandbox_id: str) -> None:
        self._emit("sandbox.deleted", sandbox_id)
        self._observed[sandbox_id] = _ObservedSandbox(
            state="Terminated",
            expires_at=None,
            terminal=True,
        )

    async def scan(self, now: Optional[datetime] = None) -> None:
        current_time = now or datetime.now(timezone.utc)
        try:
            response = self._sandbox_service.list_sandboxes(ListSandboxesRequest(pagination=None))
        except Exception as exc:
            logger.warning(f"Sandbox lifecycle webhook scan failed: {exc}")
            return

        current = {sandbox.id: sandbox for sandbox in response.items}
        for sandbox_id, sandbox in current.items():
            self._observe_current(sandbox_id, sandbox, current_time)

        for sandbox_id in tuple(self._observed.keys() - current.keys()):
            previous = self._observed[sandbox_id]
            if previous.terminal:
                del self._observed[sandbox_id]
                continue
            if previous.expires_at is not None and previous.expires_at <= current_time:
                self._emit("sandbox.expired", sandbox_id, current_time)
            else:
                self._emit("sandbox.deleted", sandbox_id, current_time)
            del self._observed[sandbox_id]

        self._initialized = True

    async def _run(self) -> None:
        while True:
            await self.scan()
            await asyncio.sleep(self._poll_interval_seconds)

    def _observe_current(self, sandbox_id: str, sandbox: Sandbox, current_time: datetime) -> None:
        previous = self._observed.get(sandbox_id)
        expires_at = sandbox.expires_at
        if expires_at is not None and expires_at <= current_time:
            self._emit("sandbox.expired", sandbox_id, current_time)
            self._observed[sandbox_id] = _ObservedSandbox(
                state="Terminated",
                expires_at=expires_at,
                terminal=True,
            )
            return

        if previous is None and self._initialized:
            self._emit("sandbox.created", sandbox_id, current_time)

        if previous is None or previous.terminal:
            self._observed[sandbox_id] = _ObservedSandbox(
                state=sandbox.status.state,
                expires_at=expires_at,
            )
            return

        state = sandbox.status.state
        if state != previous.state:
            if state == "Running":
                self._emit("sandbox.running", sandbox_id, current_time)
            elif state == "Failed":
                self._emit("sandbox.failed", sandbox_id, current_time)
            elif state == "Terminated":
                self._emit("sandbox.deleted", sandbox_id, current_time)
        self._observed[sandbox_id] = _ObservedSandbox(state=state, expires_at=expires_at)

    def _emit(self, event_type: WebhookEventType, sandbox_id: str, now: Optional[datetime] = None) -> None:
        self._webhook_service.emit(
            SandboxLifecycleEvent(
                type=event_type,
                sandboxId=sandbox_id,
                occurredAt=now or datetime.now(timezone.utc),
            )
        )
