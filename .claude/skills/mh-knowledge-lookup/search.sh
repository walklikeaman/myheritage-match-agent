#!/usr/bin/env bash
# Local pass over project knowledge: wiki (minus generated people pages), docs, loops,
# Context brief, shared project notes, graph report.
# Usage: search.sh 'term1|term2'
set -uo pipefail
TERMS="${1:?usage: search.sh 'term1|term2'}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1
echo "== wiki/index.md"; grep -E -i -n "$TERMS" wiki/index.md 2>/dev/null | head -20
echo "== pages"; grep -E -i -l -r --exclude-dir=people "$TERMS" wiki docs Context CLAUDE.md AGENTS.md 2>/dev/null | head -30
echo "== wiki/people (names only)"; grep -E -i -l -r "$TERMS" wiki/people 2>/dev/null | head -10
echo "== wiki/log.md"; grep -E -i -n "$TERMS" wiki/log.md 2>/dev/null | grep '^[0-9]*:## \[' | head -20
echo "== .loops"; grep -E -i -n -r "$TERMS" .loops 2>/dev/null | head -10
if [ -d /mnt/project-files ]; then
  echo "== /mnt/project-files (md)"
  find /mnt/project-files/ -maxdepth 3 -name '*.md' -not -path '*/My Heritage/wiki/*' -print0 2>/dev/null \
    | xargs -0 grep -E -i -l "$TERMS" 2>/dev/null | head -20
fi
if [ -f graphify-out/GRAPH_REPORT.md ]; then
  echo "== graphify-out/GRAPH_REPORT.md"; grep -E -i -n "$TERMS" graphify-out/GRAPH_REPORT.md | head -10
fi
