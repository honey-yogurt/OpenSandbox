# Copyright 2025 The OpenSandbox Authors
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
import asyncio

import pytest

from fastapi.testclient import TestClient

from opensandbox_server.api import lifecycle
from opensandbox_server.api.schema import (
    CreateSandboxRequest,
    CreateSandboxResponse,
    DeleteSandboxResponse,
    SandboxStatus,
)


def _create_response(sandbox_id: str) -> CreateSandboxResponse:
    now = datetime.now(timezone.utc)
    return CreateSandboxResponse(
        id=sandbox_id,
        status=SandboxStatus(state="Running"),
        metadata=None,
        expiresAt=now + timedelta(hours=1),
        createdAt=now,
        entrypoint=["tail", "-f", "/dev/null"],
    )


def test_create_sandbox_openapi_describes_synchronous_provisioning(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    create_response = response.json()["paths"]["/v1/sandboxes"]["post"]["responses"]["202"]
    assert create_response["description"] == "Sandbox created and provisioned successfully"


def test_create_sandbox_openapi_declares_quota_rejection_403(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    responses = response.json()["paths"]["/v1/sandboxes"]["post"]["responses"]
    quota_response = responses["403"]
    assert quota_response["description"].startswith("Namespace ResourceQuota exhausted")
    assert quota_response["content"]["application/json"]["schema"]["$ref"].endswith("ErrorResponse")


def test_create_sandbox_openapi_declares_idempotency_key(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    parameters = response.json()["paths"]["/v1/sandboxes"]["post"]["parameters"]
    idempotency = next(parameter for parameter in parameters if parameter["name"] == "Idempotency-Key")
    assert idempotency["in"] == "header"
    assert idempotency["required"] is False
    assert idempotency["schema"]["anyOf"][0] == {"type": "string", "maxLength": 255, "minLength": 1}


def test_create_sandbox_returns_202_and_service_payload(
    client: TestClient,
    auth_headers: dict,
    sample_sandbox_request: dict,
    monkeypatch,
) -> None:
    now = datetime.now(timezone.utc)
    calls: list[object] = []

    class StubService:
        @staticmethod
        async def create_sandbox(request) -> CreateSandboxResponse:
            calls.append(request)
            return CreateSandboxResponse(
                id="sbx-001",
                status=SandboxStatus(state="Pending"),
                metadata={"project": "test-project"},
                expiresAt=now + timedelta(hours=1),
                createdAt=now,
                entrypoint=["python", "-c", "print('Hello from sandbox')"],
            )

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())

    response = client.post(
        "/v1/sandboxes",
        headers=auth_headers,
        json=sample_sandbox_request,
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["id"] == "sbx-001"
    assert payload["status"]["state"] == "Pending"
    assert payload["metadata"]["project"] == "test-project"
    assert payload["entrypoint"] == ["python", "-c", "print('Hello from sandbox')"]
    assert len(calls) == 1
    assert calls[0].image.uri == "python:3.11"


def test_create_sandbox_idempotency_key_reuses_conflicts_and_releases(
    client: TestClient,
    auth_headers: dict,
    sample_sandbox_request: dict,
    monkeypatch,
) -> None:
    calls: list[object] = []
    existing_sandboxes: set[str] = set()

    class StubService:
        @staticmethod
        async def create_sandbox(request) -> CreateSandboxResponse:
            calls.append(request)
            sandbox_id = f"sbx-{len(calls):03d}"
            existing_sandboxes.add(sandbox_id)
            return _create_response(sandbox_id)

        @staticmethod
        def get_sandbox(sandbox_id: str):
            if sandbox_id not in existing_sandboxes:
                from fastapi import HTTPException

                raise HTTPException(status_code=404)
            return sandbox_id

        @staticmethod
        def delete_sandbox(sandbox_id: str) -> DeleteSandboxResponse:
            existing_sandboxes.remove(sandbox_id)
            return DeleteSandboxResponse(
                deletionConfirmed=True,
                deletedAt=datetime.now(timezone.utc),
            )

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())
    headers = {**auth_headers, "Idempotency-Key": "reuse-conflict-release"}

    first = client.post("/v1/sandboxes", headers=headers, json=sample_sandbox_request)
    retry = client.post("/v1/sandboxes", headers=headers, json=sample_sandbox_request)
    different_body = {**sample_sandbox_request, "image": {"uri": "python:3.12"}}
    conflict = client.post("/v1/sandboxes", headers=headers, json=different_body)
    delete = client.delete("/v1/sandboxes/sbx-001", headers=auth_headers)
    recreated = client.post("/v1/sandboxes", headers=headers, json=sample_sandbox_request)

    assert first.status_code == 202
    assert retry.status_code == 202
    assert first.json()["id"] == retry.json()["id"] == "sbx-001"
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "SANDBOX::IDEMPOTENCY_KEY_CONFLICT"
    assert delete.status_code == 200
    assert recreated.status_code == 202
    assert recreated.json()["id"] == "sbx-002"
    assert len(calls) == 2


def test_create_sandbox_rejects_invalid_idempotency_key(
    client: TestClient,
    auth_headers: dict,
    sample_sandbox_request: dict,
    monkeypatch,
) -> None:
    class StubService:
        @staticmethod
        async def create_sandbox(request) -> CreateSandboxResponse:
            raise AssertionError("create must not run for an invalid idempotency key")

        @staticmethod
        def get_sandbox(sandbox_id: str) -> str:
            return sandbox_id

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())

    response = client.post(
        "/v1/sandboxes",
        headers={**auth_headers, "Idempotency-Key": " "},
        json=sample_sandbox_request,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "SANDBOX::INVALID_PARAMETER"


@pytest.mark.asyncio
async def test_idempotency_service_concurrent_requests_create_once() -> None:
    from opensandbox_server.services.idempotency import IdempotencyService

    service = IdempotencyService()
    request = CreateSandboxRequest.model_validate(
        {
            "extensions": {"poolRef": "pool-a"},
            "timeout": 3600,
        }
    )
    response = _create_response("sbx-concurrent")
    allow_create = asyncio.Event()
    create_calls = 0

    async def create() -> CreateSandboxResponse:
        nonlocal create_calls
        create_calls += 1
        if create_calls == 1:
            await allow_create.wait()
        return response

    def exists(sandbox_id: str) -> bool:
        return sandbox_id == response.id

    first = asyncio.create_task(
        service.create(
            key="concurrent",
            scope="tenant-a",
            request=request,
            create=create,
            exists=exists,
        )
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    second = asyncio.create_task(
        service.create(
            key="concurrent",
            scope="tenant-a",
            request=request,
            create=create,
            exists=exists,
        )
    )
    allow_create.set()
    first_response, second_response = await asyncio.gather(first, second)

    assert first_response is response
    assert second_response is response
    assert create_calls == 1


def test_create_sandbox_manual_cleanup_omits_none_fields(
    client: TestClient,
    auth_headers: dict,
    sample_sandbox_request: dict,
    monkeypatch,
) -> None:
    now = datetime.now(timezone.utc)

    class StubService:
        @staticmethod
        async def create_sandbox(request) -> CreateSandboxResponse:
            return CreateSandboxResponse(
                id="sbx-manual",
                status=SandboxStatus(state="Pending"),
                metadata=None,
                expiresAt=None,
                createdAt=now,
                entrypoint=["python", "-c", "print('Hello from sandbox')"],
            )

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())
    sample_sandbox_request.pop("timeout", None)

    response = client.post(
        "/v1/sandboxes",
        headers=auth_headers,
        json=sample_sandbox_request,
    )

    assert response.status_code == 202
    payload = response.json()
    assert "expiresAt" not in payload
    assert "metadata" not in payload
    assert "reason" not in payload["status"]
    assert "message" not in payload["status"]
    assert "lastTransitionAt" not in payload["status"]


def test_create_sandbox_rejects_invalid_request(
    client: TestClient,
    auth_headers: dict,
) -> None:
    response = client.post(
        "/v1/sandboxes",
        headers=auth_headers,
        json={"timeout": 10},
    )

    assert response.status_code == 422


def test_create_sandbox_accepts_snapshot_id_without_entrypoint(
    client: TestClient,
    auth_headers: dict,
    monkeypatch,
) -> None:
    now = datetime.now(timezone.utc)
    calls: list[object] = []

    async def passthrough_resolve(request):
        return request

    monkeypatch.setattr(lifecycle, "resolve_sandbox_image_from_request", passthrough_resolve)

    class StubService:
        @staticmethod
        async def create_sandbox(request) -> CreateSandboxResponse:
            calls.append(request)
            return CreateSandboxResponse(
                id="sbx-from-snapshot",
                status=SandboxStatus(state="Pending"),
                metadata=None,
                expiresAt=now + timedelta(hours=1),
                createdAt=now,
                entrypoint=None,
            )

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())

    response = client.post(
        "/v1/sandboxes",
        headers=auth_headers,
        json={
            "snapshotId": "snap-001",
            "resourceLimits": {"cpu": "500m", "memory": "512Mi"},
        },
    )

    assert response.status_code == 202
    assert calls[0].snapshot_id == "snap-001"
    assert calls[0].entrypoint is None


def test_create_sandbox_accepts_snapshot_id_with_entrypoint(
    client: TestClient,
    auth_headers: dict,
    monkeypatch,
) -> None:
    now = datetime.now(timezone.utc)
    calls: list[object] = []

    async def passthrough_resolve(request):
        return request

    monkeypatch.setattr(lifecycle, "resolve_sandbox_image_from_request", passthrough_resolve)

    class StubService:
        @staticmethod
        async def create_sandbox(request) -> CreateSandboxResponse:
            calls.append(request)
            return CreateSandboxResponse(
                id="sbx-from-snapshot",
                status=SandboxStatus(state="Pending"),
                metadata=None,
                expiresAt=now + timedelta(hours=1),
                createdAt=now,
                entrypoint=["python", "app.py"],
            )

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())

    response = client.post(
        "/v1/sandboxes",
        headers=auth_headers,
        json={
            "snapshotId": "snap-001",
            "resourceLimits": {"cpu": "500m", "memory": "512Mi"},
            "entrypoint": ["python", "app.py"],
        },
    )

    assert response.status_code == 202
    assert calls[0].snapshot_id == "snap-001"
    assert calls[0].entrypoint == ["python", "app.py"]


def test_delete_sandbox_returns_confirmation_and_calls_service(
    client: TestClient,
    auth_headers: dict,
    monkeypatch,
) -> None:
    calls: list[str] = []
    deleted_at = datetime.now(timezone.utc)

    class StubService:
        @staticmethod
        def delete_sandbox(sandbox_id: str) -> DeleteSandboxResponse:
            calls.append(sandbox_id)
            return DeleteSandboxResponse(deletion_confirmed=True, deleted_at=deleted_at)

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())

    response = client.delete("/v1/sandboxes/sbx-001", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "deletionConfirmed": True,
        "deletedAt": deleted_at.isoformat().replace("+00:00", "Z"),
    }
    assert calls == ["sbx-001"]


def test_delete_sandbox_requires_api_key(client: TestClient) -> None:
    response = client.delete("/v1/sandboxes/sbx-001")

    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_API_KEY"


def test_create_sandbox_pool_only_passes_resolution_untouched(
    client: TestClient,
    auth_headers: dict,
    monkeypatch,
) -> None:
    now = datetime.now(timezone.utc)
    calls: list[CreateSandboxRequest] = []
    resolve_calls: list[CreateSandboxRequest] = []

    async def spy_resolve(request: CreateSandboxRequest):
        resolve_calls.append(request)
        return request

    monkeypatch.setattr(lifecycle, "resolve_sandbox_image_from_request", spy_resolve)

    class StubService:
        @staticmethod
        async def create_sandbox(request) -> CreateSandboxResponse:
            calls.append(request)
            return CreateSandboxResponse(
                id="sbx-pool",
                status=SandboxStatus(state="Pending"),
                metadata=None,
                expiresAt=now + timedelta(hours=1),
                createdAt=now,
                entrypoint=None,
            )

    monkeypatch.setattr(lifecycle, "sandbox_service", StubService())

    response = client.post(
        "/v1/sandboxes",
        headers=auth_headers,
        json={
            "extensions": {"poolRef": "pool-a"},
            "timeout": 3600,
        },
    )

    # Pool-only creates carry no snapshot; resolution must pass them
    # through to the backend untouched (no 400/404 from the snapshot repo).
    assert response.status_code == 202, response.text
    assert len(resolve_calls) == 1
    assert calls[0].extensions == {"poolRef": "pool-a"}
