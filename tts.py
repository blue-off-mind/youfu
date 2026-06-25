import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "tts_config.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"
ELEVENLABS_PROVIDER = "elevenlabs"
MIMO_PROVIDER = "mimo"
DEFAULT_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_MIMO_MODEL = "mimo-v2.5-tts"
DEFAULT_MIMO_VOICE = "kimi_Female1"
DEFAULT_MIMO_FORMAT = "pcm16"
DEFAULT_MIMO_SAMPLE_RATE = 32000


def load_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    provider = tts_provider(config)
    if provider == MIMO_PROVIDER:
        api_key = config.get("mimo_api_key") or os.getenv(config.get("mimo_api_key_env", "MIMO_API_KEY"))
        if api_key:
            config["mimo_api_key"] = api_key
        if not config.get("mimo_api_key"):
            raise SystemExit("Missing required config value(s): mimo_api_key")
        config.setdefault("mimo_base_url", DEFAULT_MIMO_BASE_URL)
        config.setdefault("mimo_model", DEFAULT_MIMO_MODEL)
        config.setdefault("mimo_voice", DEFAULT_MIMO_VOICE)
        config.setdefault("mimo_format", DEFAULT_MIMO_FORMAT)
        config.setdefault("mimo_sample_rate", DEFAULT_MIMO_SAMPLE_RATE)
        return config

    api_key = config.get("api_key") or os.getenv(config.get("api_key_env", "ELEVENLABS_API_KEY"))
    if api_key:
        config["api_key"] = api_key

    missing = [key for key in ("api_key", "voice_id") if not config.get(key)]
    if missing:
        raise SystemExit(f"Missing required config value(s): {', '.join(missing)}")
    return config


def tts_provider(config: dict) -> str:
    provider = str(config.get("provider") or ELEVENLABS_PROVIDER).strip().lower()
    return MIMO_PROVIDER if provider in {"mimo", "mimo-v2.5-tts", "xiaomi_mimo", "xiaomimimo"} else ELEVENLABS_PROVIDER


def apply_desktop_output_format(config: dict, output_format: str | None) -> None:
    if not output_format:
        return

    if tts_provider(config) == MIMO_PROVIDER:
        output_format = str(output_format).strip().lower()
        if output_format.startswith("pcm_"):
            config["mimo_format"] = DEFAULT_MIMO_FORMAT
            config["mimo_sample_rate"] = output_format.split("_", 1)[1]
        elif output_format in {"pcm16", "wav", "mp3"}:
            config["mimo_format"] = output_format
        return

    config["output_format"] = output_format


def audio_output_info(config: dict) -> tuple[str, int | None]:
    if tts_provider(config) == MIMO_PROVIDER:
        audio_format = str(config.get("mimo_format") or DEFAULT_MIMO_FORMAT).strip().lower()
        if audio_format == "pcm16":
            try:
                return "wav", int(config.get("mimo_sample_rate") or DEFAULT_MIMO_SAMPLE_RATE)
            except (TypeError, ValueError):
                raise SystemExit(f"Unsupported MiMo sample rate: {config.get('mimo_sample_rate')}")
        if audio_format == "wav":
            return "wav", None
        if audio_format == "mp3":
            return "mp3", None
        raise SystemExit(f"Unsupported MiMo audio format: {audio_format}")

    output_format = str(config.get("output_format") or "mp3_44100_128").strip()
    if output_format.startswith("pcm_"):
        try:
            return "wav", int(output_format.split("_", 1)[1])
        except (IndexError, ValueError):
            raise SystemExit(f"Unsupported PCM output format: {output_format}")
    return "mp3", None


def synthesize_elevenlabs(text: str, config: dict) -> bytes:
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


def mimo_endpoint(base_url: str) -> str:
    base_url = (base_url or DEFAULT_MIMO_BASE_URL).strip().rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def synthesize_mimo(text: str, config: dict) -> bytes:
    try:
        sample_rate = int(config.get("mimo_sample_rate") or DEFAULT_MIMO_SAMPLE_RATE)
    except (TypeError, ValueError):
        raise SystemExit(f"Unsupported MiMo sample rate: {config.get('mimo_sample_rate')}")

    payload = {
        "model": config.get("mimo_model") or DEFAULT_MIMO_MODEL,
        "messages": [{"role": "assistant", "content": text}],
        "audio": {
            "voice": config.get("mimo_voice") or DEFAULT_MIMO_VOICE,
            "format": config.get("mimo_format") or DEFAULT_MIMO_FORMAT,
            "sample_rate": sample_rate,
        },
        "stream": False,
    }
    request = urllib.request.Request(
        mimo_endpoint(config.get("mimo_base_url") or DEFAULT_MIMO_BASE_URL),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": config["mimo_api_key"],
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"MiMo API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error calling MiMo: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON returned by MiMo: {exc}") from exc

    try:
        audio_b64 = body["choices"][0]["message"]["audio"]["data"]
        return base64.b64decode(audio_b64)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise SystemExit(f"MiMo response did not include audio data: {body}") from exc


def synthesize(text: str, config: dict) -> bytes:
    if tts_provider(config) == MIMO_PROVIDER:
        return synthesize_mimo(text, config)
    return synthesize_elevenlabs(text, config)


def output_path(path_arg: str | None, output_dir: Path, extension: str = "mp3") -> Path:
    if path_arg:
        path = Path(path_arg)
        return path if path.is_absolute() else ROOT / path

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return output_dir / f"tts-{timestamp}.{extension}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate speech with the configured TTS provider.")
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
    extension, sample_rate = audio_output_info(config)
    out_path = output_path(args.out, DEFAULT_OUTPUT_DIR, extension)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = synthesize(text, config)
    if sample_rate:
        with wave.open(str(out_path), "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(sample_rate)
            file.writeframes(data)
    else:
        out_path.write_bytes(data)

    print(f"Saved audio: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
