#!/usr/bin/env bash
# Wrapper — actual script lives in scripts/verify_local.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify_local.sh" "$@"
