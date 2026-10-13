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
	"errors"
	"fmt"
	"io/fs"
	"os"
	pathpkg "path"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
)

var envVarPattern = regexp.MustCompile(`\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)`)

// IsPathWithinRoot reports whether path, after symlink resolution, is equal to
// root or located below it. Missing path components are resolved against the
// nearest existing ancestor so upload targets may not yet exist.
func IsPathWithinRoot(path, root string) (bool, error) {
	absolutePath, err := filepath.Abs(filepath.Clean(path))
	if err != nil {
		return false, fmt.Errorf("resolve path: %w", err)
	}
	absoluteRoot, err := filepath.Abs(filepath.Clean(root))
	if err != nil {
		return false, fmt.Errorf("resolve root: %w", err)
	}

	resolvedPath, err := resolveSymlinkPath(absolutePath)
	if err != nil {
		return false, fmt.Errorf("resolve symlinks in %s: %w", path, err)
	}
	resolvedRoot, err := resolveSymlinkPath(absoluteRoot)
	if err != nil {
		return false, fmt.Errorf("resolve symlinks in %s: %w", root, err)
	}

	relativePath, err := filepath.Rel(resolvedRoot, resolvedPath)
	if err != nil {
		return false, fmt.Errorf("compare path with root: %w", err)
	}
	return relativePath == "." || (relativePath != ".." && !startsWithParentTraversal(relativePath)), nil
}

func resolveSymlinkPath(path string) (string, error) {
	resolved, err := filepath.EvalSymlinks(path)
	if err == nil {
		return resolved, nil
	}
	if !errors.Is(err, fs.ErrNotExist) {
		return "", err
	}

	if link, readErr := os.Readlink(path); readErr == nil {
		target := link
		if !filepath.IsAbs(target) {
			target = filepath.Join(filepath.Dir(path), target)
		}
		return resolveSymlinkPath(target)
	}

	parent, err := resolveSymlinkPath(filepath.Dir(path))
	if err != nil {
		return "", err
	}
	return filepath.Join(parent, filepath.Base(path)), nil
}

func startsWithParentTraversal(path string) bool {
	return len(path) >= 3 && path[:3] == ".."+string(filepath.Separator)
}

// IsVirtualPathWithinRoot performs the same prefix check for paths that are
// not backed directly by the daemon filesystem, such as isolated-session
// overlay paths. Such paths must be absolute so they cannot be reinterpreted
// against an unknown relative base.
func IsVirtualPathWithinRoot(path, root string) bool {
	cleanedPath := pathpkg.Clean(path)
	cleanedRoot := pathpkg.Clean(root)
	if !strings.HasPrefix(cleanedPath, "/") || !strings.HasPrefix(cleanedRoot, "/") {
		return false
	}
	if cleanedPath == cleanedRoot {
		return true
	}
	if cleanedRoot == "/" {
		return true
	}
	return strings.HasPrefix(cleanedPath, cleanedRoot+"/")
}

func envMapFromProcessAndOverrides(envOverrides map[string]string) map[string]string {
	out := make(map[string]string, len(envOverrides)+16)
	for _, kv := range os.Environ() {
		parts := strings.SplitN(kv, "=", 2)
		if len(parts) != 2 {
			continue
		}
		out[EnvKey(parts[0])] = parts[1]
	}
	for k, v := range envOverrides {
		out[EnvKey(k)] = v
	}
	return out
}

func validateEnvVars(path string, env map[string]string) error {
	matches := envVarPattern.FindAllStringSubmatch(path, -1)
	if len(matches) == 0 {
		return nil
	}

	missingSet := make(map[string]struct{})
	for _, m := range matches {
		name := m[1]
		if name == "" {
			name = m[2]
		}
		if _, ok := env[EnvKey(name)]; !ok {
			missingSet[name] = struct{}{}
		}
	}
	if len(missingSet) == 0 {
		return nil
	}

	missing := make([]string, 0, len(missingSet))
	for name := range missingSet {
		missing = append(missing, name)
	}
	sort.Strings(missing)
	return fmt.Errorf("path references undefined environment variables: %s", strings.Join(missing, ","))
}

// ExpandPathWithEnv expands environment variables and a leading "~" to user home.
// Environment resolution uses process env overlaid by envOverrides.
func ExpandPathWithEnv(path string, envOverrides map[string]string) (string, error) {
	if path == "" {
		return "", nil
	}
	env := envMapFromProcessAndOverrides(envOverrides)
	if err := validateEnvVars(path, env); err != nil {
		return "", err
	}

	expanded := os.Expand(path, func(key string) string {
		return env[EnvKey(key)]
	})
	if expanded == "~" || strings.HasPrefix(expanded, "~/") || strings.HasPrefix(expanded, `~\`) {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		if expanded == "~" {
			return home, nil
		}
		return filepath.Join(home, expanded[2:]), nil
	}

	return expanded, nil
}

// ExpandPath expands environment variables and a leading "~" to user home.
// It supports "~", "~/" and "~\" prefixes.
func ExpandPath(path string) (string, error) {
	return ExpandPathWithEnv(path, nil)
}

func ExpandAbsPath(path string) (string, error) {
	expanded, err := ExpandPathWithEnv(path, nil)
	if err != nil {
		return "", err
	}
	return filepath.Abs(expanded)
}

// EnvKey normalizes environment variable names for the current platform.
// Windows names are case-insensitive; Unix names are preserved.
func EnvKey(key string) string {
	if runtime.GOOS == "windows" {
		return strings.ToUpper(key)
	}
	return key
}
