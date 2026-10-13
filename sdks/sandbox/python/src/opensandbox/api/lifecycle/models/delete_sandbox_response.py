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
from dateutil.parser import isoparse

T = TypeVar("T", bound="DeleteSandboxResponse")


@_attrs_define
class DeleteSandboxResponse:
    """Deletion acknowledgement with runtime cleanup confirmation.

    Attributes:
        deletion_confirmed (bool): Whether the runtime confirmed that the workload, Pod, and
            server-managed PVCs were removed before the deletion timeout.
        deleted_at (datetime.datetime): Timestamp of the deletion acknowledgement.
    """

    deletion_confirmed: bool
    deleted_at: datetime.datetime

    def to_dict(self) -> dict[str, Any]:
        deletion_confirmed = self.deletion_confirmed

        deleted_at = self.deleted_at.isoformat()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "deletionConfirmed": deletion_confirmed,
                "deletedAt": deleted_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        deletion_confirmed = d.pop("deletionConfirmed")

        deleted_at = isoparse(d.pop("deletedAt"))

        delete_sandbox_response = cls(
            deletion_confirmed=deletion_confirmed,
            deleted_at=deleted_at,
        )

        return delete_sandbox_response
