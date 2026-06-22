<a id="top"></a>

<div align="center">

# 幽浮 / Youfu

**Windows 桌面悬浮语音助手。按住说话，松开发送，听它回你。**  
**A Windows floating voice assistant with hold-to-talk, multimodal input, and TTS playback.**

<p>
  <a href="#screenshots">Screenshots / 截图</a> ·
  <a href="#features">Features / 功能</a> ·
  <a href="#quick-start">Quick Start / 快速开始</a> ·
  <a href="#configuration">Configuration / 配置</a> ·
  <a href="#build">Build / 构建</a> ·
  <a href="#diagnostics">Diagnostics / 诊断</a>
</p>

<p>
  <a href="https://www.microsoft.com/windows">
    <img alt="Platform: Windows" src="https://img.shields.io/badge/platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white">
  </a>
  <a href="https://www.python.org/">
    <img alt="Python" src="https://img.shields.io/badge/python-3.14+-3776AB?style=flat-square&logo=python&logoColor=white">
  </a>
  <a href="https://ai.google.dev/gemini-api/docs">
    <img alt="Gemini multimodal" src="https://img.shields.io/badge/Gemini-multimodal-8E75B2?style=flat-square">
  </a>
  <a href="https://elevenlabs.io/docs">
    <img alt="ElevenLabs TTS" src="https://img.shields.io/badge/ElevenLabs-TTS-111111?style=flat-square">
  </a>
  <a href="./build_exe.ps1">
    <img alt="Build: PyInstaller" src="https://img.shields.io/badge/build-PyInstaller-5B5B5B?style=flat-square">
  </a>
  <a href="./LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green?style=flat-square">
  </a>
</p>

</div>

> [!NOTE]
> 幽浮是本地 Windows 桌面应用，不是网页应用。[`web/`](./web) 只是保留的本地调试入口。  
> Youfu is a local Windows desktop app. The [`web/`](./web) folder is kept only as a local debug surface.

<a id="screenshots"></a>

## Screenshots / 截图

<p align="center">
  <img src="./docs/images/youfu-chat.png" alt="Youfu chat bubble and floating orb" width="760">
</p>

<p align="center">
  <img src="./docs/images/youfu-hint.png" alt="Youfu operation hint bubble" width="520">
</p>

<a id="features"></a>

## Features / 功能

| Area / 模块 | What it does / 能做什么 |
| --- | --- |
| Floating orb / 悬浮球 | Always-on-top desktop orb, drag to move, right-click menu, startup launch, opacity, edge docking, skin system. |
| Voice input / 语音输入 | Hold a shortcut to record microphone audio, release to send, cancel mid-recording, or capture desktop/system audio separately. |
| Multimodal input / 多模态输入 | Gemini-style gateway can receive audio and screenshots directly; screenshot can be attached while recording. |
| AI gateway / 模型网关 | Supports Gemini, OpenAI-compatible, and Anthropic-compatible gateway formats through settings. |
| TTS playback / 语音输出 | Uses [ElevenLabs](https://elevenlabs.io/docs) TTS and plays the reply on desktop. |
| Conversation UI / 对话界面 | Comic-style reply bubble with streaming text, expandable history, scrollable user text and assistant text. |
| Persona / 人格约束 | Uses [`prompts/persona.md`](./prompts/persona.md) for short, spoken, conversational replies. |
| Session memory / 会话记忆 | Keeps session context and can summarize long context instead of letting it grow forever. |
| Diagnostics / 诊断 | Optional JSONL turn logs for checking recordings, transcripts, model output, and TTS playback. |

<p align="right"><a href="#top">Back to top / 回到顶部</a></p>

<a id="how-it-works"></a>

## How It Works / 工作流

```text
Microphone / desktop audio / screenshot
-> Gemini or compatible gateway
-> persona + session context
-> structured user_text + assistant_text
-> ElevenLabs TTS
-> floating orb playback + streaming bubble
```

For Gemini-format turns, audio and images are sent as multimodal input. The model is asked to return structured text:

```json
{
  "user_text": "what the user said, or [no speech]",
  "assistant_text": "the assistant reply"
}
```

中文说明：Gemini 格式会把音频和截图直接交给模型，不是先在本地固定转文字再发给 DeepSeek。`user_text` 是模型根据音频返回的“用户说了什么”，用于展示、诊断和会话记忆。

<p align="right"><a href="#top">Back to top / 回到顶部</a></p>

<a id="quick-start"></a>

## Quick Start / 快速开始

Install dependencies / 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

Start the desktop orb / 启动桌面悬浮球：

```powershell
.\run_desktop.ps1
```

Or run the Python entry directly / 或直接运行入口文件：

```powershell
python .\desktop_orb.py
```

The packaged executable is built to:

```text
release\幽浮\幽浮.exe
```

<a id="shortcuts"></a>

## Shortcuts / 快捷键

| Action / 操作 | Default / 默认 |
| --- | --- |
| Microphone hold-to-talk / 麦克风长按说话 | Mouse side button 2 / 鼠标侧键二 |
| Desktop audio input / 桌面音频输入 | Ctrl+3 |
| Attach screenshot while recording / 录音中附加截图 | Alt |
| Cancel current recording / 取消当前录音 | Middle mouse button / 鼠标中键 |

All keyboard and mouse triggers can be changed in **Settings -> Shortcuts**. You can record a single key/button or a modifier combination.

所有键鼠触发项都在 **设置 -> 快捷键** 里单独配置，可以录制单键，也可以录制组合键。

<p align="right"><a href="#top">Back to top / 回到顶部</a></p>

<a id="configuration"></a>

## Configuration / 配置

Most options are available from the orb right-click menu: **Settings / 设置**. The same state is stored in JSON files.

大多数配置都能在悬浮球右键菜单的 **设置** 里改；配置也会落在这些 JSON 文件里。

| File / 文件 | Purpose / 用途 |
| --- | --- |
| [`gemini_config.json`](./gemini_config.json) | AI model, gateway base URL, gateway API key, provider format. |
| [`tts_config.json`](./tts_config.json) | ElevenLabs API key, voice ID, TTS model, output format. |
| [`.env.example`](./.env.example) | Optional environment variable names for local secrets. |
| [`desktop_config.json`](./desktop_config.json) | Orb name, skin, size, opacity, edge docking, hint bubble, shortcuts. |
| [`session_config.json`](./session_config.json) | Session memory, summarization, context length. |
| [`prompts/persona.md`](./prompts/persona.md) | Spoken persona and reply style constraints. |
| [`skins/`](./skins) | Skin metadata. |
| [`assets/skins/`](./assets/skins) | Skin image assets for idle, recording, connecting, speaking, error. |

> [!IMPORTANT]
> Do not commit real API keys to a public repository. Test keys are convenient locally, but GitHub is very good at making secrets permanent.  
> 不建议把真实 API Key 提交到公开仓库。测试 Key 本地用很方便，但公开仓库会让它很难收回来。

<a id="gateway"></a>

## Gateway Modes / 网关格式

| Mode / 格式 | Best for / 适合 | Notes / 说明 |
| --- | --- | --- |
| Gemini | Native audio + image input / 原生音频和图片输入 | Recommended for this project. |
| OpenAI-compatible | Text, image, and provider-dependent audio / 文本、图片、取决于网关的音频 | Works with compatible gateway base URLs. |
| Anthropic-compatible | Text-oriented gateway use / 偏文本的网关调用 | Desktop voice flow treats it as a text-oriented format. |

External docs:

- [Google Gemini API documentation](https://ai.google.dev/gemini-api/docs)
- [ElevenLabs API documentation](https://elevenlabs.io/docs)
- [PyInstaller documentation](https://pyinstaller.org/)
- [sounddevice documentation](https://python-sounddevice.readthedocs.io/)
- [soundcard project](https://github.com/bastibe/python-soundcard)
- [pynput documentation](https://pynput.readthedocs.io/)

<p align="right"><a href="#top">Back to top / 回到顶部</a></p>

<a id="cli"></a>

## CLI Usage / 命令行用法

Text turn / 文字对话：

```powershell
python .\voice_turn.py --text "你好，帮我总结一下今天的计划"
```

Audio turn / 音频对话：

```powershell
python .\voice_turn.py --audio .\input.wav
```

Audio plus screenshot / 音频加截图：

```powershell
python .\voice_turn.py --audio .\input.wav --image .\screenshot.png
```

Desktop audio / 桌面音频：

```powershell
python .\voice_turn.py --audio .\desktop.wav --audio-source desktop
```

New session / 新会话：

```powershell
python .\voice_turn.py --new-session
```

TTS only / 只生成语音：

```powershell
python .\tts.py "你好，这是一次 TTS 测试。" --out outputs\test.mp3
```

<a id="build"></a>

## Build / 构建

Build the Windows executable / 构建 Windows 可执行文件：

```powershell
.\build_exe.ps1
```

Build output / 构建产物：

```text
release\幽浮\幽浮.exe
```

The build script copies required config files, prompt files, skins, assets, and runtime files into [`release/幽浮/`](./release/幽浮).

构建脚本会把运行所需的配置、prompt、皮肤、资源和运行时文件复制到 [`release/幽浮/`](./release/幽浮)。

<p align="right"><a href="#top">Back to top / 回到顶部</a></p>

<a id="diagnostics"></a>

## Diagnostics / 诊断

When diagnostic logging is enabled, each turn is written to:

```text
logs/voice-turns.jsonl
```

Inspect recent turns / 查看最近记录：

```powershell
python .\inspect_diagnostics.py --last 12
```

Use this when you need to check:

- Whether a short accidental recording was only noise.
- Whether desktop audio captured the expected source.
- Whether the model hallucinated speech from silence.
- Whether `user_text` matches the saved WAV.
- Whether TTS returned a complete audio file.

这个日志主要用来定位：误触噪声、桌面音频来源、模型把静音听成文字、`user_text` 和 wav 不一致、TTS 音频不完整等问题。

<a id="project-structure"></a>

## Project Structure / 项目结构

| Path / 路径 | Role / 作用 |
| --- | --- |
| [`desktop_orb.py`](./desktop_orb.py) | Main Windows floating orb UI, context menu, settings, state transitions. |
| [`voice_turn.py`](./voice_turn.py) | One complete user turn: input, model call, session, TTS. |
| [`gemini_brain.py`](./gemini_brain.py) | Gemini and gateway model request logic. |
| [`gemini_audio.py`](./gemini_audio.py) | Audio/image payload helpers. |
| [`tts.py`](./tts.py) | ElevenLabs TTS request and audio output generation. |
| [`hotkey_listener.py`](./hotkey_listener.py) | Keyboard and mouse trigger capture/listening. |
| [`inspect_diagnostics.py`](./inspect_diagnostics.py) | Diagnostic log reader. |
| [`build_exe.ps1`](./build_exe.ps1) | PyInstaller packaging script. |
| [`docs/images/`](./docs/images) | README screenshots. |

<a id="web-debug"></a>

## Web Debug UI / Web 调试入口

The desktop orb is the main UI. A legacy local web debug entry is still available:

桌面悬浮球才是主要界面；本地 Web 调试入口仍然保留：

```powershell
.\run_web.ps1
```

```text
http://127.0.0.1:8765
```

<p align="right"><a href="#top">Back to top / 回到顶部</a></p>

---

<div align="center">

Built for quick voice turns on Windows desktop.  
为 Windows 桌面上的即时语音交流而做。

</div>
