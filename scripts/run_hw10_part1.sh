#!/bin/sh
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
else
  PY=python3
fi
exec "$PY" -m streamlit run code/ops_dashboard/app.py --server.port 8501
