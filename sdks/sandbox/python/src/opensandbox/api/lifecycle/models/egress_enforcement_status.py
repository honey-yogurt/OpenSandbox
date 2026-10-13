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

from ..models.egress_enforcement_status_enforcement_status import EgressEnforcementStatusEnforcementStatus
from ..models.egress_enforcement_status_mode import EgressEnforcementStatusMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="EgressEnforcementStatus")


@_attrs_define
class EgressEnforcementStatus:
    """Live egress enforcement state reported by the sandbox egress service.

    Attributes:
        status (str):  Example: ok.
        enforcement_status (EgressEnforcementStatusEnforcementStatus):
        enforced (bool): True only after kernel rules have been verified.
        mode (EgressEnforcementStatusMode):
        reason (str | Unset):
        warning (str | Unset):
        last_verified_at (datetime.datetime | Unset):
    """

    status: str
    enforcement_status: EgressEnforcementStatusEnforcementStatus
    enforced: bool
    mode: EgressEnforcementStatusMode
    reason: str | Unset = UNSET
    warning: str | Unset = UNSET
    last_verified_at: datetime.datetime | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        enforcement_status = self.enforcement_status.value

        enforced = self.enforced

        mode = self.mode.value

        reason = self.reason

        warning = self.warning

        last_verified_at: str | Unset = UNSET
        if not isinstance(self.last_verified_at, Unset):
            last_verified_at = self.last_verified_at.isoformat()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "status": status,
                "enforcementStatus": enforcement_status,
                "enforced": enforced,
                "mode": mode,
            }
        )
        if reason is not UNSET:
            field_dict["reason"] = reason
        if warning is not UNSET:
            field_dict["warning"] = warning
        if last_verified_at is not UNSET:
            field_dict["lastVerifiedAt"] = last_verified_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = d.pop("status")

        enforcement_status = EgressEnforcementStatusEnforcementStatus(d.pop("enforcementStatus"))

        enforced = d.pop("enforced")

        mode = EgressEnforcementStatusMode(d.pop("mode"))

        reason = d.pop("reason", UNSET)

        warning = d.pop("warning", UNSET)

        _last_verified_at = d.pop("lastVerifiedAt", UNSET)
        last_verified_at: datetime.datetime | Unset
        if isinstance(_last_verified_at, Unset):
            last_verified_at = UNSET
        else:
            last_verified_at = isoparse(_last_verified_at)

        egress_enforcement_status = cls(
            status=status,
            enforcement_status=enforcement_status,
            enforced=enforced,
            mode=mode,
            reason=reason,
            warning=warning,
            last_verified_at=last_verified_at,
        )

        return egress_enforcement_status
