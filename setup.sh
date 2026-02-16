#!/bin/bash
# Setup script for macOS and Linux. On Windows, run: powershell -ExecutionPolicy Bypass -File setup.ps1
set -e

OS="$(uname -s)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# On Windows (Git Bash / MSYS / Cygwin), direct to PowerShell script
case "$OS" in
  MINGW*|MSYS*|CYGWIN*)
    echo "On Windows, run instead: powershell -ExecutionPolicy Bypass -File setup.ps1"
    exit 1
    ;;
esac

# Colors and style (OpenClaw-inspired)
R='\033[0;31m'
G='\033[0;32m'
W='\033[1;37m'
D='\033[0;90m'
N='\033[0m'

# --- Environment check (run first) ---
check_venv() {
  [[ -d .venv ]]
}
check_env_file() {
  [[ -f .env ]]
}
# API key: when cloud model set, GOOGLE_API_KEY must be set and not placeholder; when local only, N/A
check_api_key() {
  if [[ ! -f .env ]]; then
    return 1
  fi
  CLOUD_MODEL=$(grep -E '^CLOUD_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  GOOGLE_KEY=$(grep -E '^GOOGLE_API_KEY=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  LOCAL_MODEL=$(grep -E '^LOCAL_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  KEY_PLACEHOLDER="Google AI Studio API Key"
  if [[ -n "$CLOUD_MODEL" ]]; then
    [[ -n "$GOOGLE_KEY" && "$GOOGLE_KEY" != "$KEY_PLACEHOLDER" ]]
    return
  fi
  # Local only: no API key required
  [[ -n "$LOCAL_MODEL" ]]
}

# Model configured: CLOUD_AI_MODEL or LOCAL_AI_MODEL set in .env
check_model_configured() {
  if [[ ! -f .env ]]; then
    return 1
  fi
  CLOUD_MODEL=$(grep -E '^CLOUD_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  LOCAL_MODEL=$(grep -E '^LOCAL_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  [[ -n "$CLOUD_MODEL" || -n "$LOCAL_MODEL" ]]
}

# Echo which model is configured (for display after "All checks passed")
get_model_display() {
  if [[ ! -f .env ]]; then
    return
  fi
  CLOUD_MODEL=$(grep -E '^CLOUD_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  LOCAL_MODEL=$(grep -E '^LOCAL_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  if [[ -n "$CLOUD_MODEL" ]]; then
    printf "  Model ${G}%s${N}\n" "$CLOUD_MODEL"
  elif [[ -n "$LOCAL_MODEL" ]]; then
    printf "  Model ${G}local (%s)${N}\n" "$LOCAL_MODEL"
  fi
}

# Cloud-only: API key + CLOUD_AI_MODEL set (for pre-exit test)
check_cloud_configured() {
  if [[ ! -f .env ]]; then
    return 1
  fi
  CLOUD_MODEL=$(grep -E '^CLOUD_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  GOOGLE_KEY=$(grep -E '^GOOGLE_API_KEY=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  KEY_PLACEHOLDER="Google AI Studio API Key"
  [[ -n "$CLOUD_MODEL" && -n "$GOOGLE_KEY" && "$GOOGLE_KEY" != "$KEY_PLACEHOLDER" ]]
}

# Local-only: LOCAL_AI_MODEL set (for pre-exit test)
check_local_configured() {
  if [[ ! -f .env ]]; then
    return 1
  fi
  LOCAL_MODEL=$(grep -E '^LOCAL_AI_MODEL=' .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//" | tr -d "'\"")
  [[ -n "$LOCAL_MODEL" ]]
}

# Discard any input already buffered in the terminal (e.g. keypresses during pip install).
# Only runs when stdin is a tty. Call before the first read after a non-interactive block.
drain_stdin() {
  [[ ! -t 0 ]] && return
  # Read with 1s timeout until no input (drains buffer; add at most ~1s after install)
  while read -r -t 1 2>/dev/null; do :; done
}

run_main_test() {
  (source .venv/bin/activate && python -m main run -i "what is GOOGL's next earning release date")
}

# Run quick test (assumes model is configured). Used when user says y to "Test the agent quickly?"
run_quick_test() {
  echo ""
  if check_cloud_configured; then
    printf "${R}--- Running quick test (cloud model), this will take up to 60 seconds... ---${N}\n"
  elif check_local_configured; then
    printf "${R}--- Running quick test (local model), this will take up to 3 minutes...  ---${N}\n"
  else
    printf "${R}--- Running quick test, this will take up to 3 minutes... ---${N}\n"
  fi
  printf "  ${D}python -m main run -i \"what is GOOGL's next earning release date\"${N}\n"
  exec 3<&0
  exec 0</dev/null
  run_main_test
  exec 0<&3 3<&-
}

# Run test or ensure model configured. Return 0 if test ran, 1 if no model (caller may run run_model_selection).
run_exit_test() {
  if check_cloud_configured; then
    run_quick_test
    return 0
  fi
  if check_local_configured; then
    run_quick_test
    return 0
  fi
  printf "${R}You must set up a model (cloud or local).${N}\n"
  return 1
}

start_agent() {
  printf "${G}✓${N} Starting UI at ${G}http://localhost:8080${N}\n"
  (source .venv/bin/activate && uvicorn server:app --host 0.0.0.0 --port 8080) &
  UVICORN_PID=$!
  printf "  ${D}Waiting for uvicorn to start ...${N}\n"
  sleep 5
  case "$OS" in
    Darwin) open "http://localhost:8080" ;;
    *) xdg-open "http://localhost:8080" 2>/dev/null || echo "Open http://localhost:8080 in your browser." ;;
  esac
  wait $UVICORN_PID
}

run_model_selection() {
  source .venv/bin/activate
  printf "${R}--- Model selection ---${N}\n"
  echo "Which model do you want to use?"
  echo "  1) gemini-2.5-flash (recommended)"
  echo "  2) gemini-3-pro-preview"
  echo "  3) gemini-2.5-pro"
  echo "  4) qwen3-coder-next:latest (local LLM, requires Ollama)"
  echo "  5) qwen3:8b (local LLM, requires Ollama)"
  echo "  6) Other models"
  read -r -p "Enter choice [1-6]: " choice
  case "$choice" in
    1) MODE=cloud; MODEL_NAME="gemini-2.5-flash" ;;
    2) MODE=cloud; MODEL_NAME="gemini-3-pro-preview" ;;
    3) MODE=cloud; MODEL_NAME="gemini-2.5-pro" ;;
    4) MODE=local; MODEL_NAME="qwen3-coder-next:latest" ;;
    5) MODE=local; MODEL_NAME="qwen3:8b" ;;
    6)
      read -r -p "Enter model name: " MODEL_NAME
      [[ -z "$MODEL_NAME" ]] && { echo "Model name cannot be empty."; exit 1; }
      read -r -p "Is this a local (Ollama) model? (y/n): " is_local
      case "$is_local" in
        [yY]|[yY][eE][sS]) MODE=local ;;
        *) MODE=cloud ;;
      esac
      ;;
    *) echo "Invalid choice."; exit 1 ;;
  esac
  API_KEY_TYPE=ollama
  API_KEY_VAL=""
  if [[ "$MODE" == "cloud" ]]; then
    if [[ "$MODEL_NAME" == gemini-* ]]; then
      API_KEY_TYPE=google
      while true; do
        read -r -p "Enter your Google (Gemini) API key (press 'h' for setup help): " API_KEY_VAL
        case "$API_KEY_VAL" in
          [hH])
            echo ""
            echo "To get a Google Gemini API key: go to https://aistudio.google.com/app/apikey, sign in with your Google account, click \"Create API Key,\" pick a project (or create one), then copy the key and keep it somewhere safe for use in your apps."
            echo ""
            echo "Warning: never share the API key, the wallet won't like it."
            read -r -p "Create your Google API key and paste it to continue, or press 'q' to quit: " API_KEY_VAL
            case "$API_KEY_VAL" in [qQ]) echo "Quitting."; exit 1 ;; esac
            [[ -n "$API_KEY_VAL" ]] && break
            ;;
        esac
        [[ -n "$API_KEY_VAL" ]] && break
        echo "API key cannot be empty."
      done
    else
      echo "Which API key will you use for this model?"
      echo "  1) Google (Gemini)"
      echo "  2) OpenAI"
      echo "  3) Anthropic (Claude)"
      read -r -p "Enter choice [1-3]: " key_choice
      case "$key_choice" in
        1) API_KEY_TYPE=google ;;
        2) API_KEY_TYPE=openai ;;
        3) API_KEY_TYPE=anthropic ;;
        *) echo "Invalid choice."; exit 1 ;;
      esac
      read -r -p "Enter your $API_KEY_TYPE API key: " API_KEY_VAL
    fi
    [[ -z "$API_KEY_VAL" ]] && { echo "API key cannot be empty for cloud models."; exit 1; }
  else
    API_KEY_VAL="ollama"
  fi
  BRAVE_ENABLED=""
  BRAVE_KEY=""
  if [[ "$MODEL_NAME" != gemini-* ]]; then
    read -r -p "Do you have a brave.com API key for search? (y/n): " has_brave
    case "$has_brave" in
      [yY]|[yY][eE][sS])
        read -r -p "Enter your Brave API key: " BRAVE_KEY
        [[ -n "$BRAVE_KEY" ]] && BRAVE_ENABLED="--brave-enabled"
        ;;
    esac
  fi
  BRAVE_ARGS=()
  [[ -n "$BRAVE_ENABLED" ]] && BRAVE_ARGS=(--brave-enabled --brave-key "$BRAVE_KEY")
  python3.11 tools/setup_env_writer.py --mode "$MODE" --model "$MODEL_NAME" --api-key-type "$API_KEY_TYPE" --api-key "$API_KEY_VAL" "${BRAVE_ARGS[@]}"
}

echo ""
printf "${R}💎 MarginCall Setup${N}\n"
printf "${D}Stock analyst agent — cloud or local LLM.${N}\n"
echo ""
printf "${R}--- Environment check ---${N}\n"
printf "  %b\n" "$(check_venv && echo "${G}✓${N} .venv created" || echo "${R}✗${N} .venv missing")"
printf "  %b\n" "$(check_env_file && echo "${G}✓${N} .env created" || echo "${R}✗${N} .env missing")"
printf "  %b\n" "$(check_api_key && echo "${G}✓${N} API key found in .env" || echo "${R}✗${N} API key missing")"
printf "  %b\n" "$(check_model_configured && echo "${G}✓${N} model configured" || echo "${R}✗${N} model not configured")"
echo ""

if check_venv && check_env_file && check_api_key && check_model_configured; then
  printf "${G}✓ All checks passed. Environment is already set up.${N}\n"
  get_model_display
  read -r -p "Change model or API key? (y/n): " change_choice
  case "$change_choice" in
    [yY]|[yY][eE][sS])
      run_model_selection
      printf "${G}✓ Model/API key updated.${N}\n"
      ;;
    *)
      printf "${G}✓ Setup complete.${N}\n"
      ;;
  esac
  read -r -p "Test the agent quickly? (y/n): " test_choice
  case "$test_choice" in
    [yY]|[yY][eE][sS]) run_quick_test ;;
  esac
  read -r -p "Start the agent now? (y/n): " start_choice
  case "$start_choice" in
    [yY]|[yY][eE][sS]) start_agent ;;
    *) printf "${D}Setup is complete. See README.md for how to start the agent or just run setup.sh again to start it.${N}\n" ;;
  esac
  exit 0
fi

# --- Fresh setup ---
echo ""
printf "${R}[1/3] Preparing environment${N}\n"
printf "  ${D}Detected: %s${N}\n" "$(echo "$OS" | tr '[:upper:]' '[:lower:]')"

# Ensure python3.11 is installed
if ! command -v python3.11 &>/dev/null; then
  echo "python3.11 not found."
  case "$OS" in
    Darwin)
      echo "Installing python3.11 via Homebrew..."
      if command -v brew &>/dev/null; then
        brew install python@3.11
        if [[ -x "$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11" ]]; then
          export PATH="$(brew --prefix python@3.11)/bin:$PATH"
        fi
      else
        echo "Homebrew not found. Install from https://brew.sh then run this script again."
        exit 1
      fi
      ;;
    Linux)
      if command -v apt-get &>/dev/null; then
        echo "Installing python3.11 via apt..."
        sudo apt-get update -qq
        sudo apt-get install -y python3.11 python3.11-venv 2>/dev/null || {
          echo "Python 3.11 may not be in default repos. Try: sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv"
          exit 1
        }
      elif command -v dnf &>/dev/null; then
        echo "Installing python3.11 via dnf..."
        sudo dnf install -y python3.11 2>/dev/null || sudo dnf install -y python3.11
      elif command -v yum &>/dev/null; then
        echo "Installing python3.11 via yum..."
        sudo yum install -y python3.11 2>/dev/null || { echo "Install Python 3.11 manually (e.g. from EPEL or pyenv)."; exit 1; }
      elif command -v pacman &>/dev/null; then
        echo "Installing python 3.11 via pacman..."
        sudo pacman -S --noconfirm python311 2>/dev/null || sudo pacman -S --noconfirm python
      elif command -v zypper &>/dev/null; then
        echo "Installing python3.11 via zypper..."
        sudo zypper install -y python3.11
      else
        echo "Unknown Linux package manager. Install Python 3.11 manually (e.g. pyenv install 3.11)."
        exit 1
      fi
      ;;
    *)
      echo "Unsupported OS. Install Python 3.11 manually (e.g. pyenv install 3.11)."
      exit 1
      ;;
  esac
fi

if ! command -v python3.11 &>/dev/null; then
  echo "python3.11 still not available. Ensure it is on your PATH."
  exit 1
fi

# Block keyboard input during venv/pip so keypresses aren't buffered as the next prompt's answer
exec 3<&0
exec 0</dev/null

python3.11 -m venv .venv
printf "  ${G}✓${N} .venv created\n"
source .venv/bin/activate
# Install tqdm first so install_with_progress can show a progress bar
pip install tqdm -q
if ! python3.11 tools/install_with_progress.py; then
  exec 0<&3 3<&-
  printf "${R}ERROR: pip install failed. Check the output above, fix any issues (e.g. network, missing deps), and run this script again.${N}\n"
  exit 1
fi
printf "  ${G}✓${N} required packages installed\n"

exec 0<&3 3<&-
drain_stdin

# Copy env.example to .env if .env does not exist
if [[ ! -f .env ]]; then
  cp env.example .env
  printf "  ${G}✓${N} Created .env from env.example\n"
fi

echo ""
printf "${R}[2/3] Model & API key${N}\n"
echo "--- Model selection ---"
while true; do
  echo "Which model do you want to use?"
  echo "  1) gemini-2.5-flash (recommended)"
  echo "  2) gemini-3-pro-preview"
  echo "  3) gemini-2.5-pro"
  echo "  4) qwen3-coder-next:latest (local LLM, requires Ollama)"
  echo "  5) qwen3:8b (local LLM, requires Ollama)"
  echo "  6) Other models"
  read -r -p "Enter choice [1-6]: " choice
  case "$choice" in
    1) MODE=cloud; MODEL_NAME="gemini-2.5-flash"; break ;;
    2) MODE=cloud; MODEL_NAME="gemini-3-pro-preview"; break ;;
    3) MODE=cloud; MODEL_NAME="gemini-2.5-pro"; break ;;
    4) MODE=local; MODEL_NAME="qwen3-coder-next:latest"; break ;;
    5) MODE=local; MODEL_NAME="qwen3:8b"; break ;;
    6)
      read -r -p "Enter model name: " MODEL_NAME
      [[ -z "$MODEL_NAME" ]] && { echo "Model name cannot be empty."; exit 1; }
      read -r -p "Is this a local (Ollama) model? (y/n): " is_local
      case "$is_local" in
        [yY]|[yY][eE][sS]) MODE=local ;;
        *) MODE=cloud ;;
      esac
      break
      ;;
    *) echo "Invalid choice. Please enter a number from 1 to 6." ;;
  esac
done


# API key
API_KEY_TYPE=ollama
API_KEY_VAL=""
if [[ "$MODE" == "cloud" ]]; then
  if [[ "$MODEL_NAME" == gemini-* ]]; then
    API_KEY_TYPE=google
    while true; do
      read -r -p "Enter your Google (Gemini) API key (press 'h' for setup help): " API_KEY_VAL
      case "$API_KEY_VAL" in
        [hH])
        echo ""
        echo "To get a Google Gemini API key: go to https://aistudio.google.com/app/apikey, sign in with your Google account, click \"Create API Key,\" pick a project (or create one), then copy the key and keep it somewhere safe for use in your apps."
        echo ""
        echo "Note: As of 2/15/2026, each Gmail account gets \$300 in Google Cloud credit for 90 days. This applies when you use gemini-* models."
        echo ""
        echo "Warning: never share the API key, the wallet won't like it."
        while true; do
          read -r -p "Create your Google API key and paste it to continue, or press 'q' to quit: " API_KEY_VAL
          case "$API_KEY_VAL" in [qQ]) echo "Quitting."; exit 1 ;; esac
          [[ -n "$API_KEY_VAL" ]] && break
        done
        break
        ;;
      esac
      [[ -n "$API_KEY_VAL" ]] && break
      echo "API key cannot be empty."
    done
  else
    echo "Which API key will you use for this model?"
    echo "  1) Google (Gemini)"
    echo "  2) OpenAI"
    echo "  3) Anthropic (Claude)"
    read -r -p "Enter choice [1-3]: " key_choice
    case "$key_choice" in
      1) API_KEY_TYPE=google ;;
      2) API_KEY_TYPE=openai ;;
      3) API_KEY_TYPE=anthropic ;;
      *) echo "Invalid choice."; exit 1 ;;
    esac
    read -r -p "Enter your $API_KEY_TYPE API key: " API_KEY_VAL
  fi
  [[ -z "$API_KEY_VAL" ]] && { echo "API key cannot be empty for cloud models."; exit 1; }
else
  API_KEY_TYPE=ollama
  API_KEY_VAL="ollama"
fi

# Brave search (for non-Gemini models)
BRAVE_ENABLED=""
BRAVE_KEY=""
if [[ "$MODEL_NAME" != gemini-* ]]; then
  read -r -p "Do you have a brave.com API key for search? (y/n): " has_brave
  case "$has_brave" in
    [yY]|[yY][eE][sS])
    read -r -p "Enter your Brave API key: " BRAVE_KEY
    [[ -n "$BRAVE_KEY" ]] && BRAVE_ENABLED="--brave-enabled"
    ;;
  esac
fi

# Update .env
BRAVE_ARGS=()
[[ -n "$BRAVE_ENABLED" ]] && BRAVE_ARGS=(--brave-enabled --brave-key "$BRAVE_KEY")
python3.11 tools/setup_env_writer.py --mode "$MODE" --model "$MODEL_NAME" --api-key-type "$API_KEY_TYPE" --api-key "$API_KEY_VAL" "${BRAVE_ARGS[@]}"

echo ""
printf "  ${D}You can enable agent observability later by setting AGENTOPS_API_KEY in .env (see agentops.ai).${N}\n"
echo ""

# Summary with checkmarks
VENV_OK=0
[[ -d .venv ]] && VENV_OK=1
MODEL_DISPLAY="$MODEL_NAME"
[[ "$MODE" == "local" ]] && MODEL_DISPLAY="local ($MODEL_NAME)"
KEY_OK=0
[[ "$MODE" == "local" || -n "$API_KEY_VAL" ]] && KEY_OK=1
SEARCH_STATUS="disabled"
[[ -n "$BRAVE_ENABLED" ]] && SEARCH_STATUS="enabled"

printf "${R}[3/3] Finalizing setup${N}\n"
echo ""
printf "${R}--- Setup summary ---${N}\n"
printf "  %b\n" "$([[ $VENV_OK -eq 1 ]] && echo "${G}✓${N} venv created" || echo "${R}✗${N} venv missing")"
printf "  %b\n" "$([[ $VENV_OK -eq 1 ]] && echo "${G}✓${N} model: ${G}$MODEL_DISPLAY${N}" || echo "${R}✗${N} model")"
printf "  %b\n" "$([[ $KEY_OK -eq 1 ]] && echo "${G}✓${N} API key set" || echo "${R}✗${N} API key missing")"
printf "  search ${G}%s${N}\n" "$SEARCH_STATUS"
echo ""

ALL_OK=0
[[ $VENV_OK -eq 1 && $KEY_OK -eq 1 ]] && ALL_OK=1
if [[ $ALL_OK -eq 1 ]]; then
  printf "${R}💎${N} ${G}MarginCall setup complete.${N}\n"
else
  printf "${R}Fix any missing steps above, then run this script again if needed.${N}\n"
fi

read -r -p "Test the agent quickly? (y/n): " test_choice
case "$test_choice" in
  [yY]|[yY][eE][sS])
    run_exit_test || {
      echo ""
      run_model_selection
      run_exit_test
    }
    ;;
esac

if check_cloud_configured || check_local_configured; then
  read -r -p "Start the agent now? (y/n): " start_choice
  case "$start_choice" in
    [yY]|[yY][eE][sS]) start_agent ;;
    *) printf "${D}Setup is complete. See README.md for how to start the agent or run this setup.sh to start it.${N}\n" ;;
  esac
fi
