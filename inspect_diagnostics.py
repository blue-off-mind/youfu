import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_LOG = ROOT / "logs" / "voice-turns.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect recent 幽浮 diagnostic records.")
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--last", type=int, default=12)
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"No diagnostic log found: {log_path}")
        return 0

    lines = log_path.read_text(encoding="utf-8").splitlines()[-args.last :]
    for line in lines:
        record = json.loads(line)
        audio = record.get("audio") or {}
        pieces = [
            record.get("ts", ""),
            record.get("event", ""),
            f"duration={audio.get('duration_ms', '-') }ms",
            f"rms={audio.get('rms', '-')}",
            f"peak={audio.get('peak', '-')}",
        ]
        if record.get("reason"):
            pieces.append(f"reason={record['reason']}")
        if record.get("brain"):
            pieces.append(f"brain={record['brain']}")
        if record.get("model"):
            pieces.append(f"model={record['model']}")
        if record.get("user_text"):
            pieces.append(f"user_text={record['user_text']}")
        if record.get("error"):
            pieces.append(f"error={record['error']}")
        if audio.get("path"):
            pieces.append(f"audio={audio['path']}")
        print(" | ".join(pieces))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
