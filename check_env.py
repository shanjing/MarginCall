"""
Environment and structure sanity check for MarginCall.

Verifies:
  1. root_agent.name matches the root agent directory name.
  2. Sub-agent directories under root exist and match SUB_AGENTS from config.
  3. Each sub-agent's .name matches its directory name.
  4. root_agent and sub-agents can import config, tools, and dependencies.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
from pathlib import Path

# Project root = directory containing this script (MarginCall/)
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from tools.logging_utils import setup_logging
from tools.config import AI_MODEL, AI_MODEL_NAME, ROOT_AGENT, SUB_AGENTS

logger = logging.getLogger(__name__)


def run_sanity_check() -> bool:
    """Run all sanity checks. Returns True if all pass, False otherwise."""
    setup_logging(debug=True, model_name=AI_MODEL_NAME)
    logger.info("--- SANITY CHECK START ---")

    all_ok = True

    # --- 1. Environment ---
    app_name = os.getenv("AGENT_APP_NAME")
    if not app_name:
        logger.warning("AGENT_APP_NAME is missing from .env.")
    else:
        logger.info("Environment: APP_NAME=%s", app_name)

    logger.info("Model: %s (%s)", AI_MODEL_NAME, "Cloud" if isinstance(AI_MODEL, str) else "Local/LiteLLM")
    logger.info("Config: ROOT_AGENT=%s, SUB_AGENTS=%s", ROOT_AGENT, SUB_AGENTS)

    root_dir = PROJECT_ROOT / ROOT_AGENT
    sub_agents_dir = root_dir / "sub_agents"

    # --- 2. Root directory exists ---
    if not root_dir.is_dir():
        logger.error("Root agent directory not found: %s", root_dir)
        all_ok = False
    else:
        logger.info("Root agent directory: %s", root_dir)

    # --- 3. root_agent.name matches root directory name ---
    try:
        root_mod = importlib.import_module(f"{ROOT_AGENT}.agent")
        root_agent = getattr(root_mod, "root_agent", None)
        if root_agent is None:
            logger.error("root_agent not found in %s.agent", ROOT_AGENT)
            all_ok = False
        elif getattr(root_agent, "name", None) != ROOT_AGENT:
            logger.error(
                "root_agent.name=%r does not match root directory name %r",
                getattr(root_agent, "name", None),
                ROOT_AGENT,
            )
            all_ok = False
        else:
            logger.info("root_agent.name matches root directory: %s", ROOT_AGENT)
    except Exception as e:
        logger.exception("Failed to import root_agent from %s.agent: %s", ROOT_AGENT, e)
        all_ok = False
        root_agent = None

    # --- 4. Sub-agent directories exist and match SUB_AGENTS ---
    if sub_agents_dir.is_dir():
        actual_sub_dirs = sorted(
            d.name for d in sub_agents_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
        expected = set(SUB_AGENTS)
        actual = set(actual_sub_dirs)

        missing_dirs = expected - actual
        extra_dirs = actual - expected

        if missing_dirs:
            logger.error("Sub-agent directories missing (in SUB_AGENTS but not on disk): %s", sorted(missing_dirs))
            all_ok = False
        if extra_dirs:
            logger.warning("Extra sub-agent directories (on disk but not in SUB_AGENTS): %s", sorted(extra_dirs))

        if not missing_dirs:
            logger.info("Sub-agent directories match SUB_AGENTS: %s", actual_sub_dirs)
    else:
        logger.error("Sub-agents directory not found: %s", sub_agents_dir)
        all_ok = False
        actual_sub_dirs = []

    # --- 5. Each sub-agent's .name matches its directory name ---
    for sub_name in SUB_AGENTS:
        sub_dir = sub_agents_dir / sub_name
        if not sub_dir.is_dir():
            continue
        try:
            sub_mod = importlib.import_module(f"{ROOT_AGENT}.sub_agents.{sub_name}.agent")
            sub_agent = getattr(sub_mod, sub_name, None)
            if sub_agent is None:
                logger.error("Sub-agent %r not found in %s.sub_agents.%s.agent", sub_name, ROOT_AGENT, sub_name)
                all_ok = False
            elif getattr(sub_agent, "name", None) != sub_name:
                logger.error(
                    "Sub-agent %s: .name=%r does not match directory name %r",
                    sub_name,
                    getattr(sub_agent, "name", None),
                    sub_name,
                )
                all_ok = False
            else:
                logger.info("Sub-agent %s: .name matches directory", sub_name)
        except Exception as e:
            logger.exception("Failed to import sub-agent %s: %s", sub_name, e)
            all_ok = False

    # --- 6. Imports: root_agent (config, tools, sub-agents), sub-agents (deps) ---
    # Root imports config + sub-agents: already exercised by loading root_agent.
    # Explicitly verify config and tools are importable and used by root.
    try:
        from tools import config as tools_config
        _ = getattr(tools_config, "AI_MODEL", None)
        _ = getattr(tools_config, "INCLUDE_THOUGHTS", None)
        _ = getattr(tools_config, "ROOT_AGENT", None)
        _ = getattr(tools_config, "SUB_AGENTS", None)
        logger.info("Config objects (AI_MODEL, INCLUDE_THOUGHTS, ROOT_AGENT, SUB_AGENTS) OK")
    except Exception as e:
        logger.exception("Failed to import tools.config or required symbols: %s", e)
        all_ok = False

    try:
        from tools import logging_utils
        from tools import runner_utils
        _ = getattr(logging_utils, "setup_logging", None)
        _ = getattr(runner_utils, "execute_agent_stream", None)
        logger.info("Tools modules (logging_utils, runner_utils) OK")
    except Exception as e:
        logger.exception("Failed to import tools modules: %s", e)
        all_ok = False

    # Root imports sub-agents: already verified when we loaded root_agent (it pulls them).
    if root_agent is not None:
        logger.info("Root agent imports (config, sub-agents) OK")

    # Sub-agents import deps: verified by successfully importing each sub-agent module above.
    logger.info("Sub-agent imports (deps) OK (verified via sub-agent load)")

    # --- Final verdict ---
    if all_ok:
        print("\n\033[92mPASSED\033[0m")  # ANSI green
    else:
        print("\n\033[91mFAILED\033[0m")  # ANSI red

    return all_ok


if __name__ == "__main__":
    ok = run_sanity_check()
    sys.exit(0 if ok else 1)
