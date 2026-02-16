"""
Update .env with model choice, API key, and Brave search setting.
Called by setup.sh / setup.ps1 after interactive prompts.
"""
import re
from pathlib import Path

import click


@click.command()
@click.option(
    "--mode",
    required=True,
    type=click.Choice(["cloud", "local"]),
    help="Use cloud or local (Ollama) model.",
)
@click.option(
    "--model",
    required=True,
    help="Model name (e.g. gemini-2.5-flash or qwen3:8b).",
)
@click.option(
    "--api-key-type",
    required=True,
    type=click.Choice(["google", "openai", "anthropic", "ollama"]),
    help="Which API key to set.",
)
@click.option("--api-key", default="", help="API key value (empty for ollama).")
@click.option("--brave-enabled", is_flag=True, help="Enable Brave search.")
@click.option("--brave-key", default="", help="Brave API key when --brave-enabled.")
def main(
    mode: str,
    model: str,
    api_key_type: str,
    api_key: str,
    brave_enabled: bool,
    brave_key: str,
) -> None:
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    example_path = root / "env.example"
    if not env_path.exists() and example_path.exists():
        env_path.write_text(example_path.read_text())

    content = env_path.read_text()
    lines = content.splitlines()
    out: list[str] = []
    done: set[str] = set()

    api_keys = {
        "GOOGLE_API_KEY": api_key if api_key_type == "google" else "",
        "OPENAI_API_KEY": api_key if api_key_type == "openai" else "",
        "ANTHROPIC_API_KEY": api_key if api_key_type == "anthropic" else "",
    }
    brave_val = brave_key if brave_enabled else None  # None = comment out / disable

    # Normalize model for display: strip ollama_chat/ when writing LOCAL_AI_MODEL
    if mode == "local":
        local_model_value = f"ollama_chat/{model}"
    else:
        local_model_value = ""

    for line in lines:
        # CLOUD_AI_MODEL
        if re.match(r"^#?\s*CLOUD_AI_MODEL\s*=", line):
            if mode == "cloud":
                out.append(f"CLOUD_AI_MODEL='{model}'")
            else:
                out.append("# CLOUD_AI_MODEL=  # using local model")
            done.add("CLOUD_AI_MODEL")
            continue
        # LOCAL_AI_MODEL
        if re.match(r"^#?\s*LOCAL_AI_MODEL\s*=", line):
            if mode == "local":
                out.append(f"LOCAL_AI_MODEL='{local_model_value}'")
            else:
                out.append(line)
            done.add("LOCAL_AI_MODEL")
            continue
        # API keys
        for key in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            if re.match(rf"^#?\s*{re.escape(key)}\s*=", line):
                val = api_keys.get(key, "")
                if val:
                    out.append(f"{key}='{val}'")
                else:
                    out.append(line)
                done.add(key)
                break
        else:
            # BRAVE_API_KEY
            if re.match(r"^#?\s*BRAVE_API_KEY\s*=", line):
                if brave_val is not None and brave_val:
                    out.append(f"BRAVE_API_KEY='{brave_val}'")
                else:
                    out.append("# BRAVE_API_KEY=  # Search disabled (no key)")
                done.add("BRAVE_API_KEY")
                continue
            out.append(line)

    # Append only keys we set that were missing from the file
    if "CLOUD_AI_MODEL" not in done and mode == "cloud":
        out.append(f"CLOUD_AI_MODEL='{model}'")
    if "LOCAL_AI_MODEL" not in done and mode == "local":
        out.append(f"LOCAL_AI_MODEL='{local_model_value}'")
    for key, val in api_keys.items():
        if key not in done and val:
            out.append(f"{key}='{val}'")
    if "BRAVE_API_KEY" not in done:
        if brave_val:
            out.append(f"BRAVE_API_KEY='{brave_val}'")
        else:
            out.append("# BRAVE_API_KEY=  # Search disabled (no key)")

    env_path.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
