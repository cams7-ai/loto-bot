#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname "$(realpath "$0")")/aws_linux.py" stop --ip-version 4 "$@"
