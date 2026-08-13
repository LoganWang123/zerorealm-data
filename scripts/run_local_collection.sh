#!/usr/bin/env bash
# Local daily collection only: crawl + rule clean + digest.
# Never calls generate_daily / publish / git push / cursor-agent / agy / external LLM APIs.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STATUS_DIR="${ROOT}/logs/local_collection"
LOCK_DIR="${STATUS_DIR}/run.lock"
STATUS_FILE="${STATUS_DIR}/latest_status.json"
HANDOFF_FILE="${STATUS_DIR}/latest_handoff.md"
SCHEMA_VERSION=1

mkdir -p "$STATUS_DIR"

DATE="${LOCAL_COLLECTION_DATE:-}"
if [[ -z "${DATE}" ]]; then
  if [[ "${1:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    DATE="$1"
  else
    DATE="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
  fi
fi

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
else
  PYTHON="$(command -v python3 || command -v python)"
fi

RUN_LOG="${STATUS_DIR}/run_${DATE}.log"
STARTED_AT="$(TZ=Asia/Shanghai date -Iseconds)"

# Strip generation / publish / remote-store credentials from this process.
# Timed collection must never call project DeepSeek/OpenAI/Anthropic/Gemini/Agnes APIs.
unset LLM_API_KEY \
  DEEPSEEK_API_KEY \
  OPENAI_API_KEY \
  ANTHROPIC_API_KEY \
  GEMINI_API_KEY \
  AGNES_API_KEY \
  ANYSEARCH_API_KEY \
  WECHAT_APPID \
  WECHAT_SECRET \
  WEBSITE_REPO_TOKEN \
  SUPABASE_URL \
  SUPABASE_KEY \
  CONTENT_GENERATOR_ALLOW_LIVE \
  ZEROREALM_LOCAL_IMAGE_CMD || true

write_status() {
  local status="$1"
  local exit_code="$2"
  local finished_at="$3"
  local message="${4:-}"
  local digest_hint="data/digest/$(printf '%s' "${DATE}" | tr '-' '/')"
  local finished_json="null"
  if [[ -n "${finished_at}" ]]; then
    finished_json=$("${PYTHON}" -c 'import json,sys; print(json.dumps(sys.argv[1]))' "${finished_at}")
  fi
  local message_json
  message_json=$("${PYTHON}" -c 'import json,sys; print(json.dumps(sys.argv[1]))' "${message}")
  local python_json
  python_json=$("${PYTHON}" -c 'import json,sys; print(json.dumps(sys.argv[1]))' "${PYTHON}")
  cat >"${STATUS_FILE}.tmp" <<EOF
{
  "schema_version": ${SCHEMA_VERSION},
  "mode": "local-only",
  "status": "${status}",
  "date": "${DATE}",
  "started_at": "${STARTED_AT}",
  "finished_at": ${finished_json},
  "exit_code": ${exit_code},
  "python": ${python_json},
  "command": ["main.py", "--local-only", "--date", "${DATE}"],
  "log_path": "logs/local_collection/run_${DATE}.log",
  "status_path": "logs/local_collection/latest_status.json",
  "handoff_path": "logs/local_collection/latest_handoff.md",
  "data_dir": "data",
  "digest_hint": "${digest_hint}",
  "message": ${message_json},
  "forbidden_in_this_job": [
    "generate_daily.py",
    "publish.py",
    "run_daily.py",
    "git push",
    "cursor-agent",
    "agy",
    "external_llm_api"
  ],
  "next_llm_work": {
    "delivery": "/Users/Logan/AICoding/ZeroRealmAI/scripts/ai-delivery.sh zerorealm-data",
    "cursor_model": "auto",
    "antigravity_model": "gemini-3.6-flash-medium",
    "images": "Antigravity only"
  }
}
EOF
  mv "${STATUS_FILE}.tmp" "${STATUS_FILE}"
}

write_handoff() {
  local status="$1"
  local exit_code="$2"
  local finished_at="$3"
  cat >"${HANDOFF_FILE}.tmp" <<EOF
# Local collection handoff

- mode: local-only
- status: ${status}
- date: ${DATE}
- started_at: ${STARTED_AT}
- finished_at: ${finished_at}
- exit_code: ${exit_code}
- python: ${PYTHON}
- command: \`main.py --local-only --date ${DATE}\`
- log: \`logs/local_collection/run_${DATE}.log\`
- status_json: \`logs/local_collection/latest_status.json\`
- local outputs: \`data/\` (raw / clean / digest) and \`logs/\`
- this job does **not** generate daily reports, images, publish, push, or draft WeChat

## Next (manual LLM via IDE tools only)

\`\`\`bash
/Users/Logan/AICoding/ZeroRealmAI/scripts/ai-delivery.sh zerorealm-data "<task>"
\`\`\`

- Cursor implementation model: \`auto\`
- Antigravity acceptance / images: \`gemini-3.6-flash-medium\`
- Bitmap images: Antigravity only (not this script, not project LLM APIs)
EOF
  mv "${HANDOFF_FILE}.tmp" "${HANDOFF_FILE}"
}

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  FINISHED_AT="$(TZ=Asia/Shanghai date -Iseconds)"
  write_status "locked" 75 "${FINISHED_AT}" "Another local collection run holds the lock"
  write_handoff "locked" 75 "${FINISHED_AT}"
  echo "[local-collection] locked: ${LOCK_DIR}" >&2
  exit 75
fi

cleanup() {
  rmdir "${LOCK_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

write_status "running" 0 "" "collection in progress"
write_handoff "running" 0 ""

{
  echo "[local-collection] mode=local-only date=${DATE} started_at=${STARTED_AT}"
  echo "[local-collection] python=${PYTHON}"
  echo "[local-collection] invoking: main.py --local-only --date ${DATE}"
} | tee -a "${RUN_LOG}"

set +e
"${PYTHON}" "${ROOT}/main.py" --local-only --date "${DATE}" 2>&1 | tee -a "${RUN_LOG}"
EXIT_CODE=${PIPESTATUS[0]}
set -e

FINISHED_AT="$(TZ=Asia/Shanghai date -Iseconds)"
if [[ "${EXIT_CODE}" -eq 0 ]]; then
  write_status "ok" 0 "${FINISHED_AT}" "local collection completed"
  write_handoff "ok" 0 "${FINISHED_AT}"
  echo "[local-collection] ok date=${DATE}" | tee -a "${RUN_LOG}"
else
  write_status "error" "${EXIT_CODE}" "${FINISHED_AT}" "main.py exited non-zero"
  write_handoff "error" "${EXIT_CODE}" "${FINISHED_AT}"
  echo "[local-collection] error exit_code=${EXIT_CODE}" | tee -a "${RUN_LOG}"
fi

exit "${EXIT_CODE}"
