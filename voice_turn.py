import argparse
import json
import shutil
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

from gemini_brain import (
    active_model_label,
    active_provider,
    audio_reply,
    gateway_format,
    load_config as load_gemini_config,
    load_persona,
    summarize_session,
    text_reply,
)
from tts import (
    apply_desktop_output_format,
    audio_output_info,
    load_config as load_tts_config,
    synthesize,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DEFAULT_GEMINI_CONFIG = ROOT / "gemini_config.json"
DEFAULT_TTS_CONFIG = ROOT / "tts_config.json"
DEFAULT_SESSION_CONFIG = ROOT / "session_config.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"

NEW_SESSION_COMMANDS = {"新会话", "开启新会话", "重来", "清空上下文", "reset", "new session"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def new_session() -> dict:
    now = utc_now()
    return {
        "id": time.strftime("%Y%m%d-%H%M%S"),
        "created_at": now,
        "updated_at": now,
        "summary": "",
        "messages": [],
    }


def archive_session(path: Path, archive_dir: Path) -> None:
    if not path.exists():
        return

    try:
        session = json.loads(path.read_text(encoding="utf-8"))
        session_id = session.get("id") or time.strftime("%Y%m%d-%H%M%S")
    except json.JSONDecodeError:
        session_id = time.strftime("%Y%m%d-%H%M%S")

    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{session_id}.json"
    if target.exists():
        target = archive_dir / f"{session_id}-{int(time.time())}.json"
    shutil.move(str(path), str(target))


def save_session(session: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = utc_now()
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")


def should_auto_new_session(session: dict, idle_minutes: int) -> bool:
    if idle_minutes <= 0 or not session.get("updated_at"):
        return False

    try:
        updated_at = datetime.fromisoformat(session["updated_at"])
    except ValueError:
        return False

    idle_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
    return idle_seconds >= idle_minutes * 60


def load_or_create_session(session_config: dict, force_new: bool) -> tuple[dict, Path]:
    session_path = resolve_project_path(session_config["active_session_path"])
    archive_dir = resolve_project_path(session_config["archive_dir"])

    if force_new:
        archive_session(session_path, archive_dir)
        session = new_session()
        save_session(session, session_path)
        return session, session_path

    if not session_path.exists():
        session = new_session()
        save_session(session, session_path)
        return session, session_path

    session = json.loads(session_path.read_text(encoding="utf-8"))
    if should_auto_new_session(session, int(session_config.get("idle_new_session_minutes", 30))):
        archive_session(session_path, archive_dir)
        session = new_session()
        save_session(session, session_path)
    return session, session_path


def append_turn(session: dict, user_text: str, assistant_text: str) -> None:
    session["messages"].append({"role": "user", "content": user_text, "timestamp": utc_now()})
    session["messages"].append({"role": "assistant", "content": assistant_text, "timestamp": utc_now()})


def summarize_if_needed(session: dict, session_config: dict, gemini_config: dict) -> None:
    messages = session.get("messages", [])
    summarize_after = int(session_config.get("summarize_after_messages", 16))
    max_recent = int(session_config.get("max_recent_messages", 12))
    if len(messages) < summarize_after:
        return

    old_messages = messages[:-max_recent]
    if not old_messages:
        return

    summary_session = {
        "summary": session.get("summary", ""),
        "messages": old_messages,
    }
    session["summary"] = summarize_session(summary_session, gemini_config, session_config)
    session["messages"] = messages[-max_recent:]


def default_audio_path(session_id: str, extension: str = "mp3") -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"turn-{session_id}-{timestamp}.{extension}"


def write_tts_audio(reply: str, tts_config_path: Path, out_arg: str | None, session_id: str, output_format: str | None) -> Path:
    tts_config = load_tts_config(tts_config_path)
    apply_desktop_output_format(tts_config, output_format)

    extension, sample_rate = audio_output_info(tts_config)
    audio_path = Path(out_arg) if out_arg else default_audio_path(session_id, extension)
    if not audio_path.is_absolute():
        audio_path = ROOT / audio_path
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    data = synthesize(reply, tts_config)
    if sample_rate:
        with wave.open(str(audio_path), "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(sample_rate)
            file.writeframes(data)
    else:
        audio_path.write_bytes(data)
    return audio_path


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def is_new_session_command(user_text: str) -> bool:
    return user_text.strip().lower() in NEW_SESSION_COMMANDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Gemini-native voice-assistant turn.")
    parser.add_argument("--text", help="User text. If omitted, stdin is used unless --audio is provided.")
    parser.add_argument("--audio", help="Audio file for Gemini to understand directly.")
    parser.add_argument("--audio-source", choices=["microphone", "desktop"], default="microphone")
    parser.add_argument("--image", action="append", default=[], help="Image attachment path for the same turn.")
    parser.add_argument("--out", help="Output mp3 path. Defaults to outputs/turn-SESSION-TIMESTAMP.mp3.")
    parser.add_argument("--new-session", action="store_true", help="Archive current session and start fresh.")
    parser.add_argument("--no-tts", action="store_true", help="Do not synthesize the assistant reply.")
    parser.add_argument("--tts-output-format", help="Override ElevenLabs output format, e.g. pcm_16000.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--gemini-config", default=str(DEFAULT_GEMINI_CONFIG))
    parser.add_argument("--tts-config", default=str(DEFAULT_TTS_CONFIG))
    parser.add_argument("--session-config", default=str(DEFAULT_SESSION_CONFIG))
    return parser


def execute_turn(args: argparse.Namespace) -> dict:
    session_config = load_json(Path(args.session_config))
    session, session_path = load_or_create_session(session_config, args.new_session)

    if args.new_session and not args.text and not args.audio:
        return {
            "session_id": session["id"],
            "event": "new_session",
            "session_path": str(session_path),
        }

    gemini_config = load_gemini_config(Path(args.gemini_config))
    persona = load_persona(gemini_config)
    max_recent = int(session_config.get("max_recent_messages", 12))

    if args.audio:
        image_paths = [Path(path) for path in (args.image or [])]
        user_text, reply = audio_reply(
            Path(args.audio),
            session,
            persona,
            gemini_config,
            max_recent,
            image_paths=image_paths,
            audio_source=args.audio_source,
        )
    elif args.text is not None:
        image_paths = []
        user_text = args.text.strip()
        if not user_text:
            raise SystemExit("Text is empty.")
        if is_new_session_command(user_text):
            session, session_path = load_or_create_session(session_config, True)
            reply = "好，已经开启新会话。我们从这里重新开始。"
        else:
            user_text, reply = text_reply(user_text, session, persona, gemini_config, max_recent)
    else:
        image_paths = []
        user_text = sys.stdin.read().strip()
        if not user_text:
            return {
                "session_id": session["id"],
                "event": "no_input",
                "session_path": str(session_path),
            }
        if is_new_session_command(user_text):
            session, session_path = load_or_create_session(session_config, True)
            reply = "好，已经开启新会话。我们从这里重新开始。"
        else:
            user_text, reply = text_reply(user_text, session, persona, gemini_config, max_recent)

    if args.audio and is_new_session_command(user_text):
        session, session_path = load_or_create_session(session_config, True)
        reply = "好，已经开启新会话。我们从这里重新开始。"

    append_turn(session, user_text, reply)
    summarize_if_needed(session, session_config, gemini_config)
    save_session(session, session_path)

    audio_path = None
    if not args.no_tts:
        audio_path = write_tts_audio(
            reply,
            Path(args.tts_config),
            args.out,
            session["id"],
            args.tts_output_format,
        )

    brain = "gemini_audio_direct"
    if active_provider(gemini_config) == "gateway":
        brain = f"gateway_{gateway_format(gemini_config)}"

    payload = {
        "brain": brain,
        "model": active_model_label(gemini_config),
        "session_id": session["id"],
        "session_path": str(session_path),
        "user_text": user_text,
        "assistant_text": reply,
        "audio_path": str(audio_path) if audio_path else None,
        "input_audio_source": args.audio_source if args.audio else None,
        "image_paths": [str(path) for path in image_paths],
    }
    return payload


def run_turn(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    return execute_turn(args)


def print_payload(payload: dict, json_mode: bool) -> None:
    if json_mode:
        print_json(payload)
        return

    event = payload.get("event")
    if event == "new_session":
        print(f"Session {payload['session_id']} ready: {payload['session_path']}")
    elif event == "no_input":
        print(f"Session {payload['session_id']} ready: {payload['session_path']}")
    else:
        print(f"Brain: {payload['brain']}")
        print(f"Session: {payload['session_id']}")
        print(f"User: {payload['user_text']}")
        print(f"Assistant: {payload['assistant_text']}")
        if payload.get("audio_path"):
            print(f"Saved audio: {payload['audio_path']}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = execute_turn(args)
    print_payload(payload, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
