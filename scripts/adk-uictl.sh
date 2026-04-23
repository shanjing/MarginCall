#!/usr/bin/env bash
set -euo pipefail

# ADK UI lifecycle manager for MarginCall.
# Commands:
#   start            Start ADK web UI in background
#   kill             Stop ADK web UI
#   restart          Restart ADK web UI
#   status           Show ADK web UI status
#
# Options:
#   -k               Sure-kill mode (force kill process tree and listeners)
#   -p <port>        UI port (default: 8000)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_ACTIVATE="${PROJECT_ROOT}/.venv/bin/activate"
RUNTIME_DIR="${PROJECT_ROOT}/.tmp"
PID_FILE="${RUNTIME_DIR}/adk-ui.pid"
LOG_FILE="${RUNTIME_DIR}/adk-ui.log"
UI_URL_TEMPLATE="http://127.0.0.1:%s"

PORT=8000
SURE_KILL=0
COMMAND=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [-k] [-p PORT] {start|kill|restart|status}

Examples:
  $(basename "$0") start
  $(basename "$0") kill
  $(basename "$0") -k kill
  $(basename "$0") -k restart
EOF
}

log() {
  printf '[adk-uictl] %s\n' "$*"
}

open_ui_in_browser() {
  local ui_url
  ui_url="$(printf "${UI_URL_TEMPLATE}" "${PORT}")"

  if command -v open >/dev/null 2>&1; then
    if open -na "Google Chrome" --args --new-tab "${ui_url}" >/dev/null 2>&1; then
      log "Opened browser tab: ${ui_url}"
      return 0
    fi

    if open "${ui_url}" >/dev/null 2>&1; then
      log "Opened browser tab: ${ui_url}"
      return 0
    fi
  fi

  log "UI started, but could not auto-open browser. Open manually: ${ui_url}"
}

ensure_runtime_dir() {
  mkdir -p "${RUNTIME_DIR}"
}

pid_exists() {
  local pid="$1"
  kill -0 "${pid}" 2>/dev/null
}

children_of_pid() {
  local parent_pid="$1"
  local kids
  kids="$(ps -eo pid=,ppid= 2>/dev/null | awk -v p="${parent_pid}" '$2 == p {print $1}')"
  for kid in ${kids}; do
    echo "${kid}"
    children_of_pid "${kid}"
  done
}

collect_candidate_pids() {
  local pids=()

  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(tr -d '[:space:]' < "${PID_FILE}")"
    if [[ -n "${pid}" && "${pid}" =~ ^[0-9]+$ ]] && pid_exists "${pid}"; then
      pids+=("${pid}")
    fi
  fi

  # Any process currently listening on the UI port.
  while read -r pid; do
    [[ -n "${pid}" ]] && pids+=("${pid}")
  done < <(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)

  # Unique/sorted list.
  if ((${#pids[@]} == 0)); then
    return 0
  fi

  printf '%s\n' "${pids[@]}" | awk '/^[0-9]+$/' | sort -u
}

expand_process_tree() {
  local pid
  for pid in "$@"; do
    echo "${pid}"
    children_of_pid "${pid}"
  done | awk '/^[0-9]+$/' | sort -u
}

wait_for_exit() {
  local timeout_secs="$1"
  shift
  local pids=("$@")
  local i
  for ((i = 0; i < timeout_secs; i++)); do
    local alive=0
    local pid
    for pid in "${pids[@]}"; do
      if pid_exists "${pid}"; then
        alive=1
        break
      fi
    done
    if ((alive == 0)); then
      return 0
    fi
    sleep 1
  done
  return 1
}

kill_ui() {
  local base_pids
  base_pids="$(collect_candidate_pids || true)"

  if [[ -z "${base_pids}" ]]; then
    log "No running ADK UI process found."
    rm -f "${PID_FILE}"
    return 0
  fi

  local all_pids=()
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] && all_pids+=("${pid}")
  done <<EOF
$(expand_process_tree ${base_pids})
EOF
  if ((${#all_pids[@]} == 0)); then
    log "No live processes to stop."
    rm -f "${PID_FILE}"
    return 0
  fi

  log "Stopping ADK UI process tree: ${all_pids[*]}"
  kill -TERM "${all_pids[@]}" 2>/dev/null || true

  if ! wait_for_exit 10 "${all_pids[@]}"; then
    if ((SURE_KILL == 1)); then
      log "Sure-kill enabled: forcing process termination and resource release."
      kill -KILL "${all_pids[@]}" 2>/dev/null || true

      # Final pass: force-kill any remaining listeners on the UI port.
      local port_pids=()
      while IFS= read -r pid; do
        [[ -n "${pid}" ]] && port_pids+=("${pid}")
      done <<EOF
$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)
EOF
      if ((${#port_pids[@]} > 0)); then
        log "Force-killing remaining listeners on port ${PORT}: ${port_pids[*]}"
        kill -KILL "${port_pids[@]}" 2>/dev/null || true
      fi
    else
      log "Processes still alive. Re-run with -k for sure-kill."
      return 1
    fi
  fi

  rm -f "${PID_FILE}"
  # In sure-kill mode we also reset old runtime output.
  if ((SURE_KILL == 1)); then
    rm -f "${LOG_FILE}"
  fi
  log "ADK UI stopped."
}

start_ui() {
  ensure_runtime_dir

  if [[ ! -f "${VENV_ACTIVATE}" ]]; then
    log "Virtualenv activation script not found: ${VENV_ACTIVATE}"
    exit 1
  fi

  # Clean up stale state first.
  if collect_candidate_pids >/dev/null && [[ -n "$(collect_candidate_pids || true)" ]]; then
    log "ADK UI appears to be running; stopping existing process first."
    kill_ui
  fi

  log "Starting ADK UI on http://127.0.0.1:${PORT}"
  (
    cd "${PROJECT_ROOT}"
    source "${VENV_ACTIVATE}"
    exec adk web --port "${PORT}"
  ) >>"${LOG_FILE}" 2>&1 &

  local pid=$!
  echo "${pid}" > "${PID_FILE}"

  # Wait for UI to become reachable.
  local retries=20
  local i
  for ((i = 1; i <= retries; i++)); do
    if curl -fsS "http://127.0.0.1:${PORT}/list-apps" >/dev/null 2>&1; then
      log "ADK UI started (pid ${pid}). Log: ${LOG_FILE}"
      open_ui_in_browser
      return 0
    fi
    sleep 1
  done

  log "UI did not become healthy in time; stopping startup process."
  kill_ui || true
  exit 1
}

status_ui() {
  local ai_model db_path ui_running
  local pids
  ai_model="$(resolve_ai_model)"
  db_path="$(resolve_session_db_path)"
  pids="$(collect_candidate_pids || true)"
  ui_running=0

  if [[ -n "${pids}" ]]; then
    ui_running=1
    log "ADK UI is running on port ${PORT}."
    printf '%s\n' "${pids}" | awk '{print "  pid: "$1}'
    if [[ -f "${PID_FILE}" ]]; then
      log "PID file: ${PID_FILE} ($(tr -d '[:space:]' < "${PID_FILE}"))"
    fi
  else
    log "ADK UI is not running on port ${PORT}."
    if [[ -f "${PID_FILE}" ]]; then
      log "Removing stale PID file: ${PID_FILE}"
      rm -f "${PID_FILE}"
    fi
  fi

  log "LLM model: ${ai_model}"
  print_session_activity "${db_path}" "${ui_running}"
}

resolve_ai_model() {
  local env_file cloud_model local_model
  env_file="${PROJECT_ROOT}/.env"
  cloud_model=""
  local_model=""

  if [[ -f "${env_file}" ]]; then
    cloud_model="$(awk -F= '/^CLOUD_AI_MODEL=/{sub(/^["'\'']/, "", $2); sub(/["'\'']$/, "", $2); print $2; exit}' "${env_file}" 2>/dev/null || true)"
    if [[ -n "${cloud_model}" ]]; then
      echo "${cloud_model}"
      return 0
    fi

    local_model="$(awk -F= '/^LOCAL_AI_MODEL=/{sub(/^["'\'']/, "", $2); sub(/["'\'']$/, "", $2); print $2; exit}' "${env_file}" 2>/dev/null || true)"
    if [[ -n "${local_model}" ]]; then
      echo "local: ${local_model}"
      return 0
    fi
  fi

  echo "(not set)"
}

resolve_session_db_path() {
  if [[ -f "${PROJECT_ROOT}/sessions.db" ]]; then
    echo "${PROJECT_ROOT}/sessions.db"
    return 0
  fi

  if [[ -f "${PROJECT_ROOT}/MarginCall_sessions.db" ]]; then
    echo "${PROJECT_ROOT}/MarginCall_sessions.db"
    return 0
  fi

  echo ""
}

print_session_activity() {
  local db_path="$1"
  local ui_running="${2:-0}"
  local inflight_output recent_sessions active_agents

  if ! command -v sqlite3 >/dev/null 2>&1; then
    log "Active sessions: sqlite3 not available."
    return 0
  fi

  if [[ -z "${db_path}" ]]; then
    log "Active sessions: no sessions database found."
    return 0
  fi

  if [[ ! -f "${db_path}" ]]; then
    log "Active sessions: missing database ${db_path}."
    return 0
  fi

  log "Session DB: ${db_path}"

  if [[ "${ui_running}" != "1" ]]; then
    log "Active LLM turns (in-flight): unavailable (UI not running)"
  else
    inflight_output="$(sqlite3 -noheader "${db_path}" "SELECT app_name || '|' || user_id || '|' || session_id || '|' || COALESCE(invocation_id,'') || '|' || COALESCE(MAX(timestamp),'') || '|' || COUNT(*) FROM events WHERE COALESCE(turn_complete, 0) = 0 AND timestamp >= datetime('now','-6 hours') GROUP BY app_name, user_id, session_id, COALESCE(invocation_id,'') ORDER BY MAX(timestamp) DESC LIMIT 10;" 2>/dev/null || true)"
    if [[ -n "${inflight_output}" ]]; then
      log "Active LLM turns (in-flight, last 6h):"
      printf '%s\n' "${inflight_output}" | awk -F'|' '{printf "  app=%s user=%s session=%s invocation=%s last_ts=%s open_events=%s\n",$1,$2,$3,$4,$5,$6}'
    else
      log "Active LLM turns (in-flight, last 6h): none"
    fi
  fi

  recent_sessions="$(sqlite3 -noheader "${db_path}" "SELECT app_name || '|' || user_id || '|' || id || '|' || COALESCE(update_time,'') FROM sessions WHERE update_time >= datetime('now','-60 minutes') ORDER BY update_time DESC LIMIT 10;" 2>/dev/null || true)"
  if [[ -n "${recent_sessions}" ]]; then
    log "Recently active sessions (last 60m):"
    printf '%s\n' "${recent_sessions}" | awk -F'|' '{printf "  app=%s user=%s session=%s updated=%s\n",$1,$2,$3,$4}'
  else
    log "Recently active sessions (last 60m): none"
  fi

  active_agents="$(sqlite3 -noheader "${db_path}" "SELECT author || '|' || COUNT(*) FROM events WHERE timestamp >= datetime('now','-60 minutes') AND COALESCE(author,'') != '' GROUP BY author ORDER BY COUNT(*) DESC LIMIT 10;" 2>/dev/null || true)"
  if [[ -n "${active_agents}" ]]; then
    log "Active agents/authors in last 60m:"
    printf '%s\n' "${active_agents}" | awk -F'|' '{printf "  %s (%s events)\n",$1,$2}'
  else
    log "Active agents/authors in last 60m: none"
  fi
}

while getopts ":kp:h" opt; do
  case "${opt}" in
    k) SURE_KILL=1 ;;
    p) PORT="${OPTARG}" ;;
    h)
      usage
      exit 0
      ;;
    :)
      log "Option -${OPTARG} requires an argument."
      usage
      exit 1
      ;;
    \?)
      log "Unknown option: -${OPTARG}"
      usage
      exit 1
      ;;
  esac
done
shift $((OPTIND - 1))

COMMAND="${1:-}"
if [[ -z "${COMMAND}" ]]; then
  usage
  exit 1
fi

case "${COMMAND}" in
  start)
    start_ui
    ;;
  kill)
    kill_ui
    ;;
  restart)
    kill_ui || true
    start_ui
    ;;
  status)
    status_ui
    ;;
  *)
    log "Unknown command: ${COMMAND}"
    usage
    exit 1
    ;;
esac
