#!/usr/bin/env bash
# Fetch a web page via Jina Reader and cache it as a dated markdown snapshot.
# Re-uses the cache: if the slug is already saved, prints the cached path and does NOT re-pull.
# Usage: fetch_source.sh <slug> <url>
#   slug: short filename-safe id (e.g. mcl-168-499)
# Jina key is read at call time from the sibling factchecking_with_LLMs/src/.env (never copied here).
set -euo pipefail
SLUG="${1:?slug required}"; URL="${2:?url required}"
CACHE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/source_cache"
mkdir -p "$CACHE"
OUT="$CACHE/$SLUG.md"
if [ -s "$OUT" ]; then echo "$OUT (cached)"; exit 0; fi
ENV_FILE="${CHURVEY_ENV:-$(dirname "$0")/../.env}"
KEY="$(grep -E '^JINA_API_KEY=' "$ENV_FILE" | cut -d= -f2-)"
BODY="$(curl -s -H "Authorization: Bearer $KEY" -H "X-Return-Format: markdown" -H "X-Retain-Images: none" "https://r.jina.ai/$URL")"
FETCHED="$(date +%Y-%m-%d 2>/dev/null || echo unknown)"
{ echo "<!-- source-snapshot"; echo "url: $URL"; echo "fetched: $FETCHED via Jina Reader (r.jina.ai)"; echo "-->"; echo; printf '%s\n' "$BODY"; } > "$OUT"
echo "$OUT (pulled)"
