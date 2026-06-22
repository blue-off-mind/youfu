import argparse
import json
import os
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from pynput import mouse
from pynput.mouse import Button


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
TMP_DIR = ROOT / "tmp"


class HoldRecorder:
    def __init__(self, sample_rate: int, channels: int):
        self.sample_rate = sample_rate
        self.channels = channels
        self.stream = None
        self.chunks = []
        self.recording = False
        self.lock = threading.Lock()

    def start(self) -> None:
        with self.lock:
            if self.recording:
                return
            self.chunks = []
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._callback,
            )
            self.stream.start()
            self.recording = True
            print("Recording...")

    def stop(self) -> Path | None:
        with self.lock:
            if not self.recording:
                return None
            self.recording = False
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            if not self.chunks:
                print("No audio captured.")
                return None

            audio = np.concatenate(self.chunks, axis=0)
            TMP_DIR.mkdir(parents=True, exist_ok=True)
            path = TMP_DIR / f"hotkey-{int(time.time() * 1000)}.wav"
            with wave.open(str(path), "wb") as file:
                file.setnchannels(self.channels)
                file.setsampwidth(2)
                file.setframerate(self.sample_rate)
                file.writeframes(audio.tobytes())
            print(f"Captured: {path}")
            return path

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            print(status, file=sys.stderr)
        self.chunks.append(indata.copy())


def run_voice_turn(audio_path: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    command = [
        sys.executable,
        str(ROOT / "voice_turn.py"),
        "--audio",
        str(audio_path),
        "--json",
    ]
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
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return json.loads(process.stdout)


def play_audio(path_value: str | None, mode: str) -> None:
    if not path_value or mode == "none":
        return

    audio_path = Path(path_value)
    if mode == "open":
        os.startfile(audio_path)
        return

    raise RuntimeError(f"Unknown play mode: {mode}")


def button_from_name(name: str) -> Button:
    if name == "x1":
        return Button.x1
    if name == "x2":
        return Button.x2
    raise SystemExit("Button must be x1 or x2.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Hold a mouse side button to record one voice turn.")
    parser.add_argument("--button", choices=["x1", "x2"], default="x2", help="Mouse side button to use.")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--play", choices=["open", "none"], default="open")
    args = parser.parse_args()

    target_button = button_from_name(args.button)
    recorder = HoldRecorder(sample_rate=args.sample_rate, channels=args.channels)
    processing = threading.Event()

    def process_audio(audio_path: Path) -> None:
        if processing.is_set():
            return
        processing.set()
        try:
            print("Processing...")
            payload = run_voice_turn(audio_path)
            print("You:", payload.get("user_text"))
            print("Assistant:", payload.get("assistant_text"))
            play_audio(payload.get("audio_path"), args.play)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
        finally:
            processing.clear()
            print("Ready.")

    def on_click(x, y, button, pressed):
        if button != target_button:
            return
        if pressed:
            if not processing.is_set():
                recorder.start()
            return

        audio_path = recorder.stop()
        if audio_path:
            threading.Thread(target=process_audio, args=(audio_path,), daemon=True).start()

    print(f"Hold {args.button.upper()} to talk. Press Ctrl+C to exit.")
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
