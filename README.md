<a id="top"></a>

<div align="center">

# 幽浮

**Windows 桌面悬浮语音助手。按住说话，松开发送，听它回你。**

<p>
  中文 · <a href="./README_en.md">English</a>
</p>

<p>
  <a href="https://www.microsoft.com/windows">
    <img alt="平台：Windows" src="https://img.shields.io/badge/%E5%B9%B3%E5%8F%B0-Windows-0078D4?style=flat-square&logo=windows&logoColor=white">
  </a>
  <a href="https://www.python.org/">
    <img alt="Python 版本" src="https://img.shields.io/badge/Python-3.14+-3776AB?style=flat-square&logo=python&logoColor=white">
  </a>
  <a href="https://ai.google.dev/gemini-api/docs">
    <img alt="Gemini 多模态" src="https://img.shields.io/badge/Gemini-%E5%A4%9A%E6%A8%A1%E6%80%81-8E75B2?style=flat-square">
  </a>
  <a href="https://elevenlabs.io/docs">
    <img alt="ElevenLabs 语音合成" src="https://img.shields.io/badge/ElevenLabs-%E8%AF%AD%E9%9F%B3%E5%90%88%E6%88%90-111111?style=flat-square">
  </a>
  <a href="./LICENSE">
    <img alt="许可证：MIT" src="https://img.shields.io/badge/%E8%AE%B8%E5%8F%AF%E8%AF%81-MIT-green?style=flat-square">
  </a>
</p>

<p>
  <a href="#截图">截图</a> ·
  <a href="#功能">功能</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#配置">配置</a> ·
  <a href="#音频输入兼容性">音频输入</a> ·
  <a href="#构建">构建</a> ·
  <a href="#诊断">诊断</a>
</p>

</div>

> [!NOTE]
> 幽浮是本地 Windows 桌面应用，不是网页应用。[`web/`](./web) 只是保留的本地调试入口。

<a id="截图"></a>

## 截图

<p align="center">
  <img src="./docs/images/youfu-chat.png" alt="幽浮对话气泡和悬浮球" width="760">
</p>

<p align="center">
  <img src="./docs/images/youfu-hint.png" alt="幽浮操作提示气泡" width="520">
</p>

<a id="功能"></a>

## 功能

| 模块 | 说明 |
| --- | --- |
| 悬浮球 | 常驻桌面，支持拖拽、右键菜单、开机启动、透明度、边缘吸附和皮肤系统。 |
| 语音输入 | 按住快捷键录麦克风，松开发送；也可以取消当前录音。 |
| 桌面音频 | 可单独录制系统声音，适合让模型理解视频、会议或播放器内容。 |
| 多模态输入 | Gemini 格式网关可以直接接收音频和截图；录音时也能附加桌面截图。 |
| 模型网关 | 支持 Gemini 和 OpenAI 兼容格式。 |
| 语音输出 | 使用 ElevenLabs 生成回复语音，并在桌面播放。 |
| 对话气泡 | 漫画式对话框，支持流式文本、展开、滚动和用户转写展示。 |
| 人格约束 | 通过 [`prompts/persona.md`](./prompts/persona.md) 控制说话风格。 |
| 会话记忆 | 保留近期上下文，长上下文会自动摘要，避免无限增长。 |
| 诊断日志 | 可记录每轮音频、转写、模型回复和语音输出，方便排查误触和幻觉。 |

<p align="right"><a href="#top">回到顶部</a></p>

<a id="工作流"></a>

## 工作流

```text
麦克风 / 桌面音频 / 截图
-> 模型网关理解输入
-> 人格约束 + 会话上下文
-> 结构化返回 user_text 和 assistant_text
-> ElevenLabs 生成语音
-> 悬浮球播放语音并显示流式文本
```

使用 Gemini 格式时，音频和图片会直接发给模型。模型会返回：

```json
{
  "user_text": "用户说了什么，或 [no speech]",
  "assistant_text": "助手回复"
}
```

`user_text` 是模型根据音频理解出来的用户内容，用于展示、诊断和写入会话记忆。它不是固定的本地转写结果，所以如果短录音里只有噪声，可以通过诊断日志定位是录音问题还是模型幻觉。

<p align="right"><a href="#top">回到顶部</a></p>

<a id="音频输入兼容性"></a>

## 音频输入兼容性

幽浮不是所有网关格式都用同一种音频协议。实际行为如下：

| 网关格式 | 音频处理方式 | 截图处理方式 | 当前状态 |
| --- | --- | --- | --- |
| Gemini | 以 `inline_data` 直接把音频发给模型。 | 以 `inline_data` 直接附加图片。 | 推荐使用，体验最完整。 |
| OpenAI 兼容 | 以 Chat Completions 消息内容里的 `input_audio` 发送 base64 音频。 | 以 `image_url` 的 data URL 附加图片。 | 不是先转文字，但要求你的网关和模型真的支持 `input_audio`。 |

所以，OpenAI 兼容格式和 Gemini 一样都是“直接把音频交给模型理解”的设计，但协议字段不一样，兼容性取决于你接入的网关是否实现了这套 OpenAI 音频输入格式。

<p align="right"><a href="#top">回到顶部</a></p>

<a id="快速开始"></a>

## 快速开始

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动桌面悬浮球：

```powershell
.\run_desktop.ps1
```

也可以直接运行入口文件：

```powershell
python .\desktop_orb.py
```

首次启动后，在悬浮球右键菜单里打开设置，填入模型网关和 ElevenLabs 配置。

<a id="快捷键"></a>

## 快捷键

| 操作 | 默认按键 |
| --- | --- |
| 麦克风长按说话 | 鼠标侧键二 |
| 桌面音频输入 | Ctrl+3 |
| 录音中附加截图 | Alt |
| 取消当前录音 | 鼠标中键 |

所有键鼠触发项都在 **设置 -> 快捷键** 里单独配置，可以录制单键，也可以录制组合键。

<p align="right"><a href="#top">回到顶部</a></p>

<a id="配置"></a>

## 配置

大多数配置都可以在悬浮球右键菜单的 **设置** 里修改；同样的内容会保存到这些文件里。

| 文件 | 用途 |
| --- | --- |
| [`gemini_config.json`](./gemini_config.json) | 模型、网关地址、网关密钥、格式类型。 |
| [`tts_config.json`](./tts_config.json) | ElevenLabs 密钥、声音编号、语音模型、输出格式。 |
| [`.env.example`](./.env.example) | 本地环境变量示例。 |
| [`desktop_config.json`](./desktop_config.json) | 悬浮球名称、皮肤、大小、透明度、吸附、提示气泡、快捷键。 |
| [`session_config.json`](./session_config.json) | 会话记忆、摘要阈值、上下文长度。 |
| [`prompts/persona.md`](./prompts/persona.md) | 语音人格和回复风格。 |
| [`skins/`](./skins) | 皮肤元数据。 |
| [`assets/skins/`](./assets/skins) | 皮肤状态图。 |

> [!IMPORTANT]
> 不要把真实 API Key 提交到公开仓库。建议使用环境变量或设置窗口保存本地配置。

<a id="网关格式"></a>

## 网关格式

| 格式 | 适合场景 | 说明 |
| --- | --- | --- |
| Gemini | 原生音频和截图输入 | 当前推荐格式。 |
| OpenAI 兼容 | 支持 `input_audio` 的统一网关 | 可直接发送音频，但要求模型和网关支持。 |

相关文档：

- [Google Gemini API 文档](https://ai.google.dev/gemini-api/docs)
- [ElevenLabs API 文档](https://elevenlabs.io/docs)
- [PyInstaller 文档](https://pyinstaller.org/)
- [sounddevice 文档](https://python-sounddevice.readthedocs.io/)
- [soundcard 项目](https://github.com/bastibe/python-soundcard)
- [pynput 文档](https://pynput.readthedocs.io/)

<p align="right"><a href="#top">回到顶部</a></p>

<a id="命令行"></a>

## 命令行

文字对话：

```powershell
python .\voice_turn.py --text "你好，帮我总结一下今天的计划"
```

音频对话：

```powershell
python .\voice_turn.py --audio .\input.wav
```

音频加截图：

```powershell
python .\voice_turn.py --audio .\input.wav --image .\screenshot.png
```

桌面音频：

```powershell
python .\voice_turn.py --audio .\desktop.wav --audio-source desktop
```

新会话：

```powershell
python .\voice_turn.py --new-session
```

只生成语音：

```powershell
python .\tts.py "你好，这是一次语音合成测试。" --out outputs\test.mp3
```

<a id="构建"></a>

## 构建

构建 Windows 可执行文件：

```powershell
.\build_exe.ps1
```

构建产物会生成在本地 `release\幽浮\幽浮.exe`。`release/` 是生成目录，不会提交到仓库。

<p align="right"><a href="#top">回到顶部</a></p>

<a id="诊断"></a>

## 诊断

启用诊断日志后，每轮对话会写入：

```text
logs/voice-turns.jsonl
```

查看最近记录：

```powershell
python .\inspect_diagnostics.py --last 12
```

适合排查这些问题：

- 短按误触是否只录到了噪声。
- 桌面音频是否来自预期来源。
- 模型是否把静音或噪声幻觉成文字。
- `user_text` 是否和保存的音频一致。
- 语音输出是否完整返回。

<a id="项目结构"></a>

## 项目结构

| 路径 | 作用 |
| --- | --- |
| [`desktop_orb.py`](./desktop_orb.py) | 桌面悬浮球主界面、右键菜单、设置窗口和状态切换。 |
| [`voice_turn.py`](./voice_turn.py) | 完整的一轮语音对话流程。 |
| [`gemini_brain.py`](./gemini_brain.py) | 模型网关请求逻辑。 |
| [`gemini_audio.py`](./gemini_audio.py) | 音频和图片载荷处理。 |
| [`tts.py`](./tts.py) | ElevenLabs 语音合成。 |
| [`hotkey_listener.py`](./hotkey_listener.py) | 键盘和鼠标快捷键监听。 |
| [`inspect_diagnostics.py`](./inspect_diagnostics.py) | 诊断日志查看工具。 |
| [`build_exe.ps1`](./build_exe.ps1) | 打包脚本。 |
| [`docs/images/`](./docs/images) | README 截图。 |

<a id="本地调试"></a>

## 本地调试入口

桌面悬浮球是主界面。本地网页调试入口仍然保留：

```powershell
.\run_web.ps1
```

```text
http://127.0.0.1:8765
```

<p align="right"><a href="#top">回到顶部</a></p>

---

<div align="center">

为 Windows 桌面上的即时语音交流而做。

</div>
