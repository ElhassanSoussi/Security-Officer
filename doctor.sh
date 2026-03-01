#!/usr/bin/env bash
# Wrapper — actual script lives in scripts/doctor.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/doctor.sh" "$@"
