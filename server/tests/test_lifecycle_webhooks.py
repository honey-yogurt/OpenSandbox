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

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from opensandbox_server.api import lifecycle
from opensandbox_server.api.schema import RegisterWebhookRequest, SandboxLifecycleEvent
from opensandbox_server.services.lifecycle_webhooks import (
    LifecycleWebhookService,
    SandboxLifecycleWebhookMonitor,
)


class FakeResponse:
    def __init__(self, status_code: int = 204) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[dict] = []

    async def post(self, url: str, *, content: bytes, headers: dict) -> FakeResponse:
        self.calls.append({"url": url, "content": content, "headers": headers})
        if len(self.calls) <= self.failures:
            raise RuntimeError("connection refused")
        return FakeResponse()

    async def aclose(self) -> None:
        return None


def registration_request() -> RegisterWebhookRequest:
    return RegisterWebhookRequest(
        url="https://business.example.com/events",
        secret=SecretStr("test-webhook-secret"),
        events=["sandbox.created", "sandbox.expired"],
    )


def test_register_webhook_api_does_not_return_secret(
    client: TestClient,
    auth_headers: dict,
    monkeypatch,
) -> None:
    service = LifecycleWebhookService(client=FakeClient())
    monkeypatch.setattr(lifecycle, "lifecycle_webhook_service", service)

    response = client.post(
        "/v1/webhooks",
        headers=auth_headers,
        json={
            "url": "https://business.example.com/events",
            "secret": "test-webhook-secret",
            "events": ["sandbox.created", "sandbox.expired"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["events"] == ["sandbox.created", "sandbox.expired"]
    assert "secret" not in payload

    webhook_id = payload["id"]
    assert client.get(f"/v1/webhooks/{webhook_id}", headers=auth_headers).json()["id"] == webhook_id
    assert client.delete(f"/v1/webhooks/{webhook_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/v1/webhooks/{webhook_id}", headers=auth_headers).status_code == 404


@pytest.mark.asyncio
async def test_webhook_delivery_uses_hmac_signature() -> None:
    client = FakeClient()
    service = LifecycleWebhookService(client=client)
    service.register(registration_request())
    event = SandboxLifecycleEvent(
        type="sandbox.expired",
        sandboxId="sbx-001",
        occurredAt=datetime.now(timezone.utc),
    )

    service.emit(event)
    await service.wait_for_deliveries()

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["headers"]["X-OpenSandbox-Event"] == "sandbox.expired"
    timestamp = call["headers"]["X-OpenSandbox-Timestamp"]
    signed_payload = timestamp.encode("ascii") + b"." + call["content"]
    expected = hmac.new(
        b"test-webhook-secret",
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    assert call["headers"]["X-OpenSandbox-Signature"] == f"sha256={expected}"


@pytest.mark.asyncio
async def test_unreachable_webhook_retries_three_times_and_becomes_unavailable() -> None:
    client = FakeClient(failures=4)
    service = LifecycleWebhookService(client=client, retry_delays=(0.0, 0.0, 0.0))
    registration = service.register(registration_request())
    event = SandboxLifecycleEvent(
        type="sandbox.created",
        sandboxId="sbx-001",
        occurredAt=datetime.now(timezone.utc),
    )

    service.emit(event)
    await service.wait_for_deliveries()

    assert len(client.calls) == 4
    assert service.get(registration.id).status == "unavailable"


@pytest.mark.asyncio
async def test_expired_sandbox_emits_event_without_affecting_sandbox_scan() -> None:
    now = datetime.now(timezone.utc)
    sandbox = SimpleNamespace(
        id="sbx-001",
        expires_at=now - timedelta(seconds=1),
        status=SimpleNamespace(state="Running"),
    )

    class SandboxService:
        def list_sandboxes(self, request):
            return SimpleNamespace(items=[sandbox])

    client = FakeClient(failures=4)
    webhook_service = LifecycleWebhookService(client=client, retry_delays=(0.0, 0.0, 0.0))
    registration = webhook_service.register(registration_request())
    monitor = SandboxLifecycleWebhookMonitor(SandboxService(), webhook_service)

    await monitor.scan(now)
    await webhook_service.wait_for_deliveries()

    assert len(client.calls) == 4
    assert webhook_service.get(registration.id).status == "unavailable"
    delivered_event = SandboxLifecycleEvent.model_validate_json(client.calls[0]["content"])
    assert delivered_event.type == "sandbox.expired"
    assert delivered_event.sandbox_id == "sbx-001"
