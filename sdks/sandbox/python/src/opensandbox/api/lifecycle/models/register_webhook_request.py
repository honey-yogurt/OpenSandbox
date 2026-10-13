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

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.webhook_event_type import WebhookEventType

T = TypeVar("T", bound="RegisterWebhookRequest")


@_attrs_define
class RegisterWebhookRequest:
    """
    Attributes:
        url (str): Absolute HTTP or HTTPS callback URL without credentials or a fragment
        secret (str): Shared secret used for HMAC-SHA256 callback signatures
        events (list[WebhookEventType]):
    """

    url: str
    secret: str
    events: list[WebhookEventType]

    def to_dict(self) -> dict[str, Any]:
        url = self.url

        secret = self.secret

        events = []
        for events_item_data in self.events:
            events_item = events_item_data.value
            events.append(events_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "url": url,
                "secret": secret,
                "events": events,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        url = d.pop("url")

        secret = d.pop("secret")

        events = []
        _events = d.pop("events")
        for events_item_data in _events:
            events_item = WebhookEventType(events_item_data)

            events.append(events_item)

        register_webhook_request = cls(
            url=url,
            secret=secret,
            events=events,
        )

        return register_webhook_request
