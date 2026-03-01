#!/usr/bin/env bash
# Wrapper — actual script lives in scripts/run_all.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/run_all.sh" "$@"
