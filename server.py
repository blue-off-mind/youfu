import json
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse


ROOT = Path(__file__).resolve().parent
TMP_DIR = ROOT / "tmp"
WEB_INDEX = ROOT / "web" / "index.html"

app = FastAPI(title="幽浮 Local Voice")


def run_voice_turn(args: list[str]) -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, str(ROOT / "voice_turn.py"), *args, "--json"]
    process = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=180,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "voice_turn.py failed"
        raise HTTPException(status_code=500, detail=detail)

    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid voice_turn.py JSON: {process.stdout}") from exc


def assert_project_path(path_value: str) -> Path:
    path = Path(path_value).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=403, detail="Path is outside this project.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return path


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_INDEX)


@app.post("/api/turn/text")
def turn_text(text: str = Form(...)) -> dict:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty.")
    return run_voice_turn(["--text", text])


@app.post("/api/turn/audio")
async def turn_audio(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "recording.webm").suffix or ".webm"
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = TMP_DIR / f"recording-{int(time.time() * 1000)}{suffix}"
    audio_path.write_bytes(await file.read())
    return run_voice_turn(["--audio", str(audio_path)])


@app.post("/api/session/new")
def session_new() -> dict:
    return run_voice_turn(["--new-session"])


@app.get("/api/audio")
def audio(path: str) -> FileResponse:
    audio_path = assert_project_path(path)
    return FileResponse(audio_path, media_type="audio/mpeg")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
