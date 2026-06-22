import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "gemini_config.json"


def load_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    api_key = config.get("api_key") or os.getenv(config.get("api_key_env", "GEMINI_API_KEY"))
    if not api_key:
        raise SystemExit(
            "Gemini API key is not configured. Add it to gemini_config.json "
            "or set the GEMINI_API_KEY environment variable."
        )
    config["api_key"] = api_key
    return config


def model_url(base_url: str, model: str) -> str:
    model = model.strip("/")
    if model.startswith("models/"):
        return f"{base_url}/{model}:generateContent"
    return f"{base_url}/models/{model}:generateContent"


def extract_text(body: dict) -> str:
    try:
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"Unexpected Gemini response: {json.dumps(body, ensure_ascii=False)}") from exc

    if not text:
        raise SystemExit(f"Gemini returned an empty transcript: {json.dumps(body, ensure_ascii=False)}")
    return text


def transcribe_with_model(audio_b64: str, mime_type: str, config: dict, model: str) -> str:
    base_url = config.get("base_url", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = model_url(base_url, model)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": config.get("transcription_prompt", "Transcribe this audio.")},
                    {"inline_data": {"mime_type": mime_type, "data": audio_b64}},
                ],
            }
        ],
        "generationConfig": {"temperature": 0},
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": config["api_key"],
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    return extract_text(body)


def transcribe_audio(audio_path: Path, config: dict) -> str:
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/mpeg"
    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    models = [config.get("model", "gemini-2.5-flash"), *config.get("fallback_models", [])]
    models = list(dict.fromkeys(model for model in models if model))
    retryable_statuses = {429, 503}
    errors = []

    for model in models:
        try:
            return transcribe_with_model(audio_b64, mime_type, config, model)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            errors.append(f"{model}: HTTP {exc.code}: {body}")
            if exc.code not in retryable_statuses:
                break
        except urllib.error.URLError as exc:
            errors.append(f"{model}: network error: {exc}")
            break

    raise SystemExit("Gemini transcription failed:\n" + "\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe an audio file with Gemini.")
    parser.add_argument("audio", help="Audio file path.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to gemini_config.json.")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    try:
        print(transcribe_audio(Path(args.audio), config))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Gemini API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error calling Gemini: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
