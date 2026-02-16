# Setup script for Windows. On macOS/Linux, run: ./setup.sh
$ErrorActionPreference = "Stop"

Write-Host "Setting up runtime environment (Windows)..."

function Find-Python311 {
    # Try py launcher first (Windows)
    $py = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
    if ($py) { return $py }
    # Then direct python3.11
    $p = Get-Command python3.11 -ErrorAction SilentlyContinue
    if ($p) { return $p.Source }
    $p = Get-Command python -ErrorAction SilentlyContinue
    if ($p) {
        $v = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($v -eq "3.11") { return $p.Source }
    }
    return $null
}

$pythonExe = Find-Python311
if (-not $pythonExe) {
    Write-Host "Python 3.11 not found."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing Python 3.11 via winget..."
        winget install --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
        # Refresh env so new python is on PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $pythonExe = Find-Python311
    }
    if (-not $pythonExe) {
        Write-Host "Install Python 3.11 from https://www.python.org/downloads/ or run: winget install Python.Python.3.11"
        exit 1
    }
}

Write-Host "Using Python: $pythonExe"
& $pythonExe -m venv .venv
& .\.venv\Scripts\Activate.ps1
# Install tqdm first so install_with_progress can show a progress bar
pip install tqdm -q
& .\.venv\Scripts\python.exe tools/install_with_progress.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed. Check the output above, fix any issues (e.g. network, missing deps), and run this script again."
    exit 1
}

# Copy env.example to .env if .env does not exist
if (-not (Test-Path .env)) {
    Copy-Item env.example .env
    Write-Host "Created .env from env.example."
}

Write-Host ""
Write-Host "--- Model selection ---"
Write-Host "Which model do you want to use?"
Write-Host "  1) gemini-2.5-flash (recommended)"
Write-Host "  2) gemini-3-pro-preview"
Write-Host "  3) gemini-2.5-pro"
Write-Host "  4) qwen3-coder-next:latest (local LLM, requires Ollama)"
Write-Host "  5) qwen3:8b (local LLM, requires Ollama)"
Write-Host "  6) Other models"
$choice = Read-Host "Enter choice [1-6]"

$MODE = "cloud"
$MODEL_NAME = ""
switch ($choice) {
    "1" { $MODE = "cloud"; $MODEL_NAME = "gemini-2.5-flash" }
    "2" { $MODE = "cloud"; $MODEL_NAME = "gemini-3-pro-preview" }
    "3" { $MODE = "cloud"; $MODEL_NAME = "gemini-2.5-pro" }
    "4" { $MODE = "local"; $MODEL_NAME = "qwen3-coder-next:latest" }
    "5" { $MODE = "local"; $MODEL_NAME = "qwen3:8b" }
    "6" {
        $MODEL_NAME = Read-Host "Enter model name"
        if ([string]::IsNullOrWhiteSpace($MODEL_NAME)) { Write-Host "Model name cannot be empty."; exit 1 }
        $isLocal = (Read-Host "Is this a local (Ollama) model? (y/n)").ToLower()
        if ($isLocal -match "^(y|yes)$") { $MODE = "local" } else { $MODE = "cloud" }
    }
    default { Write-Host "Invalid choice."; exit 1 }
}

# API key
$API_KEY_TYPE = "ollama"
$API_KEY_VAL = ""
if ($MODE -eq "cloud") {
    if ($MODEL_NAME -like "gemini-*") {
        $API_KEY_TYPE = "google"
        do {
            $API_KEY_VAL = Read-Host "Enter your Google (Gemini) API key (press 'h' for setup help)"
            if ($API_KEY_VAL -eq "h" -or $API_KEY_VAL -eq "H") {
                Write-Host ""
                Write-Host "To get a Google Gemini API key: go to https://aistudio.google.com/app/apikey, sign in with your Google account, click `"Create API Key,`" pick a project (or create one), then copy the key and keep it somewhere safe for use in your apps."
                Write-Host ""
                Write-Host "Note: As of 2/15/2026, each Gmail account gets `$300 in Google Cloud credit for 90 days. This applies when you use gemini-* models."
                Write-Host ""
                do {
                    $API_KEY_VAL = Read-Host "Create your Google API key and paste it to continue, or press 'q' to quit"
                    if ($API_KEY_VAL -eq "q" -or $API_KEY_VAL -eq "Q") { Write-Host "Quitting."; exit 1 }
                } while ([string]::IsNullOrWhiteSpace($API_KEY_VAL))
                break
            }
            if (-not [string]::IsNullOrWhiteSpace($API_KEY_VAL)) { break }
            Write-Host "API key cannot be empty."
        } while ($true)
    } else {
        Write-Host "Which API key will you use for this model?"
        Write-Host "  1) Google (Gemini)"
        Write-Host "  2) OpenAI"
        Write-Host "  3) Anthropic (Claude)"
        $keyChoice = Read-Host "Enter choice [1-3]"
        switch ($keyChoice) {
            "1" { $API_KEY_TYPE = "google" }
            "2" { $API_KEY_TYPE = "openai" }
            "3" { $API_KEY_TYPE = "anthropic" }
            default { Write-Host "Invalid choice."; exit 1 }
        }
        $API_KEY_VAL = Read-Host "Enter your $API_KEY_TYPE API key"
    }
    if ([string]::IsNullOrWhiteSpace($API_KEY_VAL)) { Write-Host "API key cannot be empty for cloud models."; exit 1 }
} else {
    $API_KEY_VAL = "ollama"
}

# Brave search (for non-Gemini models)
$BRAVE_ENABLED = $false
$BRAVE_KEY = ""
if ($MODEL_NAME -notlike "gemini-*") {
    $hasBrave = (Read-Host "Do you have a brave.com API key for search? (y/n)").ToLower()
    if ($hasBrave -match "^(y|yes)$") {
        $BRAVE_KEY = Read-Host "Enter your Brave API key"
        if (-not [string]::IsNullOrWhiteSpace($BRAVE_KEY)) { $BRAVE_ENABLED = $true }
    }
}

# Update .env
$braveArgs = @()
if ($BRAVE_ENABLED) { $braveArgs = @("--brave-enabled", "--brave-key", $BRAVE_KEY) }
& .\.venv\Scripts\python.exe tools/setup_env_writer.py --mode $MODE --model $MODEL_NAME --api-key-type $API_KEY_TYPE --api-key $API_KEY_VAL @braveArgs

Write-Host ""
Write-Host "You can enable agent observability later by setting AGENTOPS_API_KEY in .env (see agentops.ai)."
Write-Host ""

# Summary with checkmarks
$VENV_OK = (Test-Path .venv)
$PIP_OK = (Test-Path .\.venv\Scripts\pip.exe)
$MODEL_DISPLAY = $MODEL_NAME
if ($MODE -eq "local") { $MODEL_DISPLAY = "local ($MODEL_NAME)" }
$KEY_OK = ($MODE -eq "local" -or -not [string]::IsNullOrWhiteSpace($API_KEY_VAL))
$SEARCH_STATUS = "disabled"
if ($BRAVE_ENABLED) { $SEARCH_STATUS = "enabled" }

Write-Host "--- Setup summary ---"
Write-Host "  1. venv created?               $(if ($VENV_OK) { '✓' } else { '✗' })"
Write-Host "  2. required packages installed? $(if ($PIP_OK) { '✓' } else { '✗' })"
Write-Host "  3. model to use:               $(if ($VENV_OK) { '✓' } else { '✗' }) [$MODEL_DISPLAY]"
Write-Host "  4. API key set?                $(if ($KEY_OK) { '✓' } else { '✗' })"
Write-Host "  5. search:                    $SEARCH_STATUS"
Write-Host ""

$ALL_OK = ($VENV_OK -and $PIP_OK -and $KEY_OK)
if ($ALL_OK) {
    Write-Host "Setup complete. Run .\run_ui.sh to start the UI, then open http://localhost:8080 in your browser to use the agent."
} else {
    Write-Host "Fix any missing steps above, then run this script again if needed."
}
Write-Host "Activate the venv with: .\.venv\Scripts\Activate.ps1"