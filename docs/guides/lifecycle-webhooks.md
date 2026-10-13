---
title: Lifecycle Webhooks
description: Receive HMAC-signed sandbox lifecycle events instead of polling sandbox status.
---

# Lifecycle Webhooks

Lifecycle webhooks deliver sandbox state changes to a business application. They reduce polling and let automation react promptly to creation, readiness, expiry, deletion, and failure.

## Events

| Event | Emitted when |
|---|---|
| `sandbox.created` | A create request is accepted and assigned a sandbox ID |
| `sandbox.running` | The sandbox becomes ready |
| `sandbox.expired` | Its configured expiration time is reached |
| `sandbox.deleted` | It is removed after an explicit or automatic deletion |
| `sandbox.failed` | Runtime state changes to `Failed` |

Webhook delivery is asynchronous. A callback outage does not block or fail sandbox operations.

## Register a webhook

The registration URL must be an absolute HTTP or HTTPS URL. The shared secret is write-only and is not returned by the API.

```bash
curl -X POST "$OPEN_SANDBOX_URL/v1/webhooks" \
  -H "Content-Type: application/json" \
  -H "OPEN-SANDBOX-API-KEY: $OPEN_SANDBOX_API_KEY" \
  -d '{
    "url": "https://business.example.com/opensandbox/events",
    "secret": "replace-with-a-shared-secret",
    "events": ["sandbox.created", "sandbox.running", "sandbox.expired"]
  }'
```

Use `GET /v1/webhooks/{webhookId}` to inspect delivery status and `DELETE /v1/webhooks/{webhookId}` to remove a registration. After the initial delivery attempt and three retries fail, the registration status becomes `unavailable`.

::: warning Registration Lifetime
Webhook registrations are currently stored in the server process memory. Re-register webhooks after a server restart or redeployment.
:::

## Event payload

Events are sent as JSON:

```json
{
  "type": "sandbox.expired",
  "sandboxId": "01f7043c-9cb3-4ea0-af6f-c6b19e2210a1",
  "occurredAt": "2026-10-13T08:30:00Z"
}
```

Each request includes these headers:

| Header | Value |
|---|---|
| `X-OpenSandbox-Event` | Event type |
| `X-OpenSandbox-Delivery-ID` | Unique delivery identifier |
| `X-OpenSandbox-Timestamp` | Unix timestamp used in the signature |
| `X-OpenSandbox-Signature` | `sha256=<hex HMAC-SHA256 digest>` |
| `X-OpenSandbox-Webhook-ID` | Registered webhook ID |

The signature covers the exact request body:

```text
<X-OpenSandbox-Timestamp>.<raw JSON body>
```

Verify the signature before processing the event:

```python
import hashlib
import hmac


def verify(request_body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

Reject callbacks with invalid signatures and stale timestamps to limit replay risk. Process deliveries idempotently using `sandboxId` and `type`, because network retries can deliver the same lifecycle event more than once.
