import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "tts_config.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"


def load_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    api_key = config.get("api_key") or os.getenv(config.get("api_key_env", "ELEVENLABS_API_KEY"))
    if api_key:
        config["api_key"] = api_key

    missing = [key for key in ("api_key", "voice_id") if not config.get(key)]
    if missing:
        raise SystemExit(f"Missing required config value(s): {', '.join(missing)}")
    return config


def synthesize(text: str, config: dict) -> bytes:
    voice_id = config["voice_id"]
    output_format = config.get("output_format", "mp3_44100_128")
    query = urllib.parse.urlencode({"output_format": output_format})
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?{query}"

    payload = {
        "text": text,
        "model_id": config.get("model_id", "eleven_multilingual_v2"),
    }
    if config.get("voice_settings"):
        payload["voice_settings"] = config["voice_settings"]

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "xi-api-key": config["api_key"],
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"ElevenLabs API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error calling ElevenLabs: {exc}") from exc


def output_path(path_arg: str | None, output_dir: Path) -> Path:
    if path_arg:
        path = Path(path_arg)
        return path if path.is_absolute() else ROOT / path

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return output_dir / f"tts-{timestamp}.mp3"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate speech with ElevenLabs TTS.")
    parser.add_argument("text", nargs="?", help="Text to synthesize.")
    parser.add_argument("--text-file", help="Read text from a UTF-8 text file.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to tts_config.json.")
    parser.add_argument("--out", help="Output mp3 path. Defaults to outputs/tts-YYYYMMDD-HHMMSS.mp3.")
    args = parser.parse_args()

    if args.text_file:
        text_path = Path(args.text_file)
        text = text_path.read_text(encoding="utf-8").strip()
    elif args.text:
        text = args.text.strip()
    else:
        text = sys.stdin.read().strip()

    if not text:
        raise SystemExit("No text provided. Pass text, --text-file, or pipe text through stdin.")

    config = load_config(Path(args.config))
    out_path = output_path(args.out, DEFAULT_OUTPUT_DIR)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(synthesize(text, config))

    print(f"Saved audio: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
