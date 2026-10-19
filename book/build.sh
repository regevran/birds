#!/usr/bin/env bash
# Build the A5 pocket edition and its cover.
# Outputs land in out/book/; the A4 sheets are untouched.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 book/make_pocket.py "$@"
python3 book/make_cover.py
