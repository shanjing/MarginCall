#!/usr/bin/env bash
# MarginCall venv activation banner: summary + stock chart figure.
# Sourced from .venv/bin/activate after install_venv_banner.sh is run.

[ -z "${VIRTUAL_ENV:-}" ] && return 0

# Project root: parent of .venv
_MC_PROJECT_ROOT="${VIRTUAL_ENV%/.venv}"
[ "$_MC_PROJECT_ROOT" = "$VIRTUAL_ENV" ] && _MC_PROJECT_ROOT="$(cd "$(dirname "$VIRTUAL_ENV")" && pwd)"

# AI model from .env (CLOUD_AI_MODEL preferred, else LOCAL_AI_MODEL)
_MC_AI_MODE=""
_MC_ENV_FILE="${_MC_PROJECT_ROOT}/.env"
if [ -f "$_MC_ENV_FILE" ]; then
  _MC_AI_MODE=$(grep -E '^CLOUD_AI_MODEL=' "$_MC_ENV_FILE" 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d '\r')
  if [ -z "$_MC_AI_MODE" ]; then
    _MC_AI_MODE=$(grep -E '^LOCAL_AI_MODEL=' "$_MC_ENV_FILE" 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d '\r')
    [ -n "$_MC_AI_MODE" ] && _MC_AI_MODE="local: $_MC_AI_MODE"
  fi
fi
[ -z "$_MC_AI_MODE" ] && _MC_AI_MODE="(not set in .env)"

printf '\n'
printf '  MarginCall — DiamondHands 💎🙌 Entertainment\n'
printf '  AI mode: %s\n' "$_MC_AI_MODE"
printf '  CWD: %s\n' "${PWD:-$(pwd)}"
printf '\n'
# Block-character line of hills (rising with gentle ups and downs)
printf '              ██\n'
printf '            ██  ██\n'
printf '      ██  ██      ██\n'
printf '    ██              ██\n'
printf '  ██\n'
printf '██\n'
printf '\n'

unset _MC_PROJECT_ROOT _MC_AI_MODE _MC_ENV_FILE
