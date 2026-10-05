#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf '%s\n' 'This folder is not a Git working copy. Use git clone or the GitHub website instructions.'
  exit 1
fi
if [[ ! -f .gitignore ]]; then
  printf '%s\n' 'Copy the provided .gitignore to the project root first.'
  exit 1
fi
git rm -r --cached --ignore-unmatch -- backend/easystock/__pycache__
git rm --cached --ignore-unmatch -- database/easystock.db database/easystock.db-wal database/easystock.db-shm
printf '%s\n' 'Cleanup staged. Local database and cache files were kept.'
git status --short
printf '%s\n' 'Next: git add .gitignore README.md docs scripts' 'Then: git diff --cached --stat' 'Then: git commit -m "Update reports and clean repository"' 'Then: git push origin main'
