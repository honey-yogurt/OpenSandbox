---
title: File Policy
description: Restrict sandbox file uploads and downloads to authorized directories.
---

# File Policy

`filePolicy` constrains the execd file-transfer APIs at creation time. It is an
additional sandbox-layer control; it does not replace application authorization
or sandbox filesystem permissions.

```json
{
  "image": { "uri": "python:3.11" },
  "resourceLimits": { "cpu": "500m", "memory": "512Mi" },
  "entrypoint": ["python", "/app/main.py"],
  "filePolicy": {
    "downloadRoots": ["/workspace/output"],
    "uploadRoots": ["/workspace/input"]
  }
}
```

- `downloadRoots` and `uploadRoots` are independent allowlists of absolute
  paths inside the sandbox.
- Ordinary and filesystem-identity download/upload requests resolve symlinks
  before comparing the target with a configured root.
- Isolated-session file APIs enforce the same roots against their absolute
  overlay paths.
- A request outside the configured roots returns `403 FORBIDDEN`.
- An empty list denies the corresponding transfer direction.
- Omitting `filePolicy` preserves the legacy unrestricted behavior and emits a
  security warning in execd logs.

::: warning
For production data sandboxes, explicitly configure both roots and ensure the
business layer does not request unrestricted legacy mode.
:::
