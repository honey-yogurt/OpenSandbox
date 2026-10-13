// Copyright 2026 The OpenSandbox Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package api

import "time"

type PolicyStatusResponse struct {
	Status          string     `json:"status,omitempty"`
	Mode            string     `json:"mode,omitempty"`
	EnforcementMode string     `json:"enforcementMode,omitempty"`
	Reason          string     `json:"reason,omitempty"`
	Warning         string     `json:"warning,omitempty"`
	Enforced        *bool      `json:"enforced,omitempty"`
	LastVerifiedAt  *time.Time `json:"lastVerifiedAt,omitempty"`
	Policy          any        `json:"policy,omitempty"`
}

type EnforcementStatusResponse struct {
	Status            string     `json:"status"`
	EnforcementStatus string     `json:"enforcementStatus"`
	Enforced          bool       `json:"enforced"`
	Mode              string     `json:"mode"`
	Reason            string     `json:"reason,omitempty"`
	Warning           string     `json:"warning,omitempty"`
	LastVerifiedAt    *time.Time `json:"lastVerifiedAt,omitempty"`
}
