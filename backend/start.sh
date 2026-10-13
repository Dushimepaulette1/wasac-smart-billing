#!/bin/sh
# Container start: fetch the model weights, then start the API.
# Never use "set -x" or print the environment here: MODEL_URLS holds private links.
# download_models.py logs only file names and "failed"; if it fails, the API still starts and
# /health lists the missing models (/submit-photo then offers manual entry).
set -u

if python scripts/download_models.py; then
  echo "Model weights ready."
else
  echo "Model weights incomplete: starting anyway. See /health."
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-7860}" --workers 1
