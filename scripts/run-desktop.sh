#!/usr/bin/env bash
set -euo pipefail
CC_REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$CC_REPO_ROOT"
exec "${CYBER_COMPANION_PYTHON:-python3}" -m cyber_companion.launch "$@"
