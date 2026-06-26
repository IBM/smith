# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})
