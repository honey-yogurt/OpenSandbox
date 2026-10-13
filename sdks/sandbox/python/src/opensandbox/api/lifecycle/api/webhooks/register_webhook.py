#
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
#

from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.register_webhook_request import RegisterWebhookRequest
from ...models.webhook_registration import WebhookRegistration
from ...types import Response


def _get_kwargs(
    *,
    body: RegisterWebhookRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/webhooks",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | WebhookRegistration | None:
    if response.status_code == 201:
        response_201 = WebhookRegistration.from_dict(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = ErrorResponse.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 500:
        response_500 = ErrorResponse.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | WebhookRegistration]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RegisterWebhookRequest,
) -> Response[ErrorResponse | WebhookRegistration]:
    """Register a lifecycle webhook

     Registers an HTTP callback for selected sandbox lifecycle events.
    Deliveries are asynchronous and include the
    `X-OpenSandbox-Signature: sha256=<hex>` header. The signature is
    HMAC-SHA256 over `<X-OpenSandbox-Timestamp>.<raw JSON body>`.
    Delivery is retried three times after the initial attempt, then the
    webhook is marked `unavailable`. Delivery failures never fail or block
    sandbox lifecycle operations.

    Args:
        body (RegisterWebhookRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | WebhookRegistration]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: RegisterWebhookRequest,
) -> ErrorResponse | WebhookRegistration | None:
    """Register a lifecycle webhook

     Registers an HTTP callback for selected sandbox lifecycle events.
    Deliveries are asynchronous and include the
    `X-OpenSandbox-Signature: sha256=<hex>` header. The signature is
    HMAC-SHA256 over `<X-OpenSandbox-Timestamp>.<raw JSON body>`.
    Delivery is retried three times after the initial attempt, then the
    webhook is marked `unavailable`. Delivery failures never fail or block
    sandbox lifecycle operations.

    Args:
        body (RegisterWebhookRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | WebhookRegistration
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RegisterWebhookRequest,
) -> Response[ErrorResponse | WebhookRegistration]:
    """Register a lifecycle webhook

     Registers an HTTP callback for selected sandbox lifecycle events.
    Deliveries are asynchronous and include the
    `X-OpenSandbox-Signature: sha256=<hex>` header. The signature is
    HMAC-SHA256 over `<X-OpenSandbox-Timestamp>.<raw JSON body>`.
    Delivery is retried three times after the initial attempt, then the
    webhook is marked `unavailable`. Delivery failures never fail or block
    sandbox lifecycle operations.

    Args:
        body (RegisterWebhookRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | WebhookRegistration]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: RegisterWebhookRequest,
) -> ErrorResponse | WebhookRegistration | None:
    """Register a lifecycle webhook

     Registers an HTTP callback for selected sandbox lifecycle events.
    Deliveries are asynchronous and include the
    `X-OpenSandbox-Signature: sha256=<hex>` header. The signature is
    HMAC-SHA256 over `<X-OpenSandbox-Timestamp>.<raw JSON body>`.
    Delivery is retried three times after the initial attempt, then the
    webhook is marked `unavailable`. Delivery failures never fail or block
    sandbox lifecycle operations.

    Args:
        body (RegisterWebhookRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | WebhookRegistration
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
