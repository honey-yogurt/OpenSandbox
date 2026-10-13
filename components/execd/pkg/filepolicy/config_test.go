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
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestPolicyAllowsLegacyModeWhenUnset(t *testing.T) {
	ResetForTest()
	t.Cleanup(ResetForTest)

	allowed, err := AllowsDownload("/etc/passwd")
	require.NoError(t, err)
	require.True(t, allowed)

	allowed, err = AllowsUpload("/etc/passwd")
	require.NoError(t, err)
	require.True(t, allowed)
}

func TestPolicyRestrictsPaths(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "allowed")
	require.NoError(t, os.Mkdir(root, 0o755))
	SetForTest(&Config{
		DownloadRoots: []string{root},
		UploadRoots:   []string{root},
	})
	t.Cleanup(ResetForTest)

	allowed, err := AllowsDownload(filepath.Join(root, "result.csv"))
	require.NoError(t, err)
	require.True(t, allowed)

	allowed, err = AllowsDownload(filepath.Join(base, "secret.txt"))
	require.NoError(t, err)
	require.False(t, allowed)

	allowed, err = AllowsUpload(filepath.Join(base, "secret.txt"))
	require.NoError(t, err)
	require.False(t, allowed)
}

func TestPolicyEmptyRootsDenyDirection(t *testing.T) {
	SetForTest(&Config{})
	t.Cleanup(ResetForTest)

	require.False(t, AllowsVirtualDownload("/workspace/output/result.csv"))
	require.False(t, AllowsVirtualUpload("/workspace/input/result.csv"))
}

func TestLoadFromEnvParsesAndUnsetsTransport(t *testing.T) {
	t.Setenv(ConfigEnv, `{"downloadRoots":["/workspace/output"],"uploadRoots":["/workspace/input"]}`)

	require.NoError(t, LoadFromEnv())
	t.Cleanup(ResetForTest)

	require.Empty(t, os.Getenv(ConfigEnv))
	require.True(t, AllowsVirtualDownload("/workspace/output/result.csv"))
	require.False(t, AllowsVirtualDownload("/etc/passwd"))
	require.True(t, AllowsVirtualUpload("/workspace/input/result.csv"))
	require.False(t, AllowsVirtualUpload("/workspace/output/result.csv"))

	transport, ok := TransportEnv()
	require.True(t, ok)
	require.Equal(
		t,
		`OPENSANDBOX_FILE_POLICY={"downloadRoots":["/workspace/output"],"uploadRoots":["/workspace/input"]}`,
		transport,
	)
}

func TestLoadFromEnvRejectsRelativeRoots(t *testing.T) {
	t.Setenv(ConfigEnv, `{"downloadRoots":["workspace/output"]}`)

	require.Error(t, LoadFromEnv())
}
