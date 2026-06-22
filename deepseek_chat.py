import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "llm_config.json"


def load_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    api_key = config.get("api_key") or os.getenv(config.get("api_key_env", "DEEPSEEK_API_KEY"))
    if not api_key:
        raise SystemExit(
            "DeepSeek API key is not configured. Add it to llm_config.json "
            "or set the DEEPSEEK_API_KEY environment variable."
        )
    config["api_key"] = api_key
    return config


def load_system_prompt(config: dict) -> str:
    prompt_file = config.get("system_prompt_file")
    if not prompt_file:
        return ""

    path = Path(prompt_file)
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(f"System prompt file not found: {path}")


def complete_chat(messages: list[dict], config: dict) -> str:
    base_url = config.get("base_url", "https://api.deepseek.com").rstrip("/")
    url = f"{base_url}/chat/completions"

    payload = {
        "model": config.get("model", "deepseek-v4-flash"),
        "messages": messages,
        "temperature": config.get("temperature", 0.7),
        "max_tokens": config.get("max_tokens", 800),
        "stream": False,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"DeepSeek API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error calling DeepSeek: {exc}") from exc

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"Unexpected DeepSeek response: {json.dumps(body, ensure_ascii=False)}") from exc


def chat(message: str, config: dict, system_prompt: str) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": message})
    return complete_chat(messages, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat with DeepSeek using AGENTS.md as persona.")
    parser.add_argument("message", nargs="?", help="User message.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to llm_config.json.")
    args = parser.parse_args()

    message = args.message.strip() if args.message else sys.stdin.read().strip()
    if not message:
        raise SystemExit("No message provided. Pass a message or pipe text through stdin.")

    config = load_config(Path(args.config))
    system_prompt = load_system_prompt(config)
    print(chat(message, config, system_prompt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
