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

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.webhook_event_type import WebhookEventType

T = TypeVar("T", bound="SandboxLifecycleEvent")


@_attrs_define
class SandboxLifecycleEvent:
    """JSON body delivered to registered lifecycle webhooks

    Attributes:
        type_ (WebhookEventType):
        sandbox_id (str):
        occurred_at (datetime.datetime):
    """

    type_: WebhookEventType
    sandbox_id: str
    occurred_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        sandbox_id = self.sandbox_id

        occurred_at = self.occurred_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "sandboxId": sandbox_id,
                "occurredAt": occurred_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = WebhookEventType(d.pop("type"))

        sandbox_id = d.pop("sandboxId")

        occurred_at = isoparse(d.pop("occurredAt"))

        sandbox_lifecycle_event = cls(
            type_=type_,
            sandbox_id=sandbox_id,
            occurred_at=occurred_at,
        )

        sandbox_lifecycle_event.additional_properties = d
        return sandbox_lifecycle_event

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
