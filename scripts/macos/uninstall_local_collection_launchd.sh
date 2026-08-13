#!/usr/bin/env bash
# Idempotent uninstaller for local collection launchd job.

set -euo pipefail

LABEL="${ZEROREALM_LAUNCHD_LABEL:-com.zerorealm.local-collection}"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${AGENTS_DIR}/${LABEL}.plist"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "${TARGET_PLIST}" 2>/dev/null || true

if [[ -f "${TARGET_PLIST}" ]]; then
  rm -f "${TARGET_PLIST}"
  echo "removed: ${TARGET_PLIST}"
else
  echo "not installed: ${TARGET_PLIST}"
fi
