#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo 'Python 3.11 or newer is required.' >&2
    exit 1
  fi
  if ! python3 -m venv --without-pip .venv; then
    echo 'Could not create .venv. Check that the Python venv module is installed.' >&2
    exit 1
  fi
fi
if ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo 'The project .venv is incomplete or does not run Python 3.11+.' >&2
  exit 1
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo 'pip is missing. Restoring it with the bundled ensurepip module...'
  if ! .venv/bin/python -m ensurepip --upgrade --default-pip; then
    echo 'Could not restore pip. Repair Python with ensurepip/venv support.' >&2
    exit 1
  fi
fi
if ! .venv/bin/python -m pip install -r backend/requirements.txt; then
  echo 'Dependency installation failed. Check the pip error above and your Internet connection.' >&2
  exit 1
fi
exec .venv/bin/python start.py --demo
