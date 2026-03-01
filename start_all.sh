#!/usr/bin/env bash
# Wrapper — actual script lives in scripts/start_all.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/start_all.sh" "$@"
