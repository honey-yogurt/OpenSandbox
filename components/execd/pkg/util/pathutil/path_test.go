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

package pathutil

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestExpandPath_HomeAndEnv(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("BASE_DIR", "project")

	got, err := ExpandPath("~/docs/$BASE_DIR")
	require.NoError(t, err)
	require.Equal(t, filepath.Join(home, "docs", "project"), got)
}

func TestExpandPath_Empty(t *testing.T) {
	got, err := ExpandPath("")
	require.NoError(t, err)
	require.Equal(t, "", got)
}

func TestExpandPath_EnvVarInMiddle(t *testing.T) {
	t.Setenv("MID", "segment")

	got, err := ExpandPath("prefix/$MID/suffix")
	require.NoError(t, err)
	require.Equal(t, filepath.Join("prefix", "segment", "suffix"), got)
}

func TestExpandPathWithEnv_RequestOverrideHasHigherPriority(t *testing.T) {
	// Different casing identifies one variable on Windows and two on Unix.
	t.Setenv("workdir", "lowercase")
	t.Setenv("WORKDIR", "from-process")

	got, err := ExpandPathWithEnv("base/$WORKDIR", map[string]string{
		"WORKDIR": "from-request",
	})
	require.NoError(t, err)
	require.Equal(t, filepath.Join("base", "from-request"), got)
	got, err = ExpandPathWithEnv("$workdir", map[string]string{"WORKDIR": "from-request"})
	require.NoError(t, err)
	expected := "lowercase"
	if runtime.GOOS == "windows" {
		expected = "from-request"
	}
	require.Equal(t, expected, got)

}

func TestExpandPathWithEnv_CanResolveVarOnlyInOverride(t *testing.T) {
	got, err := ExpandPathWithEnv("$WORKDIR/tmp", map[string]string{
		"WORKDIR": "/tmp/ws",
	})
	require.NoError(t, err)
	require.Equal(t, filepath.Join("/tmp/ws", "tmp"), got)
}

func TestExpandPath_UndefinedEnvVarInMiddleReturnsError(t *testing.T) {
	got, err := ExpandPath("prefix/$NOT_SET/suffix")
	require.Error(t, err)
	require.Contains(t, err.Error(), "NOT_SET")
	require.Equal(t, "", got)
}

func TestExpandPath_UndefinedEnvVarReturnsError(t *testing.T) {
	got, err := ExpandPath("$NOT_SET/tmp")
	require.Error(t, err)
	require.Contains(t, err.Error(), "NOT_SET")
	require.Equal(t, "", got)
}

func TestExpandPath_UndefinedEnvVarOnlyReturnsError(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	got, err := ExpandPath("$NOT_SET")
	require.Error(t, err)
	require.Contains(t, err.Error(), "NOT_SET")
	require.Equal(t, "", got)
}

func TestIsPathWithinRoot(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "allowed")
	require.NoError(t, os.Mkdir(root, 0o755))

	tests := []struct {
		name string
		path string
		want bool
	}{
		{name: "root itself", path: root, want: true},
		{name: "nested path", path: filepath.Join(root, "output", "result.csv"), want: true},
		{name: "missing nested path", path: filepath.Join(root, "new", "result.csv"), want: true},
		{name: "sibling with shared prefix", path: filepath.Join(base, "allowed-other", "result.csv"), want: false},
		{name: "outside root", path: filepath.Join(base, "secret.txt"), want: false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := IsPathWithinRoot(tt.path, root)
			require.NoError(t, err)
			require.Equal(t, tt.want, got)
		})
	}
}

func TestIsPathWithinRootRejectsSymlinkEscape(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "allowed")
	outside := filepath.Join(base, "outside")
	require.NoError(t, os.Mkdir(root, 0o755))
	require.NoError(t, os.Mkdir(outside, 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(outside, "secret.txt"), []byte("secret"), 0o600))

	link := filepath.Join(root, "escape.txt")
	if err := os.Symlink(filepath.Join(outside, "secret.txt"), link); err != nil {
		t.Skipf("symlink unavailable: %v", err)
	}

	got, err := IsPathWithinRoot(link, root)
	require.NoError(t, err)
	require.False(t, got)
}

func TestIsPathWithinRootRejectsDanglingSymlinkEscape(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "allowed")
	outside := filepath.Join(base, "outside")
	require.NoError(t, os.Mkdir(root, 0o755))

	link := filepath.Join(root, "escape")
	if err := os.Symlink(filepath.Join(outside, "new-file"), link); err != nil {
		t.Skipf("symlink unavailable: %v", err)
	}

	got, err := IsPathWithinRoot(link, root)
	require.NoError(t, err)
	require.False(t, got)
}
