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
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="FilePolicy")


@_attrs_define
class FilePolicy:
    """File-transfer roots enforced by execd. Each root is an absolute path
    inside the sandbox. An empty list denies the corresponding operation.

        Attributes:
            download_roots (list[str] | Unset): Absolute directories from which files may be downloaded. Example:
                ['/workspace/output'].
            upload_roots (list[str] | Unset): Absolute directories to which files may be uploaded. Example:
                ['/workspace/input'].
    """

    download_roots: list[str] | Unset = UNSET
    upload_roots: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        download_roots: list[str] | Unset = UNSET
        if not isinstance(self.download_roots, Unset):
            download_roots = self.download_roots

        upload_roots: list[str] | Unset = UNSET
        if not isinstance(self.upload_roots, Unset):
            upload_roots = self.upload_roots

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if download_roots is not UNSET:
            field_dict["downloadRoots"] = download_roots
        if upload_roots is not UNSET:
            field_dict["uploadRoots"] = upload_roots

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        download_roots = cast(list[str], d.pop("downloadRoots", UNSET))

        upload_roots = cast(list[str], d.pop("uploadRoots", UNSET))

        file_policy = cls(
            download_roots=download_roots,
            upload_roots=upload_roots,
        )

        return file_policy
