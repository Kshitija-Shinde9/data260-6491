#!/usr/bin/env bash
# HW9 Part 4 - two agents, lessons, and the four test variants.
#   bash scripts/setup_hw09_part4.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$REPO/code/web_application"
VENV="$REPO/.venv"

step() { printf '\n==> %s\n' "$1"; }
die() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

step "Checking Ollama"
ollama_tags="$(curl -sf http://127.0.0.1:11434/api/tags || true)"
[ -n "$ollama_tags" ] || die "Ollama is not answering on port 11434. Open the Ollama app."
case "$ollama_tags" in
  *'"qwen3:8b"'*) echo "qwen3:8b is available" ;;
  *) die "qwen3:8b is not pulled. Run: ollama pull qwen3:8b" ;;
esac

step "Python environment"
if [ ! -x "$VENV/bin/python" ]; then
  python_bin="$(command -v python3.12 || command -v python3.11 || command -v python3)"
  "$python_bin" -m venv "$VENV"
fi
PY="$VENV/bin/python"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "$WEB/requirements.txt"
echo "packages installed"

step "Running HW9 Part 4"
cd "$REPO"
"$PY" scripts/run_hw09_part4.py
