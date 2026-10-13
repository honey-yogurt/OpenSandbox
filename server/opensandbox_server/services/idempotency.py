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

"""Idempotent sandbox creation coordination."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

from fastapi import HTTPException

from opensandbox_server.api.schema import CreateSandboxRequest, CreateSandboxResponse


class IdempotencyKeyError(ValueError):
    """Raised when an idempotency key is missing or malformed."""


class IdempotencyConflictError(ValueError):
    """Raised when a key is reused with a different request body."""


@dataclass
class _IdempotencyState:
    fingerprint: str
    task: Optional[asyncio.Task[CreateSandboxResponse]] = None
    response: Optional[CreateSandboxResponse] = None
    sandbox_id: Optional[str] = None


class IdempotencyService:
    """Coordinate concurrent and retried create requests by idempotency key.

    Keys are scoped to the authenticated tenant. A completed key remains usable
    until its sandbox is deleted or no longer exists, after which the same key can
    create a new sandbox.
    """

    MAX_KEY_LENGTH = 255

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._states: dict[tuple[str, str], _IdempotencyState] = {}
        self._sandbox_keys: dict[str, set[tuple[str, str]]] = {}

    async def create(
        self,
        *,
        key: str,
        scope: str,
        request: CreateSandboxRequest,
        create: Callable[[], Coroutine[Any, Any, CreateSandboxResponse]],
        exists: Callable[[str], object],
    ) -> CreateSandboxResponse:
        self._validate_key(key)
        fingerprint = self._request_fingerprint(request)
        state_key = (scope, key)
        task_to_wait: Optional[asyncio.Task[CreateSandboxResponse]] = None

        async with self._lock:
            state = self._states.get(state_key)
            if state is not None:
                if state.fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used with a different request body"
                    )
                if state.task is not None:
                    task_to_wait = state.task
                elif await self._sandbox_exists(exists, state.sandbox_id):
                    response = state.response
                    assert response is not None
                    return response
                else:
                    self._remove_state(state_key, state)

            if task_to_wait is None:
                task_to_wait = asyncio.create_task(create())
                state = _IdempotencyState(fingerprint=fingerprint, task=task_to_wait)
                self._states[state_key] = state
                task_to_wait.add_done_callback(self._failed_task_callback(state_key, state))

        assert state is not None
        assert task_to_wait is not None
        response = await asyncio.shield(task_to_wait)
        if state.task is task_to_wait:
            state.response = response
            state.sandbox_id = response.id
            state.task = None
            self._sandbox_keys.setdefault(response.id, set()).add(state_key)
        return response

    def release_sandbox(self, sandbox_id: str) -> None:
        """Release every idempotency key associated with a destroyed sandbox."""
        state_keys = self._sandbox_keys.pop(sandbox_id, set())
        for state_key in state_keys:
            state = self._states.get(state_key)
            if state is not None:
                self._remove_state(state_key, state)

    @classmethod
    def _validate_key(cls, key: str) -> None:
        if not key.strip() or len(key) > cls.MAX_KEY_LENGTH:
            raise IdempotencyKeyError(
                f"Idempotency-Key must be a non-empty string of at most {cls.MAX_KEY_LENGTH} characters"
            )

    @staticmethod
    def _request_fingerprint(request: CreateSandboxRequest) -> str:
        payload = request.model_dump(mode="json", by_alias=True)
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    async def _sandbox_exists(
        exists: Callable[[str], object],
        sandbox_id: Optional[str],
    ) -> bool:
        if not sandbox_id:
            return False
        try:
            await asyncio.to_thread(exists, sandbox_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                return False
            raise
        return True

    def _failed_task_callback(
        self,
        state_key: tuple[str, str],
        state: _IdempotencyState,
    ) -> Callable[[asyncio.Task[CreateSandboxResponse]], None]:
        def callback(task: asyncio.Task[CreateSandboxResponse]) -> None:
            if not task.cancelled() and task.exception() is not None:
                self._remove_state(state_key, state)

        return callback

    def _remove_state(self, state_key: tuple[str, str], state: _IdempotencyState) -> None:
        self._states.pop(state_key, None)
        if state.sandbox_id is not None:
            keys = self._sandbox_keys.get(state.sandbox_id)
            if keys is not None:
                keys.discard(state_key)
                if not keys:
                    self._sandbox_keys.pop(state.sandbox_id, None)
