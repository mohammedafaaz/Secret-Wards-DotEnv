#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -x .venv312/bin/python ] && .venv312/bin/python -c 'import sys; assert (3,12)<=sys.version_info[:2]<=(3,14)' >/dev/null 2>&1; then
 exec .venv312/bin/python start_shield.py "$@"
fi
for p in python3.12 python3.13 python3.14 python3; do
 if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; assert (3,12)<=sys.version_info[:2]<=(3,14)' >/dev/null 2>&1; then exec "$p" start_shield.py "$@"; fi
done
printf '%s\n' 'Python 3.12+ is required.' >&2
exit 1
