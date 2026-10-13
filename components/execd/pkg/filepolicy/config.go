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

package filepolicy

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync/atomic"

	"github.com/alibaba/opensandbox/execd/pkg/log"
	"github.com/alibaba/opensandbox/execd/pkg/util/pathutil"
)

// ConfigEnv is the server-injected transport for sandbox file policies.
const ConfigEnv = "OPENSANDBOX_FILE_POLICY"

// Config restricts upload and download targets to explicit roots.
type Config struct {
	DownloadRoots []string `json:"downloadRoots"`
	UploadRoots   []string `json:"uploadRoots"`
}

var currentConfig atomic.Pointer[Config]

// LoadFromEnv parses and installs the injected policy, then removes the
// transport from the process environment. When no policy is configured it
// retains legacy full-filesystem access and logs a security warning.
func LoadFromEnv() error {
	raw := strings.TrimSpace(os.Getenv(ConfigEnv))
	_ = os.Unsetenv(ConfigEnv)

	if raw == "" {
		currentConfig.Store(nil)
		log.Warn("file policy: no policy configured; file APIs remain unrestricted")
		return nil
	}

	var config Config
	if err := json.Unmarshal([]byte(raw), &config); err != nil {
		return fmt.Errorf("decode %s: %w", ConfigEnv, err)
	}
	if err := validate(config); err != nil {
		return fmt.Errorf("validate %s: %w", ConfigEnv, err)
	}

	currentConfig.Store(&config)
	return nil
}

// TransportEnv returns the environment entry needed to pass the active policy
// to a short-lived filesystem worker. The parent removes its own transport env
// after startup, so inheritance alone is not sufficient.
func TransportEnv() (string, bool) {
	config := currentConfig.Load()
	if config == nil {
		return "", false
	}
	encoded, err := json.Marshal(config)
	if err != nil {
		return "", false
	}
	return fmt.Sprintf("%s=%s", ConfigEnv, encoded), true
}

func validate(config Config) error {
	if err := validateRoots(config.DownloadRoots, "downloadRoots"); err != nil {
		return err
	}
	return validateRoots(config.UploadRoots, "uploadRoots")
}

func validateRoots(roots []string, field string) error {
	for _, root := range roots {
		if strings.TrimSpace(root) == "" || strings.ContainsRune(root, 0) {
			return fmt.Errorf("%s entries must be non-empty absolute paths", field)
		}
		if !strings.HasPrefix(root, "/") {
			return fmt.Errorf("%s entry %q must be an absolute path", field, root)
		}
	}
	return nil
}

// AllowsDownload reports whether a daemon-backed path may be downloaded.
// Errors are treated as denied by the caller because the configured root
// cannot be resolved safely.
func AllowsDownload(path string) (bool, error) {
	return allowsPath(path, false)
}

// AllowsUpload reports whether a daemon-backed path may receive uploads.
func AllowsUpload(path string) (bool, error) {
	return allowsPath(path, true)
}

// AllowsVirtualDownload applies download roots to isolated-session paths.
func AllowsVirtualDownload(path string) bool {
	return allowsVirtualPath(path, false)
}

// AllowsVirtualUpload applies upload roots to isolated-session paths.
func AllowsVirtualUpload(path string) bool {
	return allowsVirtualPath(path, true)
}

func allowsPath(path string, upload bool) (bool, error) {
	config := currentConfig.Load()
	if config == nil {
		return true, nil
	}

	roots := config.DownloadRoots
	if upload {
		roots = config.UploadRoots
	}
	if len(roots) == 0 {
		return false, nil
	}
	for _, root := range roots {
		allowed, err := pathutil.IsPathWithinRoot(path, root)
		if err != nil {
			return false, err
		}
		if allowed {
			return true, nil
		}
	}
	return false, nil
}

func allowsVirtualPath(path string, upload bool) bool {
	config := currentConfig.Load()
	if config == nil {
		return true
	}

	roots := config.DownloadRoots
	if upload {
		roots = config.UploadRoots
	}
	if len(roots) == 0 {
		return false
	}
	for _, root := range roots {
		if pathutil.IsVirtualPathWithinRoot(path, root) {
			return true
		}
	}
	return false
}

// ResetForTest clears the process-wide policy.
func ResetForTest() {
	currentConfig.Store(nil)
}

// SetForTest installs a policy directly.
func SetForTest(config *Config) {
	currentConfig.Store(config)
}
