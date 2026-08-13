#!/usr/bin/env bash
# Idempotent installer: render plist with absolute repo paths into LaunchAgents.
# Does not run collection. Safe to re-run.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="${ZEROREALM_LAUNCHD_LABEL:-com.zerorealm.local-collection}"
TEMPLATE="${ROOT}/scripts/macos/com.zerorealm.local-collection.plist.template"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${AGENTS_DIR}/${LABEL}.plist"
RENDERED="${ROOT}/logs/local_collection/${LABEL}.plist.rendered"

if [[ ! -f "${TEMPLATE}" ]]; then
  echo "missing template: ${TEMPLATE}" >&2
  exit 1
fi

mkdir -p "${AGENTS_DIR}" "${ROOT}/logs/local_collection"

ESCAPED_ROOT="$(printf '%s' "${ROOT}" | sed -e 's/[\/&]/\\&/g')"
ESCAPED_LABEL="$(printf '%s' "${LABEL}" | sed -e 's/[\/&]/\\&/g')"

sed \
  -e "s/__REPO_ROOT__/${ESCAPED_ROOT}/g" \
  -e "s/__LABEL__/${ESCAPED_LABEL}/g" \
  "${TEMPLATE}" >"${RENDERED}"

cp "${RENDERED}" "${TARGET_PLIST}"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${TARGET_PLIST}" 2>/dev/null || \
  launchctl load "${TARGET_PLIST}"

echo "installed: ${TARGET_PLIST}"
echo "role: local supplement (RunAtLoad on boot + daily 23:00); GitHub Actions remains primary"
echo "schedule: RunAtLoad + daily 23:00 (Mac local TZ; prefer Asia/Shanghai)"
echo "program: ${ROOT}/scripts/run_local_collection.sh"
echo "rendered copy: ${RENDERED}"
