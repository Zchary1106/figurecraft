#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python=""
if [[ -n "${FIGURECRAFT_PYTHON:-}" ]]; then
    candidates=("$FIGURECRAFT_PYTHON")
else
    candidates=(python3 python3.13 python3.12 python3.11 python)
fi
for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        python="$candidate"
        break
    fi
done
if [[ -z "$python" ]]; then
    printf '%s\n' 'FigureCraft needs Python 3.11+. Install it from python.org, then retry.' >&2
    exit 1
fi
exec "$python" "$script_dir/install.py" --setup --scope user --agent all "$@"
