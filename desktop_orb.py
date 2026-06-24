import argparse
import inspect
import json
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import wave
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk
try:
    import winreg
except ImportError:
    winreg = None
try:
    import winsound
except ImportError:
    winsound = None

import numpy as np
import sounddevice as sd
try:
    import soundcard as sc
except ImportError:
    sc = None
try:
    from PIL import Image, ImageGrab, ImageTk
except ImportError:
    Image = None
    ImageGrab = None
    ImageTk = None
from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button

from voice_turn import run_turn


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
TMP_DIR = ROOT / "tmp"
LOG_DIR = ROOT / "logs"
AI_CONFIG_PATH = ROOT / "gemini_config.json"
TTS_CONFIG_PATH = ROOT / "tts_config.json"
DESKTOP_CONFIG_PATH = ROOT / "desktop_config.json"
SKIN_DIR = ROOT / "skins"
TRANSPARENT = "#010203"
COMPACT_WIDTH = 202
COMPACT_HEIGHT = 218
BUBBLE_EXPANDED_HEIGHT = 430
STATUS_FILL = "#fff0b8"
STATUS_SHADOW = "#6b5732"
EDGE_DOCK_TRIGGER_DISTANCE = 96
DEFAULT_DESKTOP_CONFIG = {
    "button": "x2",
    "hotkey": {
        "type": "mouse",
        "value": "x2",
        "label": "侧键二",
    },
    "shortcuts": {
        "record_mic": {
            "type": "mouse",
            "value": "x2",
            "modifiers": [],
            "label": "侧键二",
        },
        "desktop_audio": {
            "type": "keyboard",
            "value": "char:3",
            "modifiers": ["ctrl"],
            "label": "Ctrl+3",
        },
        "screenshot": {
            "type": "keyboard",
            "value": "modifier:alt",
            "modifiers": [],
            "label": "Alt",
        },
        "cancel_recording": {
            "type": "mouse",
            "value": "middle",
            "modifiers": [],
            "label": "鼠标中键",
        },
    },
    "orb_name": "幽浮",
    "show_status_text": True,
    "status_visibility": "always",
    "status_parts": {
        "orb_name": True,
        "model": True,
        "action_hint": True,
    },
    "diagnostics_enabled": True,
    "ignore_short_recordings_ms": 350,
    "startup_enabled": False,
    "tts_output_format": "pcm_24000",
    "bubble_enabled": True,
    "record_start_delay_ms": 120,
    "skin": "default",
    "orb_size": 160,
    "idle_transparency_enabled": False,
    "idle_opacity": 0.6,
    "idle_edge_dock_enabled": False,
}
DEFAULT_SKIN = {
    "id": "default",
    "name": "纸片奶油",
    "colors": {
        "drop_shadow": "#000000",
        "paper": "#fff7e8",
        "orb_outer": "#f6ecd8",
        "orb_inner": "#fff3d8",
        "face": "#fff8e6",
        "ink": "#292b27",
        "bubble": "#fffaf0",
        "bubble_back": "#fff7e8",
        "bubble_shadow": "#b8cfb4",
        "bubble_toggle": "#fff0b8",
        "status_fill": "#fff0b8",
        "status_shadow": "#6b5732",
        "user_text": "#686b62",
        "reply_text": "#2d302c",
        "scroll_track": "#d7d0bd",
        "scroll_knob": "#b8cfb4",
        "tab_idle": "#bfe6c8",
        "tab_speaking": "#f8d781",
        "state_idle": "#86e889",
        "state_recording": "#ff725d",
        "state_connecting": "#69d7d0",
        "state_speaking": "#ffc857",
        "state_error": "#ff6b6b",
        "recording_halo": "#ffc5b8",
        "connecting_node": "#8adfd9",
        "connecting_arc": "#78d9d2",
        "hair": "#273854",
        "hair_highlight": "#687aa0",
        "ribbon": "#f8c84d",
        "cheek": "#f29d90",
    },
    "features": {
        "hair_bob": False,
        "side_ribbon": False,
        "dojo_marks": False,
        "blush": False,
    },
}
STARTUP_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_VALUE_NAME = "幽浮"
LEGACY_STARTUP_VALUE_NAMES = ("TTS-Orb",)
HOTKEY_LABELS = {
    "left": "鼠标左键",
    "right": "鼠标右键",
    "x2": "侧键二",
    "x1": "侧键一",
    "middle": "鼠标中键",
}
KEY_LABELS = {
    "alt": "Alt",
    "alt_l": "左 Alt",
    "alt_r": "右 Alt",
    "backspace": "退格",
    "caps_lock": "Caps Lock",
    "cmd": "Win",
    "cmd_l": "左 Win",
    "cmd_r": "右 Win",
    "ctrl": "Ctrl",
    "ctrl_l": "左 Ctrl",
    "ctrl_r": "右 Ctrl",
    "delete": "Delete",
    "down": "方向键下",
    "end": "End",
    "enter": "Enter",
    "esc": "Esc",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
    "home": "Home",
    "insert": "Insert",
    "left": "方向键左",
    "menu": "菜单键",
    "page_down": "Page Down",
    "page_up": "Page Up",
    "right": "方向键右",
    "shift": "Shift",
    "shift_l": "左 Shift",
    "shift_r": "右 Shift",
    "space": "空格",
    "tab": "Tab",
    "up": "方向键上",
}
MODIFIER_ORDER = ("ctrl", "alt", "shift", "cmd")
MODIFIER_LABELS = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "cmd": "Win",
}
SHORTCUT_ACTIONS = (
    ("record_mic", "按住录音", "按住后开始麦克风录音，松开发送。"),
    ("desktop_audio", "桌面音频", "按住后录制系统播放声音，松开发送。"),
    ("screenshot", "添加截图", "麦克风录音中按下时，附加当前桌面截图。"),
    ("cancel_recording", "取消录音", "录音中按下时，丢弃本次录音并回到待机。"),
)


def load_json_file(path: Path, default: dict) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(default)
    except json.JSONDecodeError:
        return dict(default)
    result = {**default, **data}
    if isinstance(default.get("status_parts"), dict):
        result["status_parts"] = {
            **default["status_parts"],
            **(data.get("status_parts") if isinstance(data.get("status_parts"), dict) else {}),
        }
    if isinstance(default.get("hotkey"), dict):
        hotkey_data = data.get("hotkey") if isinstance(data.get("hotkey"), dict) else {}
        result["hotkey"] = {**default["hotkey"], **hotkey_data}
        if "hotkey" not in data and data.get("button"):
            button = str(data.get("button"))
            result["hotkey"] = {
                "type": "mouse",
                "value": button,
                "label": HOTKEY_LABELS.get(button, button),
            }
    if isinstance(default.get("shortcuts"), dict):
        shortcut_data = data.get("shortcuts") if isinstance(data.get("shortcuts"), dict) else {}
        result["shortcuts"] = {}
        for action, fallback in default["shortcuts"].items():
            configured = shortcut_data.get(action) if isinstance(shortcut_data.get(action), dict) else {}
            result["shortcuts"][action] = {**fallback, **configured}
        if "shortcuts" not in data and isinstance(result.get("hotkey"), dict):
            result["shortcuts"]["record_mic"] = {
                **default["shortcuts"]["record_mic"],
                **result["hotkey"],
            }
    if "status_visibility" not in data:
        result["status_visibility"] = "always" if result.get("show_status_text", True) else "never"
    return result


def save_json_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_skins() -> dict[str, dict]:
    skins = {DEFAULT_SKIN["id"]: DEFAULT_SKIN}
    if not SKIN_DIR.exists():
        return skins

    for path in sorted(SKIN_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        skin_id = str(data.get("id") or path.stem).strip()
        if not skin_id:
            continue
        skin = deep_merge(DEFAULT_SKIN, data)
        skin["id"] = skin_id
        skin["name"] = str(skin.get("name") or skin_id)
        skins[skin_id] = skin
    return skins


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audio_stats(audio_path: Path) -> dict:
    with wave.open(str(audio_path), "rb") as file:
        sample_rate = file.getframerate()
        channels = file.getnchannels()
        frames_count = file.getnframes()
        raw = file.readframes(frames_count)

    data = np.frombuffer(raw, dtype=np.int16)
    duration_ms = (frames_count / sample_rate * 1000) if sample_rate else 0
    if data.size:
        values = data.astype(np.float32)
        rms = float(np.sqrt(np.mean(values * values)))
        peak = int(np.max(np.abs(data.astype(np.int32))))
        mean_abs = float(np.mean(np.abs(values)))
    else:
        rms = 0.0
        peak = 0
        mean_abs = 0.0

    return {
        "path": str(audio_path),
        "bytes": audio_path.stat().st_size if audio_path.exists() else 0,
        "duration_ms": round(duration_ms, 1),
        "sample_rate": sample_rate,
        "channels": channels,
        "frames": frames_count,
        "rms": round(rms, 2),
        "peak": peak,
        "mean_abs": round(mean_abs, 2),
    }


def quoted(path: Path) -> str:
    return f'"{path}"'


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return quoted(Path(sys.executable).resolve())

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else Path(sys.executable)
    return f"{quoted(runner.resolve())} {quoted(Path(__file__).resolve())}"


def is_startup_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_PATH) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_VALUE_NAME)
        return str(value).strip() == startup_command()
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    if winreg is None:
        raise RuntimeError("当前系统不支持 Windows 开机启动注册表。")

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        STARTUP_REG_PATH,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        for legacy_name in LEGACY_STARTUP_VALUE_NAMES:
            try:
                winreg.DeleteValue(key, legacy_name)
            except FileNotFoundError:
                pass
        if enabled:
            winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, STARTUP_VALUE_NAME)
            except FileNotFoundError:
                pass


class SoundDevicePlayer:
    def play_wait(self, audio_path: Path) -> None:
        if audio_path.suffix.lower() != ".wav":
            raise RuntimeError(f"Desktop playback expects WAV audio, got: {audio_path.name}")

        with wave.open(str(audio_path), "rb") as file:
            sample_rate = file.getframerate()
            channels = file.getnchannels()
            frame_count = file.getnframes()
            frames = file.readframes(frame_count)
        duration = frame_count / sample_rate if sample_rate else 0.0

        started = time.monotonic()
        played = False
        if winsound is not None:
            try:
                winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
                played = True
            except RuntimeError:
                played = False
        if not played:
            data = np.frombuffer(frames, dtype=np.int16)
            if channels > 1:
                data = data.reshape(-1, channels)
            sd.play(data, sample_rate)
            sd.wait()

        elapsed = time.monotonic() - started
        if duration > elapsed:
            time.sleep(duration - elapsed)
        time.sleep(0.18)


class HoldRecorder:
    def __init__(self, sample_rate: int, channels: int):
        self.sample_rate = sample_rate
        self.channels = channels
        self.stream = None
        self.chunks = []
        self.recording = False
        self.lock = threading.Lock()

    def start(self) -> bool:
        with self.lock:
            if self.recording:
                return False
            self.chunks = []
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._callback,
            )
            self.stream.start()
            self.recording = True
            return True

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
                return None

            audio = np.concatenate(self.chunks, axis=0)
            TMP_DIR.mkdir(parents=True, exist_ok=True)
            path = TMP_DIR / f"desktop-orb-{int(time.time() * 1000)}.wav"
            with wave.open(str(path), "wb") as file:
                file.setnchannels(self.channels)
                file.setsampwidth(2)
                file.setframerate(self.sample_rate)
                file.writeframes(audio.tobytes())
            return path

    def _callback(self, indata, frames, time_info, status) -> None:
        self.chunks.append(indata.copy())


class DesktopAudioRecorder(HoldRecorder):
    def __init__(self):
        super().__init__(sample_rate=48000, channels=2)
        self.device = None
        self.backend = None
        self.worker = None
        self.soundcard_context = None
        self.soundcard_recorder = None
        self.soundcard_error = None

    def start(self) -> bool:
        if sc is not None:
            return self._start_soundcard()
        return self._start_sounddevice_loopback()

    def stop(self) -> Path | None:
        if self.backend == "soundcard":
            return self._stop_soundcard()
        return super().stop()

    def _start_soundcard(self) -> bool:
        with self.lock:
            if self.recording:
                return False
            speaker = sc.default_speaker()
            microphone = sc.get_microphone(speaker.name, include_loopback=True)
            self.channels = min(2, max(1, int(getattr(microphone, "channels", 2) or 2)))
            self.sample_rate = 48000
            self.chunks = []
            self.backend = "soundcard"
            self.soundcard_error = None
            self.soundcard_context = microphone.recorder(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=1024,
            )
            self.soundcard_recorder = self.soundcard_context.__enter__()
            self.recording = True
            self.worker = threading.Thread(target=self._soundcard_loop, daemon=True)
            self.worker.start()
            return True

    def _soundcard_loop(self) -> None:
        block_frames = max(1024, int(self.sample_rate * 0.08))
        try:
            while True:
                with self.lock:
                    if not self.recording:
                        break
                    recorder = self.soundcard_recorder
                if recorder is None:
                    break
                data = recorder.record(numframes=block_frames)
                if data is None or not len(data):
                    continue
                data = np.asarray(data)
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                if data.shape[1] > self.channels:
                    data = data[:, : self.channels]
                pcm = np.clip(data, -1.0, 1.0)
                pcm = (pcm * 32767).astype(np.int16)
                with self.lock:
                    if self.recording:
                        self.chunks.append(pcm.copy())
        except Exception as exc:
            with self.lock:
                self.soundcard_error = exc
                self.recording = False

    def _stop_soundcard(self) -> Path | None:
        with self.lock:
            if not self.recording and not self.chunks:
                if self.soundcard_error:
                    raise RuntimeError(f"Desktop audio capture failed: {self.soundcard_error}")
                return None
            self.recording = False
            worker = self.worker
            context = self.soundcard_context
            error = self.soundcard_error

        if worker:
            worker.join(timeout=1.5)

        if context:
            try:
                context.__exit__(None, None, None)
            finally:
                self.soundcard_context = None
                self.soundcard_recorder = None
                self.worker = None

        if error and not self.chunks:
            raise RuntimeError(f"Desktop audio capture failed: {error}")
        if not self.chunks:
            return None

        audio = np.concatenate(self.chunks, axis=0)
        self.chunks = []
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        path = TMP_DIR / f"desktop-orb-{int(time.time() * 1000)}.wav"
        with wave.open(str(path), "wb") as file:
            file.setnchannels(self.channels)
            file.setsampwidth(2)
            file.setframerate(self.sample_rate)
            file.writeframes(audio.tobytes())
        return path

    def _start_sounddevice_loopback(self) -> bool:
        with self.lock:
            if self.recording:
                return False
            if not hasattr(sd, "WasapiSettings"):
                raise RuntimeError("Current PortAudio build does not support WASAPI loopback.")
            if "loopback" not in inspect.signature(sd.WasapiSettings).parameters:
                raise RuntimeError("Install the soundcard package to capture desktop audio loopback.")

            device = self._wasapi_output_device()
            info = sd.query_devices(device)
            channels = min(2, max(1, int(info.get("max_output_channels") or 0)))
            if channels <= 0:
                raise RuntimeError("Default desktop output device has no output channels.")

            self.device = device
            self.backend = "sounddevice"
            self.channels = channels
            self.sample_rate = int(float(info.get("default_samplerate") or self.sample_rate))
            self.chunks = []
            self.stream = sd.InputStream(
                device=device,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._callback,
                extra_settings=sd.WasapiSettings(loopback=True),
            )
            self.stream.start()
            self.recording = True
            return True

    def _wasapi_output_device(self) -> int:
        try:
            default_device = sd.default.device
            default_output = default_device[1] if isinstance(default_device, (list, tuple)) else default_device
            if default_output is not None and int(default_output) >= 0:
                info = sd.query_devices(int(default_output))
                if self._is_wasapi_device(info) and int(info.get("max_output_channels") or 0) > 0:
                    return int(default_output)
        except Exception:
            pass

        hostapis = sd.query_hostapis()
        for hostapi_index, hostapi in enumerate(hostapis):
            if "WASAPI" not in str(hostapi.get("name", "")).upper():
                continue
            default_output_value = hostapi.get("default_output_device", -1)
            default_output = int(default_output_value) if default_output_value is not None else -1
            if default_output >= 0:
                return default_output
            for device_index, info in enumerate(sd.query_devices()):
                if int(info.get("hostapi", -1)) == hostapi_index and int(info.get("max_output_channels") or 0) > 0:
                    return device_index
        raise RuntimeError("No WASAPI desktop output device was found.")

    def _is_wasapi_device(self, info: dict) -> bool:
        try:
            hostapi = sd.query_hostapis(int(info.get("hostapi", -1)))
            return "WASAPI" in str(hostapi.get("name", "")).upper()
        except Exception:
            return False


class DesktopOrb:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.desktop_config = load_json_file(DESKTOP_CONFIG_PATH, DEFAULT_DESKTOP_CONFIG)
        if args.button:
            self.desktop_config["button"] = args.button
            self.desktop_config["hotkey"] = self.mouse_hotkey_binding(args.button)
        if args.tts_output_format:
            self.desktop_config["tts_output_format"] = args.tts_output_format
        self.ai_config = load_json_file(AI_CONFIG_PATH, {})
        self.tts_config = load_json_file(TTS_CONFIG_PATH, {})
        self.skins = load_skins()
        self.skin = self.active_skin()
        self.skin_images = {}

        self.root = tk.Tk()
        self.root.title("幽浮")
        self.window_x = args.x
        self.window_y = args.y
        self.undocked_x = args.x
        self.undocked_y = args.y
        self.edge_docked = False
        self.edge_dock_edge = None
        self.window_width = args.width
        self.window_height = args.height
        self.root.geometry(f"{args.width}x{args.height}+{self.window_x}+{self.window_y}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT)

        self.canvas = tk.Canvas(
            self.root,
            width=args.width,
            height=args.height,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.state = "idle"
        self.status = "待机，长按侧键二说话"
        self.user_text = ""
        self.full_reply = ""
        self.visible_reply = ""
        self.drag_start = None
        self.drag_moved = False
        self.hovering = False
        self.pressed_keys = set()
        self.pressed_mouse_buttons = set()
        self.pressed_modifiers = set()
        self.shortcut_hold_down = {
            "record_mic": False,
            "desktop_audio": False,
        }
        self.shortcut_once_down = {
            "screenshot": False,
            "cancel_recording": False,
        }
        self.bubble_expanded = False
        self.bubble_hidden = False
        self.bubble_scroll = 0
        self.bubble_max_scroll = 0
        self.bubble_toggle_bounds = None
        self.hint_close_bounds = None
        self.closed_hint_text = None
        self.hotkey_down = False
        self.ctrl_down = False
        self.desktop_audio_key_down = False
        self.alt_screenshot_down = False
        self.recording_mode = None
        self.pending_image_paths = []
        self.pending_record_start_id = None
        self.hotkey_capture_active = False
        self.processing = threading.Event()
        self.recorder = HoldRecorder(sample_rate=args.sample_rate, channels=args.channels)
        self.desktop_recorder = DesktopAudioRecorder()
        self.player = SoundDevicePlayer()
        self.context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#fffaf0",
            fg="#2d302c",
            activebackground="#fff0b8",
            activeforeground="#2d302c",
            relief="flat",
        )

        self.root.bind("<ButtonPress-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.drag)
        self.root.bind("<ButtonRelease-1>", self.end_drag)
        self.root.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<Escape>", lambda event: self.close())
        self.canvas.bind("<Enter>", self.on_hover_enter)
        self.canvas.bind("<Leave>", self.on_hover_leave)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_click, add="+")
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.mouse_listener = None
        self.keyboard_listener = None
        if not args.no_hotkey:
            self.mouse_listener = mouse.Listener(on_click=self.on_global_click)
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_global_key_press,
                on_release=self.on_global_key_release,
            )
            self.mouse_listener.start()
            self.keyboard_listener.start()

        self.render()

    def start_drag(self, event) -> None:
        self.drag_start = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.drag_moved = False

    def drag(self, event) -> None:
        if not self.drag_start:
            return
        start_x, start_y, root_x, root_y = self.drag_start
        if abs(event.x_root - start_x) > 6 or abs(event.y_root - start_y) > 6:
            self.drag_moved = True
        self.window_x = root_x + event.x_root - start_x
        self.window_y = root_y + event.y_root - start_y
        self.root.geometry(f"+{self.window_x}+{self.window_y}")

    def end_drag(self, event) -> None:
        moved = self.drag_moved
        self.drag_start = None
        if moved:
            self.edge_docked = False
            self.edge_dock_edge = None
            self.undocked_x = self.window_x
            self.undocked_y = self.window_y
            self.render()
        self.root.after_idle(lambda: setattr(self, "drag_moved", False))

    def on_hover_enter(self, event) -> None:
        self.hovering = True
        if self.edge_docked:
            self.restore_from_edge_dock()
            self.apply_window_opacity()
        self.render()

    def on_hover_leave(self, event) -> None:
        self.hovering = False
        self.render()

    def on_canvas_click(self, event) -> None:
        if self.drag_moved:
            return
        if self.drag_start:
            start_x, start_y, _, _ = self.drag_start
            if abs(event.x_root - start_x) > 6 or abs(event.y_root - start_y) > 6:
                return
        if self.hint_close_bounds:
            x1, y1, x2, y2 = self.hint_close_bounds
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.closed_hint_text = self.action_hint_text()
                self.render()
                return
        if not self.bubble_toggle_bounds:
            return
        x1, y1, x2, y2 = self.bubble_toggle_bounds
        if x1 <= event.x <= x2 and y1 <= event.y <= y2:
            self.toggle_bubble()

    def on_mouse_wheel(self, event) -> str | None:
        if not self.bubble_expanded or not self.bubble_visible() or self.bubble_max_scroll <= 0:
            return None
        step = -3 if event.delta > 0 else 3
        self.bubble_scroll = max(0, min(self.bubble_max_scroll, self.bubble_scroll + step))
        self.render()
        return "break"

    def toggle_bubble(self) -> None:
        if not self.bubble_visible():
            return
        self.bubble_expanded = not self.bubble_expanded
        self.bubble_scroll = 0
        self.render()

    def close_dialogue(self) -> None:
        self.bubble_hidden = True
        self.bubble_expanded = False
        self.bubble_scroll = 0
        self.render()

    def mouse_button_value(self, button: Button) -> str:
        if button == Button.left:
            return "left"
        if button == Button.right:
            return "right"
        if button == Button.middle:
            return "middle"
        if button == Button.x1:
            return "x1"
        if button == Button.x2:
            return "x2"
        return getattr(button, "name", str(button).replace("Button.", ""))

    def sorted_modifiers(self, modifiers) -> list[str]:
        modifier_set = {str(modifier) for modifier in (modifiers or []) if str(modifier) in MODIFIER_ORDER}
        return [modifier for modifier in MODIFIER_ORDER if modifier in modifier_set]

    def mouse_hotkey_binding(self, value: str | Button, modifiers=None) -> dict:
        button_value = self.mouse_button_value(value) if isinstance(value, Button) else str(value)
        binding = {
            "type": "mouse",
            "value": button_value,
            "modifiers": self.sorted_modifiers(modifiers),
        }
        binding["label"] = self.shortcut_binding_label(binding)
        return binding

    def modifier_name_for_key(self, key) -> str | None:
        if key in {Key.ctrl, Key.ctrl_l, Key.ctrl_r}:
            return "ctrl"
        alt_keys = {Key.alt, Key.alt_l, Key.alt_r}
        alt_gr = getattr(Key, "alt_gr", None)
        if alt_gr is not None:
            alt_keys.add(alt_gr)
        if key in alt_keys:
            return "alt"
        if key in {Key.shift, Key.shift_l, Key.shift_r}:
            return "shift"
        cmd_keys = {value for value in (getattr(Key, "cmd", None), getattr(Key, "cmd_l", None), getattr(Key, "cmd_r", None)) if value is not None}
        if key in cmd_keys:
            return "cmd"
        return None

    def keyboard_key_value(self, key) -> str:
        modifier = self.modifier_name_for_key(key)
        if modifier:
            return f"modifier:{modifier}"
        if isinstance(key, KeyCode):
            if key.char:
                return f"char:{key.char.lower()}"
            if key.vk is not None:
                return f"vk:{key.vk}"
        if isinstance(key, Key):
            return f"key:{key.name}"
        return str(key)

    def keyboard_hotkey_label(self, value: str) -> str:
        if value.startswith("modifier:"):
            modifier = value.split(":", 1)[1]
            return MODIFIER_LABELS.get(modifier, modifier.title())
        if value.startswith("char:"):
            char = value.split(":", 1)[1]
            return char.upper() if len(char) == 1 else char
        if value.startswith("key:"):
            key_name = value.split(":", 1)[1]
            return KEY_LABELS.get(key_name, key_name.replace("_", " ").title())
        if value.startswith("vk:"):
            return f"VK {value.split(':', 1)[1]}"
        return value

    def keyboard_hotkey_binding(self, key, modifiers=None) -> dict:
        value = self.keyboard_key_value(key)
        binding = {
            "type": "keyboard",
            "value": value,
            "modifiers": self.sorted_modifiers(modifiers),
        }
        binding["label"] = self.shortcut_binding_label(binding)
        return binding

    def shortcut_binding_label(self, binding: dict | None) -> str:
        if not binding:
            return "未设置"
        modifiers = self.sorted_modifiers(binding.get("modifiers"))
        main_type = str(binding.get("type") or "")
        main_value = str(binding.get("value") or "")
        labels = [MODIFIER_LABELS.get(modifier, modifier.title()) for modifier in modifiers]
        if main_type == "mouse":
            labels.append(HOTKEY_LABELS.get(main_value, f"鼠标 {main_value}"))
        elif main_type == "keyboard":
            main_label = self.keyboard_hotkey_label(main_value)
            if not (main_value.startswith("modifier:") and main_value.split(":", 1)[1] in modifiers):
                labels.append(main_label)
        elif main_value:
            labels.append(main_value)
        return "+".join(label for label in labels if label) or "未设置"

    def normalize_shortcut_binding(self, binding: dict | None, fallback: dict) -> dict:
        source = binding if isinstance(binding, dict) else {}
        result = {
            "type": str(source.get("type") or fallback.get("type") or "mouse"),
            "value": str(source.get("value") or fallback.get("value") or "x2"),
            "modifiers": self.sorted_modifiers(source.get("modifiers", fallback.get("modifiers", []))),
        }
        result["label"] = self.shortcut_binding_label(result)
        return result

    def shortcut_binding(self, action: str, config: dict | None = None) -> dict:
        source = config if config is not None else self.desktop_config
        defaults = DEFAULT_DESKTOP_CONFIG["shortcuts"]
        fallback = defaults.get(action, defaults["record_mic"])
        shortcuts = source.get("shortcuts") if isinstance(source.get("shortcuts"), dict) else {}
        configured = shortcuts.get(action) if isinstance(shortcuts.get(action), dict) else None
        if action == "record_mic" and configured is None:
            configured = source.get("hotkey") if isinstance(source.get("hotkey"), dict) else None
        return self.normalize_shortcut_binding(configured, fallback)

    def shortcut_label(self, action: str, binding: dict | None = None) -> str:
        return self.shortcut_binding_label(binding or self.shortcut_binding(action))

    def trigger_binding(self, config: dict | None = None) -> dict:
        return self.shortcut_binding("record_mic", config)

    def hotkey_binding_label(self, binding: dict | None = None) -> str:
        return self.shortcut_binding_label(binding or self.trigger_binding())

    def mouse_matches_trigger(self, button: Button) -> bool:
        binding = self.shortcut_binding("record_mic")
        return binding.get("type") == "mouse" and binding.get("value") == self.mouse_button_value(button)

    def keyboard_matches_trigger(self, key) -> bool:
        binding = self.shortcut_binding("record_mic")
        return binding.get("type") == "keyboard" and binding.get("value") == self.keyboard_key_value(key)

    def is_ctrl_key(self, key) -> bool:
        return self.modifier_name_for_key(key) == "ctrl"

    def is_alt_key(self, key) -> bool:
        return self.modifier_name_for_key(key) == "alt"

    def is_desktop_audio_key(self, key) -> bool:
        return self.keyboard_key_value(key) in {"char:3", "vk:51", "vk:99"}

    def active_skin(self) -> dict:
        skin_id = str(self.desktop_config.get("skin") or "default")
        return self.skins.get(skin_id) or self.skins.get("default") or DEFAULT_SKIN

    def skin_color(self, key: str) -> str:
        colors = self.skin.get("colors", {})
        return colors.get(key) or DEFAULT_SKIN["colors"].get(key, "#000000")

    def skin_feature(self, key: str) -> bool:
        features = self.skin.get("features", {})
        return bool(features.get(key, DEFAULT_SKIN["features"].get(key, False)))

    def state_accent(self, state: str | None = None) -> str:
        return self.skin_color(f"state_{state or self.state}")

    def orb_size(self) -> int:
        try:
            value = int(float(self.desktop_config.get("orb_size", 160)))
        except (TypeError, ValueError):
            value = 160
        return max(96, min(240, value))

    def image_background_padding(self) -> int:
        image_background = self.skin.get("image_background")
        if isinstance(image_background, dict) and image_background.get("enabled", True):
            try:
                return max(0, int(image_background.get("padding", 5)))
            except (TypeError, ValueError):
                return 5
        return 0

    def orb_visual_size(self) -> int:
        if isinstance(self.skin.get("image_states"), dict):
            return self.orb_size() + self.image_background_padding() * 2 + 8
        return 172

    def status_area_enabled(self) -> bool:
        return self.desktop_config.get("status_visibility", "always") != "never"

    def idle_opacity(self) -> float:
        try:
            opacity = float(self.desktop_config.get("idle_opacity", 0.6))
        except (TypeError, ValueError):
            opacity = 0.6
        if opacity > 1:
            opacity = opacity / 100
        return max(0.0, min(1.0, opacity))

    def target_window_opacity(self) -> float:
        if self.hovering:
            return 1.0
        if not self.desktop_config.get("idle_transparency_enabled", False):
            return 1.0
        if self.state != "idle":
            return 1.0
        if self.processing.is_set():
            return 1.0
        if self.hotkey_down or self.pending_record_start_id:
            return 1.0
        if self.recorder.recording or self.desktop_recorder.recording:
            return 1.0
        return self.idle_opacity()

    def set_window_opacity(self, opacity: float) -> None:
        try:
            self.root.attributes("-alpha", opacity)
            self.current_window_opacity = opacity
        except tk.TclError:
            pass

    def apply_window_opacity(self, force: bool = False) -> None:
        opacity = self.target_window_opacity()
        if not force and getattr(self, "current_window_opacity", None) == opacity:
            return
        self.set_window_opacity(opacity)

    def screen_bounds(self) -> tuple[int, int, int, int]:
        try:
            x = int(self.root.winfo_vrootx())
            y = int(self.root.winfo_vrooty())
            width = int(self.root.winfo_vrootwidth())
            height = int(self.root.winfo_vrootheight())
        except tk.TclError:
            x, y, width, height = 0, 0, 0, 0
        if width <= 1 or height <= 1:
            width = int(self.root.winfo_screenwidth())
            height = int(self.root.winfo_screenheight())
            x, y = 0, 0
        return x, y, width, height

    def clamp_window_position(self, x: int, y: int) -> tuple[int, int]:
        screen_x, screen_y, screen_width, screen_height = self.screen_bounds()
        max_x = screen_x + max(0, screen_width - self.window_width)
        max_y = screen_y + max(0, screen_height - self.window_height)
        return max(screen_x, min(x, max_x)), max(screen_y, min(y, max_y))

    def move_window(self, x: int, y: int) -> None:
        x = int(round(x))
        y = int(round(y))
        if x == self.window_x and y == self.window_y:
            return
        self.window_x = x
        self.window_y = y
        self.root.geometry(f"{self.window_width}x{self.window_height}+{self.window_x}+{self.window_y}")

    def idle_edge_dock_enabled(self) -> bool:
        return bool(self.desktop_config.get("idle_edge_dock_enabled", False))

    def should_edge_dock(self) -> bool:
        if not self.idle_edge_dock_enabled():
            return False
        if self.hovering:
            return False
        if self.state != "idle":
            return False
        if self.processing.is_set():
            return False
        if self.hotkey_down or self.pending_record_start_id:
            return False
        if self.recorder.recording or self.desktop_recorder.recording:
            return False
        if self.drag_start:
            return False
        if self.bubble_visible():
            return False
        return self.dockable_edge() is not None

    def edge_dock_reference_width(self) -> int:
        width, _ = self.base_compact_dimensions()
        return width

    def dockable_edge(self) -> str | None:
        screen_x, _, screen_width, _ = self.screen_bounds()
        left_distance = self.undocked_x - screen_x
        right_distance = screen_x + screen_width - (self.undocked_x + self.edge_dock_reference_width())
        near_left = left_distance <= EDGE_DOCK_TRIGGER_DISTANCE
        near_right = right_distance <= EDGE_DOCK_TRIGGER_DISTANCE
        if near_left and near_right:
            return "left" if left_distance <= right_distance else "right"
        if near_left:
            return "left"
        if near_right:
            return "right"
        return None

    def docked_position(self, edge: str) -> tuple[int, int]:
        screen_x, screen_y, screen_width, screen_height = self.screen_bounds()
        reference_width = self.edge_dock_reference_width()
        exposed_width = max(1, reference_width // 3)
        y = max(screen_y, min(self.undocked_y, screen_y + max(0, screen_height - self.window_height)))
        if edge == "left":
            return screen_x - (reference_width - exposed_width), y
        return screen_x + screen_width - exposed_width, y

    def restore_from_edge_dock(self) -> None:
        if not self.edge_docked:
            return
        self.edge_docked = False
        self.edge_dock_edge = None
        x, y = self.clamp_window_position(self.undocked_x, self.undocked_y)
        self.move_window(x, y)

    def apply_edge_dock(self) -> None:
        edge = self.dockable_edge()
        if self.should_edge_dock() and edge:
            if not self.edge_docked:
                self.undocked_x, self.undocked_y = self.clamp_window_position(self.window_x, self.window_y)
                self.edge_dock_edge = edge
                self.edge_docked = True
            x, y = self.docked_position(self.edge_dock_edge or edge)
            self.move_window(x, y)
        else:
            self.restore_from_edge_dock()

    def status_font_size(self) -> int:
        return max(9, min(16, round(10 * self.orb_size() / 160)))

    def status_area_height(self) -> int:
        return self.status_font_size() * 3 + 14 if self.status_area_enabled() else 12

    def hint_font_size(self) -> int:
        return max(9, min(14, round(10 * self.orb_size() / 160)))

    def hint_bubble_size(self) -> tuple[int, int]:
        font_spec = ("Microsoft YaHei UI", self.hint_font_size(), "bold")
        font = tkfont.Font(root=self.root, font=font_spec)
        text = self.action_hint_text()
        max_text_width = max(142, min(218, self.orb_visual_size()))
        lines = self.wrap_text_to_width(text, font, max_text_width)
        line_count = max(1, min(3, len(lines)))
        line_height = max(font.metrics("linespace"), 14)
        width = max(168, min(246, max_text_width + 38))
        height = max(58, min(104, 28 + line_height * line_count))
        return width, height

    def base_compact_dimensions(self) -> tuple[int, int]:
        visual = self.orb_visual_size()
        width = max(COMPACT_WIDTH, visual + 34)
        height = max(190, 14 + visual + self.status_area_height())
        return width, height

    def compact_dimensions(self) -> tuple[int, int]:
        visual = self.orb_visual_size()
        width, height = self.base_compact_dimensions()
        if self.hint_bubble_visible():
            hint_width, _ = self.hint_bubble_size()
            width = max(width, visual + hint_width + 46)
        return width, height

    def bubble_left_edge(self) -> int:
        return max(165, self.orb_visual_size() + 36)

    def orb_center(self) -> tuple[int, int]:
        visual = self.orb_visual_size()
        if self.bubble_visible():
            x = max(86, self.bubble_left_edge() // 2 - 6)
        elif self.hint_bubble_visible():
            x = max(86, visual // 2 + 18)
        else:
            x = self.window_width // 2
        y = 14 + visual // 2
        return x, y

    def status_position(self) -> tuple[int, int, int]:
        visual = self.orb_visual_size()
        y = 14 + visual + self.status_area_height() // 2
        if self.hint_bubble_visible():
            width = max(156, visual + 20)
            return self.orb_center()[0], y, width
        width = max(156, self.window_width - 26)
        return self.window_width // 2, y, width

    def hint_bubble_position(self) -> tuple[int, int, int, int]:
        ox, oy = self.orb_center()
        visual = self.orb_visual_size()
        width, height = self.hint_bubble_size()
        x1 = min(self.window_width - width - 10, ox + visual // 2 - 6)
        y1 = max(10, oy - visual // 2 + 18)
        return x1, y1, x1 + width, y1 + height

    def skin_asset_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT / path

    def skin_image_for_state(self, state: str | None = None) -> tk.PhotoImage | None:
        image_states = self.skin.get("image_states")
        if not isinstance(image_states, dict):
            return None
        state_key = state or self.state
        image_value = image_states.get(state_key) or image_states.get("idle")
        if not image_value:
            return None
        image_path = self.skin_asset_path(str(image_value))
        cache_key = f"{image_path}|{self.orb_size()}"
        if cache_key not in self.skin_images:
            try:
                if Image is not None and ImageTk is not None:
                    image = Image.open(image_path).convert("RGBA")
                    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
                    image = image.resize((self.orb_size(), self.orb_size()), resampling)
                    self.skin_images[cache_key] = ImageTk.PhotoImage(image)
                else:
                    self.skin_images[cache_key] = tk.PhotoImage(file=str(image_path))
            except (OSError, tk.TclError):
                self.skin_images[cache_key] = None
        return self.skin_images[cache_key]

    def shortcut_active(self, action: str) -> bool:
        binding = self.shortcut_binding(action)
        main_type = binding.get("type")
        main_value = binding.get("value")
        if main_type == "mouse":
            main_down = main_value in self.pressed_mouse_buttons
        elif main_type == "keyboard":
            main_down = main_value in self.pressed_keys
        else:
            main_down = False
        if not main_down:
            return False
        return all(modifier in self.pressed_modifiers for modifier in binding.get("modifiers", []))

    def has_recording_to_cancel(self) -> bool:
        return bool(
            self.pending_record_start_id
            or self.state == "recording"
            or self.recorder.recording
            or self.desktop_recorder.recording
        )

    def update_hold_shortcuts(self) -> None:
        record_active = self.shortcut_active("record_mic")
        if record_active and not self.shortcut_hold_down["record_mic"]:
            self.shortcut_hold_down["record_mic"] = True
            self.root.after(0, self.handle_hotkey_press)
        elif not record_active and self.shortcut_hold_down["record_mic"]:
            self.shortcut_hold_down["record_mic"] = False
            self.root.after(0, self.handle_hotkey_release)

        desktop_active = self.shortcut_active("desktop_audio")
        if desktop_active and not self.shortcut_hold_down["desktop_audio"]:
            self.shortcut_hold_down["desktop_audio"] = True
            self.root.after(0, self.handle_desktop_audio_press)
        elif not desktop_active and self.shortcut_hold_down["desktop_audio"]:
            self.shortcut_hold_down["desktop_audio"] = False
            self.root.after(0, self.handle_desktop_audio_release)

    def update_once_shortcuts(self) -> None:
        screenshot_active = self.shortcut_active("screenshot")
        if screenshot_active and not self.shortcut_once_down["screenshot"]:
            self.shortcut_once_down["screenshot"] = True
            if self.state == "recording" and self.recording_mode == "mic":
                self.root.after(0, self.capture_screenshot_attachment)
        elif not screenshot_active:
            self.shortcut_once_down["screenshot"] = False

        cancel_active = self.shortcut_active("cancel_recording")
        if cancel_active and not self.shortcut_once_down["cancel_recording"]:
            self.shortcut_once_down["cancel_recording"] = True
            if self.has_recording_to_cancel():
                self.root.after(0, self.cancel_recording)
        elif not cancel_active:
            self.shortcut_once_down["cancel_recording"] = False

    def update_shortcut_actions(self) -> None:
        self.update_hold_shortcuts()
        self.update_once_shortcuts()

    def on_global_click(self, x, y, button, pressed) -> None:
        value = self.mouse_button_value(button)
        if pressed:
            self.pressed_mouse_buttons.add(value)
        else:
            self.pressed_mouse_buttons.discard(value)
        if self.hotkey_capture_active:
            return
        self.update_shortcut_actions()

    def on_global_key_press(self, key) -> None:
        value = self.keyboard_key_value(key)
        self.pressed_keys.add(value)
        modifier = self.modifier_name_for_key(key)
        if modifier:
            self.pressed_modifiers.add(modifier)
        if self.hotkey_capture_active:
            return
        self.update_shortcut_actions()

    def on_global_key_release(self, key) -> None:
        value = self.keyboard_key_value(key)
        self.pressed_keys.discard(value)
        modifier = self.modifier_name_for_key(key)
        if modifier:
            self.pressed_modifiers.discard(modifier)
        if self.hotkey_capture_active:
            return
        self.update_shortcut_actions()

    def handle_hotkey_press(self) -> None:
        if self.recording_mode == "desktop":
            return
        if self.hotkey_down:
            return
        self.hotkey_down = True
        self.apply_edge_dock()
        self.apply_window_opacity()
        if self.pending_record_start_id:
            self.root.after_cancel(self.pending_record_start_id)
            self.pending_record_start_id = None
        delay_ms = int(self.desktop_config.get("record_start_delay_ms", 120) or 0)
        if delay_ms <= 0:
            self.start_recording_if_held()
        else:
            self.pending_record_start_id = self.root.after(delay_ms, self.start_recording_if_held)

    def handle_hotkey_release(self) -> None:
        self.hotkey_down = False
        if self.pending_record_start_id:
            self.root.after_cancel(self.pending_record_start_id)
            self.pending_record_start_id = None
            self.log_diagnostic("recording_tap_ignored", reason="released_before_start_delay")
            self.apply_edge_dock()
            self.apply_window_opacity()
            return
        if self.recording_mode == "mic" and (self.state == "recording" or self.recorder.recording):
            self.stop_recording()

    def start_recording_if_held(self) -> None:
        self.pending_record_start_id = None
        if not self.hotkey_down:
            self.log_diagnostic("recording_tap_ignored", reason="not_held_at_start_delay")
            return
        self.start_recording()

    def hotkey_label(self) -> str:
        return self.shortcut_label("record_mic")

    def ai_model_label(self) -> str:
        if self.ai_config.get("provider", "gemini") == "gateway":
            return self.ai_config.get("gateway_model") or "未配置模型"
        return self.ai_config.get("model") or "Gemini"

    def status_lines(self) -> list[str]:
        if self.bubble_expanded and self.bubble_visible():
            return []
        visibility = self.desktop_config.get("status_visibility", "always")
        if visibility == "never":
            return []
        if visibility == "hover" and not self.hovering:
            return []

        parts_config = self.desktop_config.get("status_parts", {})
        if not isinstance(parts_config, dict):
            parts_config = DEFAULT_DESKTOP_CONFIG["status_parts"]

        lines = []
        orb_name = str(self.desktop_config.get("orb_name") or "").strip()
        if parts_config.get("orb_name", True) and orb_name:
            lines.append(orb_name)

        if parts_config.get("model", True):
            lines.append(self.ai_model_label())

        return [line for line in lines if line]

    def status_text(self) -> str:
        return "\n".join(self.status_lines())

    def hint_bubble_visible(self) -> bool:
        if self.bubble_expanded and self.bubble_visible():
            return False
        if self.bubble_visible():
            return False
        if self.edge_docked:
            return False
        if (
            self.idle_edge_dock_enabled()
            and self.state == "idle"
            and not self.hovering
            and self.dockable_edge() is not None
        ):
            return False
        parts_config = self.desktop_config.get("status_parts", {})
        if not isinstance(parts_config, dict):
            parts_config = DEFAULT_DESKTOP_CONFIG["status_parts"]
        if not parts_config.get("action_hint", True):
            return False
        text = self.action_hint_text()
        if not text:
            return False
        if self.closed_hint_text == text:
            return False
        return True

    def action_hint_text(self) -> str:
        if self.state == "idle":
            return f"长按{self.hotkey_label()}说话 / {self.shortcut_label('desktop_audio')} 桌面音频"
        if self.state == "recording":
            cancel_label = self.shortcut_label("cancel_recording")
            if self.recording_mode == "desktop":
                return f"桌面音频录制中，松开{self.shortcut_label('desktop_audio')}发送，按{cancel_label}取消"
            screenshot_label = self.shortcut_label("screenshot")
            if self.pending_image_paths:
                return (
                    f"已附加截图 {len(self.pending_image_paths)} 张，"
                    f"松开{self.hotkey_label()}发送，按{screenshot_label}继续截图，按{cancel_label}取消"
                )
            return f"录音中，松开{self.hotkey_label()}发送，按{screenshot_label}截图，按{cancel_label}取消"
        if self.state == "connecting":
            return self.status
        return self.status

    def start_recording(self) -> None:
        if self.processing.is_set():
            return
        if self.state == "recording":
            return
        try:
            if self.recorder.start():
                self.recording_mode = "mic"
                self.pending_image_paths = []
                self.alt_screenshot_down = False
                self.state = "recording"
                self.status = self.action_hint_text()
                self.user_text = ""
                self.full_reply = ""
                self.visible_reply = ""
                self.bubble_hidden = False
                self.bubble_expanded = False
                self.bubble_scroll = 0
                self.render()
        except Exception as exc:
            self.show_error(f"麦克风启动失败：{exc}")

    def stop_recording(self) -> None:
        if self.recording_mode == "desktop":
            self.stop_desktop_audio_recording()
            return
        audio_path = self.recorder.stop()
        image_paths = list(self.pending_image_paths)
        self.pending_image_paths = []
        self.alt_screenshot_down = False
        self.recording_mode = None
        if not audio_path:
            if self.state == "recording":
                self.set_idle("录音太短，已忽略")
            return
        self.state = "connecting"
        self.status = "连接中，AI 正在理解音频"
        self.render()
        threading.Thread(
            target=self.process_audio,
            args=(audio_path, image_paths, "microphone"),
            daemon=True,
        ).start()

    def discard_path(self, path: Path | None) -> None:
        if not path:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def cancel_recording(self) -> None:
        if self.pending_record_start_id:
            try:
                self.root.after_cancel(self.pending_record_start_id)
            except tk.TclError:
                pass
            self.pending_record_start_id = None

        audio_path = None
        try:
            if self.recording_mode == "desktop" or self.desktop_recorder.recording:
                audio_path = self.desktop_recorder.stop()
            elif self.recording_mode == "mic" or self.recorder.recording:
                audio_path = self.recorder.stop()
        except Exception as exc:
            self.log_diagnostic("recording_cancel_stop_failed", error=str(exc), mode=self.recording_mode)

        self.discard_path(audio_path)
        for image_path in self.pending_image_paths:
            self.discard_path(image_path)

        self.pending_image_paths = []
        self.alt_screenshot_down = False
        self.desktop_audio_key_down = False
        self.recording_mode = None
        self.state = "idle"
        self.status = "录音已取消"
        self.user_text = ""
        self.full_reply = ""
        self.visible_reply = ""
        self.bubble_hidden = True
        self.bubble_expanded = False
        self.bubble_scroll = 0
        self.log_diagnostic("recording_cancelled")
        self.render()

    def capture_screenshot_attachment(self) -> None:
        if self.state != "recording" or self.recording_mode != "mic":
            return
        if ImageGrab is None:
            self.status = "截图失败：Pillow ImageGrab 不可用"
            self.render()
            return
        try:
            TMP_DIR.mkdir(parents=True, exist_ok=True)
            try:
                image = ImageGrab.grab(all_screens=True)
            except TypeError:
                image = ImageGrab.grab()
            path = TMP_DIR / f"desktop-shot-{int(time.time() * 1000)}.png"
            image.save(path)
            self.pending_image_paths.append(path)
            self.status = self.action_hint_text()
            self.log_diagnostic("screenshot_attached", image_path=str(path))
            self.render()
        except Exception as exc:
            self.log_diagnostic("screenshot_failed", error=str(exc))
            self.status = f"截图失败：{exc}"
            self.render()

    def handle_desktop_audio_press(self) -> None:
        if self.recording_mode == "desktop":
            return
        if self.hotkey_down or self.pending_record_start_id:
            return
        self.start_desktop_audio_recording()

    def handle_desktop_audio_release(self) -> None:
        if self.recording_mode == "desktop":
            self.stop_desktop_audio_recording()

    def start_desktop_audio_recording(self) -> None:
        if self.processing.is_set():
            return
        if self.state == "recording":
            return
        try:
            if self.desktop_recorder.start():
                self.recording_mode = "desktop"
                self.pending_image_paths = []
                self.alt_screenshot_down = False
                self.state = "recording"
                self.status = self.action_hint_text()
                self.user_text = ""
                self.full_reply = ""
                self.visible_reply = ""
                self.bubble_hidden = False
                self.bubble_expanded = False
                self.bubble_scroll = 0
                self.render()
        except Exception as exc:
            self.show_error(f"桌面音频启动失败：{exc}")

    def stop_desktop_audio_recording(self) -> None:
        try:
            audio_path = self.desktop_recorder.stop()
        except Exception as exc:
            self.recording_mode = None
            self.desktop_audio_key_down = False
            self.show_error(str(exc))
            return
        self.recording_mode = None
        self.desktop_audio_key_down = False
        if not audio_path:
            if self.state == "recording":
                self.set_idle("桌面音频太短，已忽略")
            return
        self.state = "connecting"
        self.status = "连接中，AI 正在理解桌面音频"
        self.render()
        threading.Thread(
            target=self.process_audio,
            args=(audio_path, [], "desktop"),
            daemon=True,
        ).start()

    def process_audio(self, audio_path: Path, image_paths: list[Path] | None = None, audio_source: str = "microphone") -> None:
        if self.processing.is_set():
            return
        self.processing.set()
        image_paths = image_paths or []
        stats = {}
        try:
            stats = audio_stats(audio_path)
            self.log_diagnostic(
                "audio_recorded",
                audio=stats,
                audio_source=audio_source,
                image_paths=[str(path) for path in image_paths],
            )
            min_duration = float(self.desktop_config.get("ignore_short_recordings_ms", 350) or 0)
            if stats["duration_ms"] < min_duration:
                self.log_diagnostic("audio_ignored", reason="too_short", audio=stats)
                self.root.after(0, lambda: self.set_idle(f"录音太短，已忽略"))
                return

            turn_args = [
                "--audio",
                str(audio_path),
                "--audio-source",
                audio_source,
                "--tts-output-format",
                self.desktop_config.get("tts_output_format", "pcm_24000"),
                "--json",
            ]
            for image_path in image_paths:
                turn_args.extend(["--image", str(image_path)])
            payload = self.run_voice_turn(turn_args)
            self.log_diagnostic(
                "ai_reply",
                audio=stats,
                audio_source=audio_source,
                image_paths=[str(path) for path in image_paths],
                brain=payload.get("brain"),
                model=payload.get("model"),
                user_text=payload.get("user_text"),
                assistant_chars=len(payload.get("assistant_text") or ""),
                tts_audio_path=payload.get("audio_path"),
            )
            self.root.after(0, lambda: self.show_reply(payload))
        except Exception as exc:
            self.log_diagnostic("error", audio=stats, error=str(exc))
            self.root.after(0, lambda: self.show_error(str(exc)))
        finally:
            self.processing.clear()

    def new_session(self) -> None:
        if self.processing.is_set():
            return
        self.state = "connecting"
        self.status = "正在开启新会话"
        self.user_text = ""
        self.visible_reply = ""
        self.bubble_hidden = False
        self.bubble_expanded = False
        self.bubble_scroll = 0
        self.render()
        threading.Thread(target=self._new_session_worker, daemon=True).start()

    def _new_session_worker(self) -> None:
        try:
            self.run_voice_turn(["--new-session", "--json"])
            self.root.after(0, lambda: self.set_idle("新会话已开启"))
        except Exception as exc:
            self.root.after(0, lambda: self.show_error(str(exc)))

    def run_voice_turn(self, args: list[str]) -> dict:
        try:
            return run_turn(args)
        except SystemExit as exc:
            message = str(exc.code) if exc.code else "voice turn stopped"
            raise RuntimeError(message) from exc

    def log_diagnostic(self, event: str, **data) -> None:
        if not self.desktop_config.get("diagnostics_enabled", True):
            return
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            payload = {"ts": utc_now(), "event": event, **data}
            with (LOG_DIR / "voice-turns.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def show_context_menu(self, event) -> None:
        self.context_menu.delete(0, "end")
        self.context_menu.add_command(label="设置", command=self.open_settings)
        self.context_menu.add_separator()
        if self.processing.is_set():
            self.context_menu.add_command(label="处理中，稍等", state="disabled")
        else:
            self.context_menu.add_command(label="开启新会话", command=self.new_session)
        self.context_menu.add_separator()
        if self.bubble_visible():
            self.context_menu.add_command(label="关闭对话框", command=self.close_dialogue)
        else:
            self.context_menu.add_command(label="关闭对话框", state="disabled")
        self.context_menu.add_separator()
        self.context_menu.add_command(label="关闭悬浮球", command=self.close)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def reload_runtime_config(self) -> None:
        self.desktop_config = load_json_file(DESKTOP_CONFIG_PATH, DEFAULT_DESKTOP_CONFIG)
        self.ai_config = load_json_file(AI_CONFIG_PATH, {})
        self.tts_config = load_json_file(TTS_CONFIG_PATH, {})
        self.skins = load_skins()
        self.skin = self.active_skin()

    def provider_option(self, ai_config: dict) -> str:
        if ai_config.get("provider", "gemini") == "gateway":
            fmt = ai_config.get("gateway_format", "gemini")
            if fmt == "openai":
                return "Gateway · OpenAI 格式"
            return "Gateway · Gemini 格式"
        if ai_config.get("provider") == "gemini":
            return "Gateway · Gemini 格式"
        return "Gateway · Gemini 格式"

    def open_settings(self) -> None:
        if getattr(self, "settings_window", None) and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        ai_config = load_json_file(AI_CONFIG_PATH, {})
        tts_config = load_json_file(TTS_CONFIG_PATH, {})
        desktop_config = load_json_file(DESKTOP_CONFIG_PATH, DEFAULT_DESKTOP_CONFIG)
        skins = load_skins()

        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title("幽浮 设置")
        win.geometry("560x750")
        win.configure(bg="#fffaf0")
        win.attributes("-topmost", True)

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=14, pady=14)

        ai_frame = ttk.Frame(notebook, padding=12)
        tts_frame = ttk.Frame(notebook, padding=12)
        shortcut_frame = ttk.Frame(notebook, padding=12)
        orb_frame = ttk.Frame(notebook, padding=12)
        notebook.add(ai_frame, text="AI")
        notebook.add(tts_frame, text="ElevenLabs")
        notebook.add(shortcut_frame, text="快捷键")
        notebook.add(orb_frame, text="悬浮球")

        provider_var = tk.StringVar(value=self.provider_option(ai_config))
        gateway_base_var = tk.StringVar(value=ai_config.get("gateway_base_url") or ai_config.get("base_url", ""))
        gateway_key_var = tk.StringVar(value=ai_config.get("gateway_api_key") or ai_config.get("api_key", ""))
        gateway_model_var = tk.StringVar(value=ai_config.get("gateway_model") or ai_config.get("model", ""))
        gateway_auth_var = tk.StringVar(value=ai_config.get("gateway_auth_header", "auto"))

        eleven_key_var = tk.StringVar(value=tts_config.get("api_key", ""))
        voice_id_var = tk.StringVar(value=tts_config.get("voice_id", ""))
        eleven_model_var = tk.StringVar(value=tts_config.get("model_id", "eleven_v3"))

        visibility_options = {
            "始终显示": "always",
            "悬停显示": "hover",
            "隐藏": "never",
        }
        visibility_labels = {value: label for label, value in visibility_options.items()}
        status_parts = desktop_config.get("status_parts", DEFAULT_DESKTOP_CONFIG["status_parts"])
        if not isinstance(status_parts, dict):
            status_parts = DEFAULT_DESKTOP_CONFIG["status_parts"]

        orb_name_var = tk.StringVar(value=desktop_config.get("orb_name", "幽浮"))
        status_visibility_var = tk.StringVar(
            value=visibility_labels.get(desktop_config.get("status_visibility", "always"), "始终显示")
        )
        show_orb_name_var = tk.BooleanVar(value=bool(status_parts.get("orb_name", True)))
        show_model_var = tk.BooleanVar(value=bool(status_parts.get("model", True)))
        show_action_var = tk.BooleanVar(value=bool(status_parts.get("action_hint", True)))
        diagnostics_var = tk.BooleanVar(value=bool(desktop_config.get("diagnostics_enabled", True)))
        short_recording_var = tk.StringVar(value=str(desktop_config.get("ignore_short_recordings_ms", 350)))
        startup_var = tk.BooleanVar(value=is_startup_enabled())
        tts_format_var = tk.StringVar(value=desktop_config.get("tts_output_format", "pcm_24000"))
        bubble_enabled_var = tk.BooleanVar(value=bool(desktop_config.get("bubble_enabled", True)))
        record_start_delay_var = tk.StringVar(value=str(desktop_config.get("record_start_delay_ms", 120)))
        skin_options = {
            f"{skin.get('name', skin_id)} [{skin_id}]": skin_id
            for skin_id, skin in sorted(skins.items(), key=lambda item: item[1].get("name", item[0]))
        }
        current_skin_id = str(desktop_config.get("skin") or "default")
        current_skin_label = next(
            (label for label, skin_id in skin_options.items() if skin_id == current_skin_id),
            next(iter(skin_options), "纸片奶油 [default]"),
        )
        skin_var = tk.StringVar(value=current_skin_label)
        shortcut_states = {}
        for action, title, description in SHORTCUT_ACTIONS:
            binding = self.shortcut_binding(action, desktop_config)
            shortcut_states[action] = {
                "title": title,
                "description": description,
                "binding": binding,
                "label_var": tk.StringVar(value=self.shortcut_binding_label(binding)),
                "button_var": tk.StringVar(value="录制"),
                "hint_var": tk.StringVar(value=description),
                "combo_var": tk.BooleanVar(value=bool(binding.get("modifiers"))),
            }
        capture_listeners = {"mouse": None, "keyboard": None}

        def clamp_orb_size(value) -> int:
            try:
                size = int(round(float(value)))
            except (TypeError, ValueError):
                size = 160
            return max(96, min(240, size))

        def opacity_percent(value) -> int:
            try:
                opacity = float(value)
            except (TypeError, ValueError):
                opacity = 0.6
            if opacity <= 1:
                opacity *= 100
            return max(0, min(100, int(round(opacity))))

        original_runtime_orb_size = clamp_orb_size(self.desktop_config.get("orb_size", desktop_config.get("orb_size", 160)))
        orb_size_initial = clamp_orb_size(desktop_config.get("orb_size", original_runtime_orb_size))
        orb_size_var = tk.DoubleVar(value=orb_size_initial)
        orb_size_label_var = tk.StringVar(value=f"{orb_size_initial} px")
        original_idle_transparency_enabled = bool(
            self.desktop_config.get(
                "idle_transparency_enabled",
                desktop_config.get("idle_transparency_enabled", False),
            )
        )
        original_idle_opacity_percent = opacity_percent(
            self.desktop_config.get("idle_opacity", desktop_config.get("idle_opacity", 0.6))
        )
        idle_transparency_var = tk.BooleanVar(
            value=bool(desktop_config.get("idle_transparency_enabled", original_idle_transparency_enabled))
        )
        idle_opacity_initial = opacity_percent(desktop_config.get("idle_opacity", original_idle_opacity_percent / 100))
        idle_opacity_var = tk.DoubleVar(value=idle_opacity_initial)
        idle_opacity_label_var = tk.StringVar(value=f"{idle_opacity_initial}%")
        original_idle_edge_dock_enabled = bool(
            self.desktop_config.get(
                "idle_edge_dock_enabled",
                desktop_config.get("idle_edge_dock_enabled", False),
            )
        )
        idle_edge_dock_var = tk.BooleanVar(
            value=bool(desktop_config.get("idle_edge_dock_enabled", original_idle_edge_dock_enabled))
        )
        settings_saved = {"value": False}

        def preview_orb_size(value=None) -> None:
            size = clamp_orb_size(value if value is not None else orb_size_var.get())
            orb_size_label_var.set(f"{size} px")
            self.desktop_config["orb_size"] = size
            self.skin_images = {}
            self.render()

        def preview_idle_opacity(value=None) -> None:
            percent = opacity_percent(value if value is not None else idle_opacity_var.get())
            idle_opacity_label_var.set(f"{percent}%")
            self.desktop_config["idle_transparency_enabled"] = bool(idle_transparency_var.get())
            self.desktop_config["idle_opacity"] = percent / 100
            self.apply_window_opacity()

        def preview_edge_dock() -> None:
            self.desktop_config["idle_edge_dock_enabled"] = bool(idle_edge_dock_var.get())
            self.render()

        capture_state = {"action": None, "modifiers": set()}

        def refresh_shortcut_label(action: str) -> None:
            state = shortcut_states[action]
            binding = dict(state["binding"])
            if not state["combo_var"].get():
                binding["modifiers"] = []
                state["binding"] = binding
            state["label_var"].set(self.shortcut_binding_label(binding))

        def stop_shortcut_capture() -> None:
            active_action = capture_state.get("action")
            self.hotkey_capture_active = False
            for key in ("mouse", "keyboard"):
                listener = capture_listeners.get(key)
                if listener:
                    listener.stop()
                    capture_listeners[key] = None
            if active_action in shortcut_states:
                shortcut_states[active_action]["button_var"].set("重新录制")
            capture_state["action"] = None
            capture_state["modifiers"] = set()

        def apply_captured_shortcut(action: str, binding: dict) -> None:
            stop_shortcut_capture()
            shortcut_states[action]["binding"] = binding
            shortcut_states[action]["label_var"].set(self.shortcut_binding_label(binding))
            shortcut_states[action]["hint_var"].set("已记录。保存设置后生效。")

        def begin_shortcut_capture(action: str) -> None:
            stop_shortcut_capture()
            self.hotkey_capture_active = True
            state = shortcut_states[action]
            capture_state["action"] = action
            capture_state["modifiers"] = set()
            state["label_var"].set("等待输入...")
            state["hint_var"].set(
                "先按住修饰键再按主键；也可以直接点击鼠标键。"
                if state["combo_var"].get()
                else "现在按键盘键，或点击一个鼠标按键。"
            )
            state["button_var"].set("录制中")

            def capture_mouse(x, y, button, pressed):
                if pressed:
                    modifiers = capture_state["modifiers"] if state["combo_var"].get() else []
                    binding = self.mouse_hotkey_binding(button, modifiers)
                    self.root.after(0, lambda: apply_captured_shortcut(action, binding))
                    return False
                return None

            def capture_key_press(key):
                modifier = self.modifier_name_for_key(key)
                if state["combo_var"].get() and modifier:
                    capture_state["modifiers"].add(modifier)
                    state["hint_var"].set(
                        f"已按住 {'+'.join(MODIFIER_LABELS.get(item, item.title()) for item in self.sorted_modifiers(capture_state['modifiers']))}，继续按主键。"
                    )
                    return None
                modifiers = capture_state["modifiers"] if state["combo_var"].get() else []
                binding = self.keyboard_hotkey_binding(key, modifiers)
                self.root.after(0, lambda: apply_captured_shortcut(action, binding))
                return False

            def capture_key_release(key):
                modifier = self.modifier_name_for_key(key)
                if modifier:
                    capture_state["modifiers"].discard(modifier)
                return None

            def start_capture_listeners() -> None:
                if not self.hotkey_capture_active or not win.winfo_exists():
                    return
                capture_listeners["mouse"] = mouse.Listener(on_click=capture_mouse)
                capture_listeners["keyboard"] = keyboard.Listener(
                    on_press=capture_key_press,
                    on_release=capture_key_release,
                )
                capture_listeners["mouse"].start()
                capture_listeners["keyboard"].start()

            win.after(180, start_capture_listeners)

        def close_settings() -> None:
            stop_shortcut_capture()
            if not settings_saved["value"]:
                self.desktop_config["orb_size"] = original_runtime_orb_size
                self.desktop_config["idle_transparency_enabled"] = original_idle_transparency_enabled
                self.desktop_config["idle_opacity"] = original_idle_opacity_percent / 100
                self.desktop_config["idle_edge_dock_enabled"] = original_idle_edge_dock_enabled
                self.skin_images = {}
                self.render()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close_settings)

        def add_entry(parent, row: int, label: str, variable: tk.StringVar, width: int = 46) -> None:
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=1, sticky="ew", pady=5)
            parent.columnconfigure(1, weight=1)

        ttk.Label(ai_frame, text="AI 提供方").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(
            ai_frame,
            textvariable=provider_var,
            values=["Gateway · Gemini 格式", "Gateway · OpenAI 格式"],
            state="readonly",
            width=43,
        ).grid(row=0, column=1, sticky="ew", pady=5)
        add_entry(ai_frame, 1, "Gateway Base URL", gateway_base_var)
        add_entry(ai_frame, 2, "Gateway API Key", gateway_key_var)
        add_entry(ai_frame, 3, "Gateway Model", gateway_model_var)
        ttk.Label(ai_frame, text="Gateway Auth Header").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Combobox(
            ai_frame,
            textvariable=gateway_auth_var,
            values=["auto", "bearer", "x-goog-api-key", "x-api-key"],
            state="readonly",
            width=43,
        ).grid(row=4, column=1, sticky="ew", pady=5)

        add_entry(tts_frame, 0, "ElevenLabs API Key", eleven_key_var)
        add_entry(tts_frame, 1, "Voice ID", voice_id_var)
        add_entry(tts_frame, 2, "ElevenLabs Model", eleven_model_var)

        ttk.Label(
            shortcut_frame,
            text="勾选“使用组合键”后，录制时可先按住 Ctrl / Alt / Shift / Win，再按主键或鼠标键。",
            foreground="#6b6558",
            wraplength=500,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))
        for row, (action, title, _description) in enumerate(SHORTCUT_ACTIONS, start=1):
            state = shortcut_states[action]
            ttk.Label(shortcut_frame, text=title).grid(row=row, column=0, sticky="nw", pady=8)
            shortcut_control = ttk.Frame(shortcut_frame)
            shortcut_control.grid(row=row, column=1, sticky="ew", pady=6)
            shortcut_control.columnconfigure(0, weight=1)
            ttk.Label(shortcut_control, textvariable=state["label_var"]).grid(row=0, column=0, sticky="ew")
            ttk.Button(
                shortcut_control,
                textvariable=state["button_var"],
                command=lambda action=action: begin_shortcut_capture(action),
            ).grid(row=0, column=1, padx=(8, 0), sticky="e")
            ttk.Checkbutton(
                shortcut_frame,
                text="使用组合键",
                variable=state["combo_var"],
                command=lambda action=action: refresh_shortcut_label(action),
            ).grid(row=row, column=2, sticky="nw", padx=(12, 0), pady=8)
            ttk.Label(
                shortcut_frame,
                textvariable=state["hint_var"],
                foreground="#6b6558",
                wraplength=170,
                justify="left",
            ).grid(row=row, column=3, sticky="nw", padx=(12, 0), pady=8)
        shortcut_frame.columnconfigure(1, weight=1)

        add_entry(orb_frame, 0, "悬浮球名称", orb_name_var)
        ttk.Label(orb_frame, text="皮肤").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            orb_frame,
            textvariable=skin_var,
            values=list(skin_options.keys()),
            state="readonly",
            width=43,
        ).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(orb_frame, text="悬浮球大小").grid(row=2, column=0, sticky="w", pady=5)
        orb_size_frame = ttk.Frame(orb_frame)
        orb_size_frame.grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Scale(
            orb_size_frame,
            from_=96,
            to=240,
            variable=orb_size_var,
            command=preview_orb_size,
            orient="horizontal",
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(orb_size_frame, textvariable=orb_size_label_var, width=7).pack(side="right", padx=(10, 0))

        ttk.Checkbutton(
            orb_frame,
            text="静默时半透明",
            variable=idle_transparency_var,
            command=preview_idle_opacity,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Label(orb_frame, text="静默不透明度").grid(row=4, column=0, sticky="w", pady=5)
        idle_opacity_frame = ttk.Frame(orb_frame)
        idle_opacity_frame.grid(row=4, column=1, sticky="ew", pady=5)
        ttk.Scale(
            idle_opacity_frame,
            from_=0,
            to=100,
            variable=idle_opacity_var,
            command=preview_idle_opacity,
            orient="horizontal",
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(idle_opacity_frame, textvariable=idle_opacity_label_var, width=7).pack(side="right", padx=(10, 0))

        ttk.Checkbutton(
            orb_frame,
            text="静默时吸附左右边缘",
            variable=idle_edge_dock_var,
            command=preview_edge_dock,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)

        add_entry(orb_frame, 6, "桌面 TTS 输出格式", tts_format_var)

        ttk.Checkbutton(orb_frame, text="启用回复对话框", variable=bubble_enabled_var).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=5
        )

        ttk.Label(orb_frame, text="下方文字显示").grid(row=8, column=0, sticky="w", pady=5)
        ttk.Combobox(
            orb_frame,
            textvariable=status_visibility_var,
            values=list(visibility_options.keys()),
            state="readonly",
            width=43,
        ).grid(row=8, column=1, sticky="ew", pady=5)

        ttk.Label(orb_frame, text="下方文字内容").grid(row=9, column=0, sticky="nw", pady=6)
        parts_frame = ttk.Frame(orb_frame)
        parts_frame.grid(row=9, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(parts_frame, text="悬浮球名称", variable=show_orb_name_var).pack(anchor="w")
        ttk.Checkbutton(parts_frame, text="模型名称", variable=show_model_var).pack(anchor="w")

        ttk.Checkbutton(orb_frame, text="显示操作提示气泡", variable=show_action_var).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=5
        )
        ttk.Checkbutton(orb_frame, text="开机启动悬浮球", variable=startup_var).grid(
            row=11, column=0, columnspan=2, sticky="w", pady=5
        )
        ttk.Checkbutton(orb_frame, text="记录诊断日志", variable=diagnostics_var).grid(
            row=12, column=0, columnspan=2, sticky="w", pady=5
        )
        add_entry(orb_frame, 13, "忽略短录音(ms)", short_recording_var)
        add_entry(orb_frame, 14, "启动录音延迟(ms)", record_start_delay_var)
        orb_frame.columnconfigure(1, weight=1)

        button_bar = ttk.Frame(win, padding=(14, 0, 14, 14))
        button_bar.pack(fill="x")

        def save_settings() -> None:
            provider = provider_var.get()
            ai_config["provider"] = "gateway"
            if "OpenAI" in provider:
                ai_config["gateway_format"] = "openai"
            else:
                ai_config["gateway_format"] = "gemini"

            ai_config["gateway_base_url"] = gateway_base_var.get().strip()
            ai_config["gateway_api_key"] = gateway_key_var.get().strip()
            ai_config["gateway_model"] = gateway_model_var.get().strip()
            ai_config["gateway_auth_header"] = gateway_auth_var.get().strip() or "auto"
            if ai_config["gateway_format"] == "gemini":
                ai_config["base_url"] = ai_config["gateway_base_url"]
                ai_config["api_key"] = ai_config["gateway_api_key"]
                ai_config["model"] = ai_config["gateway_model"]

            tts_config["api_key"] = eleven_key_var.get().strip()
            tts_config["voice_id"] = voice_id_var.get().strip()
            tts_config["model_id"] = eleven_model_var.get().strip() or "eleven_v3"

            shortcuts_config = {}
            for action, _title, _description in SHORTCUT_ACTIONS:
                binding = dict(shortcut_states[action]["binding"])
                if not shortcut_states[action]["combo_var"].get():
                    binding["modifiers"] = []
                binding = self.normalize_shortcut_binding(
                    binding,
                    DEFAULT_DESKTOP_CONFIG["shortcuts"].get(action, DEFAULT_DESKTOP_CONFIG["shortcuts"]["record_mic"]),
                )
                shortcuts_config[action] = binding
            desktop_config["shortcuts"] = shortcuts_config
            desktop_config["hotkey"] = shortcuts_config["record_mic"]
            if shortcuts_config["record_mic"].get("type") == "mouse":
                desktop_config["button"] = shortcuts_config["record_mic"].get("value", "x2")
            desktop_config["orb_name"] = orb_name_var.get().strip() or "幽浮"
            desktop_config["skin"] = skin_options.get(skin_var.get(), "default")
            desktop_config["orb_size"] = clamp_orb_size(orb_size_var.get())
            desktop_config["idle_transparency_enabled"] = bool(idle_transparency_var.get())
            desktop_config["idle_opacity"] = opacity_percent(idle_opacity_var.get()) / 100
            desktop_config["idle_edge_dock_enabled"] = bool(idle_edge_dock_var.get())
            desktop_config["status_visibility"] = visibility_options.get(status_visibility_var.get(), "always")
            desktop_config["status_parts"] = {
                "orb_name": bool(show_orb_name_var.get()),
                "model": bool(show_model_var.get()),
                "action_hint": bool(show_action_var.get()),
            }
            desktop_config["show_status_text"] = desktop_config["status_visibility"] != "never"
            desktop_config["diagnostics_enabled"] = bool(diagnostics_var.get())
            try:
                desktop_config["ignore_short_recordings_ms"] = max(0, int(float(short_recording_var.get().strip())))
            except ValueError:
                messagebox.showerror("保存失败", "忽略短录音(ms) 必须是数字。", parent=win)
                return
            try:
                desktop_config["record_start_delay_ms"] = max(0, int(float(record_start_delay_var.get().strip())))
            except ValueError:
                messagebox.showerror("保存失败", "启动录音延迟(ms) 必须是数字。", parent=win)
                return
            desktop_config["startup_enabled"] = bool(startup_var.get())
            desktop_config["tts_output_format"] = tts_format_var.get().strip() or "pcm_24000"
            desktop_config["bubble_enabled"] = bool(bubble_enabled_var.get())

            try:
                set_startup_enabled(bool(startup_var.get()))
                save_json_file(AI_CONFIG_PATH, ai_config)
                save_json_file(TTS_CONFIG_PATH, tts_config)
                save_json_file(DESKTOP_CONFIG_PATH, desktop_config)
            except Exception as exc:
                messagebox.showerror("保存失败", str(exc), parent=win)
                return

            self.reload_runtime_config()
            if bool(show_action_var.get()):
                self.closed_hint_text = None
            self.state = "idle"
            self.status = "设置已保存"
            self.render()
            settings_saved["value"] = True
            win.destroy()

        ttk.Button(button_bar, text="取消", command=close_settings).pack(side="right", padx=(8, 0))
        ttk.Button(button_bar, text="保存", command=save_settings).pack(side="right")

    def show_reply(self, payload: dict) -> None:
        self.state = "speaking"
        self.status = "输出中"
        self.user_text = payload.get("user_text", "")
        self.full_reply = payload.get("assistant_text", "")
        self.visible_reply = ""
        self.bubble_hidden = False
        self.bubble_scroll = 0
        self.render()

        audio_path = payload.get("audio_path")
        if audio_path:
            threading.Thread(target=self.play_then_idle, args=(Path(audio_path),), daemon=True).start()
        self.type_next(0)

    def play_then_idle(self, audio_path: Path) -> None:
        try:
            self.player.play_wait(audio_path)
        except Exception as exc:
            self.root.after(0, lambda: self.show_error(f"播放失败：{exc}"))
            return
        self.root.after(1400, lambda: self.set_idle("待机，长按侧键二说话"))

    def type_next(self, index: int) -> None:
        if self.state != "speaking":
            return
        self.visible_reply = self.full_reply[:index]
        self.render()
        if index < len(self.full_reply):
            self.root.after(self.args.type_ms, lambda: self.type_next(index + 1))

    def set_idle(self, status: str) -> None:
        self.state = "idle"
        self.recording_mode = None
        self.status = status
        self.render()

    def show_error(self, message: str) -> None:
        self.state = "error"
        self.recording_mode = None
        self.status = "出错了"
        self.visible_reply = message[:160]
        self.bubble_hidden = False
        self.bubble_scroll = 0
        self.render()
        self.root.after(3600, lambda: self.set_idle("待机，长按侧键二说话"))

    def render(self) -> None:
        resizing = self.sync_window_size()
        c = self.canvas
        c.delete("all")
        self.bubble_toggle_bounds = None
        self.hint_close_bounds = None
        self.draw_orb()
        self.draw_speech_bubble()
        self.draw_hint_bubble()
        status = self.status_text()
        if status:
            status_font = ("Microsoft YaHei UI", self.status_font_size(), "bold")
            status_x, status_y, status_width = self.status_position()
            status = self.fit_text_to_box(status, status_font, status_width, self.status_area_height())
            c.create_text(
                status_x + 1,
                status_y + 1,
                text=status,
                fill=self.skin_color("status_shadow"),
                font=status_font,
                anchor="center",
                width=status_width,
            )
            c.create_text(
                status_x,
                status_y,
                text=status,
                fill=self.skin_color("status_fill"),
                font=status_font,
                anchor="center",
                width=status_width,
            )
        if resizing:
            try:
                self.root.update_idletasks()
            except tk.TclError:
                pass
        self.apply_edge_dock()
        self.apply_window_geometry()
        self.apply_window_opacity()

    def bubble_visible(self) -> bool:
        if not self.desktop_config.get("bubble_enabled", True):
            return False
        if self.bubble_hidden:
            return False
        return self.state in {"speaking", "error"} or bool(self.visible_reply) or bool(self.full_reply)

    def target_window_dimensions(self) -> tuple[int, int]:
        if self.bubble_visible():
            compact_width, compact_height = self.compact_dimensions()
            width = max(self.args.width, compact_width)
            height = max(BUBBLE_EXPANDED_HEIGHT if self.bubble_expanded else self.args.height, compact_height)
        else:
            width, height = self.compact_dimensions()
        return width, height

    def window_size_will_change(self) -> bool:
        width, height = self.target_window_dimensions()
        return width != self.window_width or height != self.window_height

    def sync_window_size(self) -> bool:
        width, height = self.target_window_dimensions()
        if width == self.window_width and height == self.window_height:
            return False

        self.window_width = width
        self.window_height = height
        self.canvas.configure(width=width, height=height)
        return True

    def apply_window_geometry(self) -> None:
        self.root.geometry(f"{self.window_width}x{self.window_height}+{self.window_x}+{self.window_y}")

    def draw_orb(self) -> None:
        c = self.canvas
        ox, oy = self.orb_center()
        image = self.skin_image_for_state()
        if image:
            offset = self.skin.get("image_offset", {})
            dx = int(offset.get("x", 0)) if isinstance(offset, dict) else 0
            dy = int(offset.get("y", 0)) if isinstance(offset, dict) else 0
            cx, cy = ox + dx, oy + dy
            half_w = image.width() // 2
            half_h = image.height() // 2
            image_background = self.skin.get("image_background")
            if isinstance(image_background, dict) and image_background.get("enabled", True):
                padding = int(image_background.get("padding", 5))
                shadow = image_background.get("shadow", {})
                if isinstance(shadow, dict) and shadow.get("enabled", True):
                    shadow_offset = shadow.get("offset", {})
                    shadow_x = int(shadow_offset.get("x", 3)) if isinstance(shadow_offset, dict) else 3
                    shadow_y = int(shadow_offset.get("y", 5)) if isinstance(shadow_offset, dict) else 5
                    c.create_oval(
                        cx - half_w - padding + shadow_x,
                        cy - half_h - padding + shadow_y,
                        cx + half_w + padding + shadow_x,
                        cy + half_h + padding + shadow_y,
                        fill=str(shadow.get("fill", "#d8c6a4")),
                        outline="",
                    )
                c.create_oval(
                    cx - half_w - padding,
                    cy - half_h - padding,
                    cx + half_w + padding,
                    cy + half_h + padding,
                    fill=str(image_background.get("fill", self.skin_color("paper"))),
                    outline=str(image_background.get("outline", self.skin_color("paper"))),
                    width=int(image_background.get("width", 3)),
                )
            elif self.skin.get("image_shadow", True):
                c.create_oval(
                    cx - half_w + 8,
                    cy - half_h + 10,
                    cx + half_w + 8,
                    cy + half_h + 10,
                    fill=self.skin_color("drop_shadow"),
                    outline="",
                    stipple="gray50",
                )
            c.create_image(cx, cy, image=image, anchor="center")
            return

        accent = self.state_accent()
        ink = self.skin_color("ink")

        c.create_oval(ox - 59, oy - 43, ox + 61, oy + 53, fill=self.skin_color("drop_shadow"), outline="", stipple="gray50")
        c.create_oval(ox - 62, oy - 58, ox + 62, oy + 62, fill=self.skin_color("paper"), outline=self.skin_color("paper"), width=8)
        c.create_oval(ox - 50, oy - 49, ox + 51, oy + 52, fill=self.skin_color("orb_outer"), outline=ink, width=3)
        c.create_oval(ox - 33, oy - 32, ox + 33, oy + 34, fill=self.skin_color("orb_inner"), outline=accent, width=4)
        c.create_oval(ox - 25, oy - 24, ox + 25, oy + 25, fill=self.skin_color("face"), outline="", stipple="gray12")
        self.draw_skin_face_details(ox, oy)
        c.create_line(ox - 13, oy - 3, ox - 13, oy + 14, fill=ink, width=5, capstyle="round")
        c.create_line(ox + 14, oy - 3, ox + 14, oy + 14, fill=ink, width=5, capstyle="round")

        if self.skin_feature("blush") and self.state in {"recording", "speaking"}:
            c.create_oval(ox - 29, oy + 15, ox - 17, oy + 23, fill=self.skin_color("cheek"), outline="")
            c.create_oval(ox + 18, oy + 15, ox + 30, oy + 23, fill=self.skin_color("cheek"), outline="")

        tab_fill = self.skin_color("tab_speaking") if self.state == "speaking" else self.skin_color("tab_idle")
        c.create_polygon(
            ox + 31,
            oy - 52,
            ox + 67,
            oy - 31,
            ox + 49,
            oy - 4,
            ox + 18,
            oy - 27,
            fill=self.skin_color("paper"),
            outline=self.skin_color("paper"),
            width=8,
        )
        c.create_polygon(
            ox + 35,
            oy - 47,
            ox + 61,
            oy - 29,
            ox + 48,
            oy - 10,
            ox + 25,
            oy - 27,
            fill=tab_fill,
            outline=ink,
            width=2,
        )

        if self.state == "recording":
            self.draw_recording_marks(ox, oy, accent)
        elif self.state == "connecting":
            self.draw_connecting_marks(ox, oy)
        elif self.state == "speaking":
            self.draw_sound_marks(ox, oy)
        elif self.state == "idle":
            self.draw_idle_marks(ox, oy)

    def draw_skin_face_details(self, ox: int, oy: int) -> None:
        c = self.canvas
        ink = self.skin_color("ink")
        if self.skin_feature("hair_bob"):
            hair = self.skin_color("hair")
            highlight = self.skin_color("hair_highlight")
            c.create_arc(ox - 31, oy - 36, ox + 32, oy + 28, start=0, extent=180, style="pieslice", fill=hair, outline="")
            c.create_polygon(
                ox - 31,
                oy - 8,
                ox - 18,
                oy - 31,
                ox - 6,
                oy - 11,
                ox + 6,
                oy - 32,
                ox + 15,
                oy - 10,
                ox + 29,
                oy - 30,
                ox + 28,
                oy - 2,
                fill=hair,
                outline="",
            )
            c.create_line(ox - 21, oy - 27, ox - 6, oy - 31, fill=highlight, width=2, capstyle="round")
            c.create_line(ox + 7, oy - 31, ox + 20, oy - 27, fill=highlight, width=2, capstyle="round")

        if self.skin_feature("side_ribbon"):
            ribbon = self.skin_color("ribbon")
            c.create_polygon(ox - 48, oy - 26, ox - 64, oy - 39, ox - 57, oy - 16, fill=ribbon, outline=ink, width=2)
            c.create_polygon(ox - 47, oy - 25, ox - 65, oy - 12, ox - 54, oy - 6, fill=ribbon, outline=ink, width=2)
            c.create_oval(ox - 53, oy - 25, ox - 43, oy - 15, fill=ribbon, outline=ink, width=2)

        if self.skin_feature("dojo_marks"):
            mark = self.skin_color("state_recording")
            c.create_arc(ox - 46, oy + 25, ox - 27, oy + 44, start=20, extent=300, outline=mark, width=3)
            c.create_line(ox - 36, oy + 35, ox - 28, oy + 35, fill=mark, width=2, capstyle="round")

    def draw_idle_marks(self, ox: int, oy: int) -> None:
        c = self.canvas
        for i, y in enumerate([-25, -10, 6]):
            c.create_arc(ox - 79 - i * 3, oy + y, ox - 54 - i * 2, oy + y + 26, start=115, extent=55, outline=self.skin_color("state_idle"), width=4)

    def draw_recording_marks(self, ox: int, oy: int, accent: str) -> None:
        c = self.canvas
        c.create_oval(ox - 75, oy - 73, ox + 75, oy + 75, outline=self.skin_color("recording_halo"), width=13)
        c.create_oval(ox - 86, oy - 84, ox + 86, oy + 86, outline=accent, width=3, dash=(10, 9))
        for side in [-1, 1]:
            x = ox + side * 88
            for h in [21, 36, 54, 36, 21]:
                c.create_line(x, oy - h // 2, x, oy + h // 2, fill=accent, width=5, capstyle="round")
                x += side * 11

    def draw_connecting_marks(self, ox: int, oy: int) -> None:
        c = self.canvas
        c.create_oval(ox - 82, oy - 82, ox + 82, oy + 82, outline=self.skin_color("ink"), width=3, dash=(7, 9))
        nodes = [(ox, oy - 83), (ox - 79, oy + 25), (ox + 79, oy + 25)]
        for x, y in nodes:
            c.create_oval(x - 14, y - 14, x + 14, y + 14, fill=self.skin_color("paper"), outline=self.skin_color("paper"), width=4)
            c.create_oval(x - 8, y - 8, x + 8, y + 8, fill=self.skin_color("connecting_node"), outline=self.skin_color("ink"), width=2)
        for side in [-1, 1]:
            c.create_arc(ox + side * 104 - 30, oy - 42, ox + side * 104 + 30, oy + 42, start=300 if side < 0 else 120, extent=105, outline=self.skin_color("connecting_arc"), width=5)

    def draw_sound_marks(self, ox: int, oy: int) -> None:
        c = self.canvas
        for i in range(3):
            c.create_arc(ox + 54 + i * 12, oy - 28 - i * 4, ox + 100 + i * 13, oy + 31 + i * 4, start=300, extent=120, outline=self.skin_color("state_speaking"), width=4)

    def draw_hint_bubble(self) -> None:
        if not self.hint_bubble_visible():
            return

        c = self.canvas
        x1, y1, x2, y2 = self.hint_bubble_position()
        ox, oy = self.orb_center()
        visual = self.orb_visual_size()
        ink = self.skin_color("ink")
        fill = self.skin_color("bubble")
        back = self.skin_color("bubble_back")
        shadow = self.skin_color("bubble_shadow")

        cloud = [
            (x1 + 26, y2 - 4),
            (x1 + 8, y2 - 22),
            (x1 + 12, y1 + 20),
            (x1 + 34, y1 + 6),
            (x1 + 72, y1 + 2),
            (x1 + 98, y1 + 10),
            (x2 - 40, y1 + 4),
            (x2 - 10, y1 + 24),
            (x2 - 12, y2 - 22),
            (x2 - 40, y2 - 4),
        ]
        shadow_cloud = [(x + 6, y + 7) for x, y in cloud]
        c.create_polygon(shadow_cloud, smooth=True, fill=shadow, outline=shadow)
        c.create_polygon(cloud, smooth=True, fill=back, outline=back, width=6)
        c.create_polygon(cloud, smooth=True, fill=fill, outline=ink, width=2)

        dots = [
            (x1 - 8, y2 - 10, 5),
            (x1 - 23, y2 + 1, 4),
            (ox + visual // 2 - 12, oy - visual // 3, 3),
        ]
        for cx, cy, radius in dots:
            c.create_oval(cx - radius + 3, cy - radius + 4, cx + radius + 3, cy + radius + 4, fill=shadow, outline="")
            c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=fill, outline=ink, width=1)

        close_r = 9
        close_x = x2 - 20
        close_y = y1 + 18
        self.hint_close_bounds = (
            close_x - close_r - 3,
            close_y - close_r - 3,
            close_x + close_r + 3,
            close_y + close_r + 3,
        )
        c.create_oval(
            close_x - close_r,
            close_y - close_r,
            close_x + close_r,
            close_y + close_r,
            fill=self.skin_color("bubble_toggle"),
            outline=ink,
            width=2,
        )
        c.create_text(
            close_x,
            close_y - 1,
            text="x",
            fill=self.skin_color("reply_text"),
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="center",
        )

        font_spec = ("Microsoft YaHei UI", self.hint_font_size(), "bold")
        text = self.fit_text_to_box(self.action_hint_text(), font_spec, x2 - x1 - 54, y2 - y1 - 26)
        c.create_text(
            x1 + 22,
            y1 + 17,
            text=text,
            fill=self.skin_color("reply_text"),
            font=font_spec,
            anchor="nw",
            width=x2 - x1 - 54,
        )

    def wrap_text_to_width(self, text: str, font: tkfont.Font, max_width: int) -> list[str]:
        lines: list[str] = []
        paragraphs = text.splitlines() or [""]
        for paragraph in paragraphs:
            current = ""
            for char in paragraph:
                candidate = current + char
                if current and font.measure(candidate) > max_width:
                    lines.append(current)
                    current = char
                else:
                    current = candidate
            lines.append(current)
        return lines

    def fit_text_to_box(
        self,
        text: str,
        font_spec: tuple,
        max_width: int,
        max_height: int,
        keep_tail: bool = False,
    ) -> str:
        font = tkfont.Font(root=self.root, font=font_spec)
        line_height = max(font.metrics("linespace"), 1)
        max_lines = max(1, max_height // line_height)
        lines = self.wrap_text_to_width(text, font, max_width)
        if len(lines) <= max_lines:
            return "\n".join(lines)

        if keep_tail:
            visible = lines[-max_lines:]
            if visible:
                visible[0] = "…" + visible[0].lstrip("…")
            return "\n".join(visible)

        visible = lines[:max_lines]
        if visible:
            last = visible[-1]
            while last and font.measure(last + "…") > max_width:
                last = last[:-1]
            visible[-1] = f"{last}…"
        return "\n".join(visible)

    def expanded_bubble_lines(self, max_width: int) -> list[dict]:
        lines: list[dict] = []

        def add_text(text: str, font_spec: tuple, fill: str) -> None:
            font = tkfont.Font(root=self.root, font=font_spec)
            line_height = max(font.metrics("linespace"), 16)
            for line in self.wrap_text_to_width(text, font, max_width):
                lines.append({"text": line, "font": font_spec, "fill": fill, "height": line_height})

        if self.user_text:
            add_text("你：" + self.user_text, ("Microsoft YaHei UI", 9), self.skin_color("user_text"))
            lines.append({"text": "", "font": ("Microsoft YaHei UI", 5), "fill": self.skin_color("user_text"), "height": 8})

        text = self.visible_reply or self.full_reply or "……"
        cursor = "▌" if self.state == "speaking" else ""
        add_text(text + cursor, ("Microsoft YaHei UI", 11, "bold"), self.skin_color("reply_text"))
        return lines

    def draw_bubble_toggle(self, x2: int, y1: int) -> None:
        label = "收起" if self.bubble_expanded else "展开"
        tx2 = x2 - 14
        tx1 = tx2 - 48
        ty1 = y1 + 10
        ty2 = ty1 + 24
        self.bubble_toggle_bounds = (tx1, ty1, tx2, ty2)
        self.canvas.create_rectangle(tx1, ty1, tx2, ty2, fill=self.skin_color("bubble_toggle"), outline=self.skin_color("ink"), width=2)
        self.canvas.create_text(
            (tx1 + tx2) // 2,
            (ty1 + ty2) // 2,
            text=label,
            fill=self.skin_color("reply_text"),
            font=("Microsoft YaHei UI", 8, "bold"),
            anchor="center",
        )

    def draw_bubble_scrollbar(self, x: int, y1: int, y2: int) -> None:
        if self.bubble_max_scroll <= 0:
            return
        track_height = max(y2 - y1, 1)
        knob_height = max(26, int(track_height * 0.35))
        travel = max(track_height - knob_height, 1)
        ratio = self.bubble_scroll / max(self.bubble_max_scroll, 1)
        knob_y = y1 + int(travel * ratio)
        self.canvas.create_line(x, y1, x, y2, fill=self.skin_color("scroll_track"), width=4, capstyle="round")
        self.canvas.create_rectangle(
            x - 4,
            knob_y,
            x + 4,
            knob_y + knob_height,
            fill=self.skin_color("scroll_knob"),
            outline=self.skin_color("ink"),
            width=1,
        )

    def draw_speech_bubble(self) -> None:
        if not self.bubble_visible():
            return

        c = self.canvas
        x1, y1 = self.bubble_left_edge(), 30
        x2 = self.window_width - 32
        y2 = self.window_height - 54 if self.bubble_expanded else 164
        text_width = x2 - x1 - 34
        shadow = [(x1 + 10, y1 + 10), (x2 + 10, y1 + 10), (x2 + 10, y2 + 10), (x1 + 72, y2 + 10), (x1 + 50, y2 + 28), (x1 + 52, y2 + 10), (x1 + 10, y2 + 10)]
        bubble = [(x1, y1), (x2, y1), (x2, y2), (x1 + 62, y2), (x1 + 38, y2 + 24), (x1 + 42, y2), (x1, y2)]
        c.create_polygon(shadow, fill=self.skin_color("bubble_shadow"), outline=self.skin_color("bubble_shadow"))
        c.create_polygon(bubble, fill=self.skin_color("bubble_back"), outline=self.skin_color("bubble_back"), width=8)
        c.create_polygon(bubble, fill=self.skin_color("bubble"), outline=self.skin_color("ink"), width=3)
        self.draw_bubble_toggle(x2, y1)

        if self.bubble_expanded:
            lines = self.expanded_bubble_lines(text_width - 18)
            content_top = y1 + 48
            content_bottom = y2 - 18
            probe_y = content_top
            visible_count = 0
            for item in lines:
                if probe_y + item["height"] > content_bottom:
                    break
                probe_y += item["height"] + 3
                visible_count += 1

            self.bubble_max_scroll = max(0, len(lines) - max(visible_count, 1))
            self.bubble_scroll = max(0, min(self.bubble_scroll, self.bubble_max_scroll))

            y = content_top
            for item in lines[self.bubble_scroll :]:
                if y + item["height"] > content_bottom:
                    break
                if item["text"]:
                    c.create_text(
                        x1 + 18,
                        y,
                        text=item["text"],
                        fill=item["fill"],
                        font=item["font"],
                        anchor="nw",
                    )
                y += item["height"] + 3
            self.draw_bubble_scrollbar(x2 - 17, content_top, content_bottom)
            return

        self.bubble_max_scroll = 0
        self.bubble_scroll = 0

        reply_y = y1 + 20
        if self.user_text:
            user_font = ("Microsoft YaHei UI", 9)
            user_display = self.fit_text_to_box("你：" + self.user_text, user_font, text_width - 64, 28)
            c.create_text(
                x1 + 18,
                y1 + 16,
                text=user_display,
                fill=self.skin_color("user_text"),
                font=user_font,
                anchor="nw",
                width=text_width,
            )
            reply_y = y1 + 49

        text = self.visible_reply or self.full_reply or "……"
        cursor = "▌" if self.state == "speaking" else ""
        reply_font = ("Microsoft YaHei UI", 12, "bold")
        reply_display = self.fit_text_to_box(
            text + cursor,
            reply_font,
            text_width,
            y2 - reply_y - 12,
            keep_tail=self.state == "speaking",
        )
        c.create_text(
            x1 + 18,
            reply_y,
            text=reply_display,
            fill=self.skin_color("reply_text"),
            font=reply_font,
            anchor="nw",
            width=text_width,
        )

    def close(self) -> None:
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        try:
            self.recorder.stop()
        except Exception:
            pass
        try:
            self.desktop_recorder.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows floating paper-cut voice orb.")
    parser.add_argument("--button", choices=["x1", "x2", "middle"])
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--tts-output-format")
    parser.add_argument("--type-ms", type=int, default=32)
    parser.add_argument("--width", type=int, default=620)
    parser.add_argument("--height", type=int, default=230)
    parser.add_argument("--x", type=int, default=1180)
    parser.add_argument("--y", type=int, default=720)
    parser.add_argument("--no-hotkey", action="store_true")
    args = parser.parse_args()

    DesktopOrb(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
