#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

FORMATTER=${CLANG_FORMAT:-clang-format}
if ! command -v "$FORMATTER" >/dev/null 2>&1; then
    echo "clang-format 18.1.8 is required (or set CLANG_FORMAT)" >&2
    exit 2
fi

version=$($FORMATTER --version)
case "$version" in
    *"version 18.1.8"*) ;;
    *) echo "expected clang-format 18.1.8, got: $version" >&2; exit 2 ;;
esac

mapfile_compat() {
    while IFS= read -r path; do
        [ -n "$path" ] && SOURCES+=("$path")
    done
}

SOURCES=()
mapfile_compat < <(
    find main components -type f \( -name '*.c' -o -name '*.h' \) \
        ! -path '*/generated/*' ! -path '*/managed_components/*' | sort
)

if [ "${1:-}" = "--check" ]; then
    "$FORMATTER" --dry-run --Werror "${SOURCES[@]}"
else
    "$FORMATTER" -i "${SOURCES[@]}"
fi
