import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "gemini_config.json"


def load_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    provider = config.get("provider", "gemini")
    if provider == "gateway":
        gateway_key = config.get("gateway_api_key") or os.getenv(
            config.get("gateway_api_key_env", "AI_GATEWAY_API_KEY")
        )
        if not gateway_key:
            raise SystemExit("Gateway API key is not configured.")
        if not config.get("gateway_base_url"):
            raise SystemExit("Gateway base URL is not configured.")
        if not config.get("gateway_model"):
            raise SystemExit("Gateway model is not configured.")
        config["gateway_api_key"] = gateway_key
    else:
        api_key = config.get("api_key") or os.getenv(config.get("api_key_env", "GEMINI_API_KEY"))
        if not api_key:
            raise SystemExit(
                "Gemini API key is not configured. Add it to gemini_config.json "
                "or set the GEMINI_API_KEY environment variable."
            )
        config["api_key"] = api_key
    return config


def load_persona(config: dict) -> str:
    persona_file = config.get("persona_file", "prompts/persona.md")
    path = Path(persona_file)
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(f"Persona file not found: {path}")


def model_url(base_url: str, model: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith(":generateContent"):
        return base_url
    model = model.strip("/")
    if model.startswith("models/"):
        return f"{base_url}/{model}:generateContent"
    return f"{base_url}/models/{model}:generateContent"


def candidate_text(body: dict) -> str:
    try:
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini response: {json.dumps(body, ensure_ascii=False)}") from exc

    if not text:
        raise RuntimeError(f"Gemini returned empty text: {json.dumps(body, ensure_ascii=False)}")
    return text


def generate_with_model(parts: list[dict], config: dict, model: str, temperature: float | None = None) -> str:
    base_url = config.get("base_url", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": config.get("temperature", 0.7) if temperature is None else temperature,
            "maxOutputTokens": config.get("max_output_tokens", 900),
        },
    }
    request = urllib.request.Request(
        model_url(base_url, model),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": config["api_key"],
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        body = json.loads(response.read().decode("utf-8"))
    return candidate_text(body)


def generate(parts: list[dict], config: dict, temperature: float | None = None) -> str:
    models = [config.get("model", "gemini-2.5-flash"), *config.get("fallback_models", [])]
    models = list(dict.fromkeys(model for model in models if model))
    retryable_statuses = {429, 503}
    errors = []

    for model in models:
        try:
            return generate_with_model(parts, config, model, temperature)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            errors.append(f"{model}: HTTP {exc.code}: {body}")
            if exc.code not in retryable_statuses:
                break
        except urllib.error.URLError as exc:
            errors.append(f"{model}: network error: {exc}")
            break

    raise RuntimeError("Gemini generation failed:\n" + "\n".join(errors))


def parse_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def active_provider(config: dict) -> str:
    provider = config.get("provider", "gemini")
    return "gateway" if provider == "gateway" else "gemini"


def gateway_format(config: dict) -> str:
    value = str(config.get("gateway_format", "openai")).lower().strip()
    if value in {"gemini", "anthropic"}:
        return value
    return "openai"


def active_model_label(config: dict) -> str:
    if active_provider(config) == "gateway":
        return config.get("gateway_model") or "gateway-model"
    return config.get("model") or "gemini"


def append_endpoint(base_url: str, endpoint: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith(endpoint):
        return base
    return f"{base}{endpoint}"


def post_json(url: str, payload: dict, headers: dict, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def gateway_auth_headers(config: dict, protocol: str) -> dict:
    api_key = config["gateway_api_key"]
    header_mode = str(config.get("gateway_auth_header", "auto")).lower().strip()
    if header_mode in {"bearer", "authorization"}:
        return {"Authorization": f"Bearer {api_key}"}
    if header_mode in {"x-goog-api-key", "google"}:
        return {"x-goog-api-key": api_key}
    if header_mode in {"x-api-key", "api-key"}:
        return {"x-api-key": api_key}

    if protocol == "gemini":
        base_url = config.get("gateway_base_url", "")
        if "googleapis.com" in base_url:
            return {"x-goog-api-key": api_key}
        return {"Authorization": f"Bearer {api_key}"}
    if protocol == "anthropic":
        return {"x-api-key": api_key}
    return {"Authorization": f"Bearer {api_key}"}


def openai_message_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    return str(content).strip()


def gateway_openai_generate(
    config: dict,
    messages: list[dict],
    temperature: float | None = None,
    response_format_json: bool = False,
) -> str:
    url = append_endpoint(config["gateway_base_url"], "/chat/completions")
    payload = {
        "model": config["gateway_model"],
        "messages": messages,
        "temperature": config.get("temperature", 0.7) if temperature is None else temperature,
        "max_tokens": config.get("max_output_tokens", 900),
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}

    body = post_json(
        url,
        payload,
        {
            "Content-Type": "application/json",
            **gateway_auth_headers(config, "openai"),
        },
    )
    try:
        return openai_message_text(body["choices"][0]["message"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenAI-format gateway response: {json.dumps(body, ensure_ascii=False)}") from exc


def gateway_gemini_generate(parts: list[dict], config: dict, temperature: float | None = None) -> str:
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": config.get("temperature", 0.7) if temperature is None else temperature,
            "maxOutputTokens": config.get("max_output_tokens", 900),
        },
    }
    body = post_json(
        model_url(config["gateway_base_url"].rstrip("/"), config["gateway_model"]),
        payload,
        {
            "Content-Type": "application/json",
            **gateway_auth_headers(config, "gemini"),
        },
    )
    return candidate_text(body)


def gateway_anthropic_generate(
    config: dict,
    system_prompt: str,
    user_text: str,
    temperature: float | None = None,
) -> str:
    url = append_endpoint(config["gateway_base_url"], "/messages")
    payload = {
        "model": config["gateway_model"],
        "max_tokens": config.get("max_output_tokens", 900),
        "temperature": config.get("temperature", 0.7) if temperature is None else temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_text}],
    }
    body = post_json(
        url,
        payload,
        {
            "Content-Type": "application/json",
            **gateway_auth_headers(config, "anthropic"),
            "anthropic-version": config.get("anthropic_version", "2023-06-01"),
        },
    )
    try:
        parts = body["content"]
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Anthropic-format gateway response: {json.dumps(body, ensure_ascii=False)}") from exc


def generate_text(prompt: str, config: dict, temperature: float | None = None) -> str:
    if active_provider(config) == "gateway":
        fmt = gateway_format(config)
        if fmt == "gemini":
            return gateway_gemini_generate([{"text": prompt}], config, temperature).strip()
        if fmt == "anthropic":
            return gateway_anthropic_generate(config, base_instruction("", {"messages": []}, 0), prompt, temperature)
        return gateway_openai_generate(config, [{"role": "user", "content": prompt}], temperature).strip()
    return generate([{"text": prompt}], config, temperature).strip()


def generate_chat(system_prompt: str, user_text: str, config: dict, temperature: float | None = None) -> str:
    if active_provider(config) == "gateway":
        fmt = gateway_format(config)
        if fmt == "gemini":
            return gateway_gemini_generate([{"text": f"{system_prompt}\n\n{user_text}"}], config, temperature).strip()
        if fmt == "anthropic":
            return gateway_anthropic_generate(config, system_prompt, user_text, temperature).strip()
        return gateway_openai_generate(
            config,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature,
        ).strip()

    prompt = f"{system_prompt}\n\n{user_text}"
    return generate([{"text": prompt}], config, temperature).strip()


def recent_context(session: dict, max_recent_messages: int) -> str:
    lines = []
    if session.get("summary"):
        lines.append("当前 session 摘要：")
        lines.append(session["summary"])
        lines.append("")

    recent = session.get("messages", [])[-max_recent_messages:]
    if recent:
        lines.append("最近对话：")
        for message in recent:
            role = "用户" if message["role"] == "user" else "助手"
            lines.append(f"{role}: {message['content']}")
    return "\n".join(lines).strip()


def base_instruction(persona: str, session: dict, max_recent_messages: int) -> str:
    context = recent_context(session, max_recent_messages)
    parts = [
        "你是实时语音助手的主脑。请严格遵守下面的人格设定，并结合当前 session 上下文自然回复。",
        "人格设定：",
        persona,
    ]
    if context:
        parts.extend(["", context])
    return "\n".join(parts)


def text_reply(user_text: str, session: dict, persona: str, config: dict, max_recent_messages: int) -> tuple[str, str]:
    system_prompt = base_instruction(persona, session, max_recent_messages)
    user_prompt = (
        "本轮用户输入：\n"
        f"{user_text}\n\n"
        "请只输出助手要说的话，不要 Markdown，不要标题，不要解释。"
    )
    return user_text, generate_chat(system_prompt, user_prompt, config).strip()


def inline_file_part(path: Path) -> dict:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"inline_data": {"mime_type": mime_type, "data": data}}


def openai_image_part(path: Path) -> dict:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime_type};base64,{data}"},
    }


def audio_reply(
    audio_path: Path,
    session: dict,
    persona: str,
    config: dict,
    max_recent_messages: int,
    image_paths: list[Path] | None = None,
    audio_source: str = "microphone",
) -> tuple[str, str]:
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")
    image_paths = image_paths or []
    for image_path in image_paths:
        if not image_path.exists():
            raise SystemExit(f"Image file not found: {image_path}")

    mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    system_prompt = base_instruction(persona, session, max_recent_messages)
    source_hint = (
        "Audio source: desktop/system loopback. It may contain app, video, meeting, or game audio rather than the user's microphone speech."
        if audio_source == "desktop"
        else "Audio source: microphone."
    )
    attachment_hint = (
        "This turn also includes desktop screenshot attachment(s). Use them as visual context for the audio and answer."
        if image_paths
        else "No screenshot attachment is included in this turn."
    )
    prompt = (
        f"{source_hint}\n{attachment_hint}\n\n"
        "本轮用户输入是下面这段音频。请直接理解音频内容、语气和意图，然后生成适合实时 TTS 播放的回复。\n"
        "如果音频里没有可辨认的人声、只有噪声或误触，请不要猜测内容；user_text 写为 [no speech]，assistant_text 简短说明没有听清。\n"
        "你必须只输出 JSON，不要 Markdown，不要代码块，格式如下：\n"
        '{"user_text":"这里写对用户音频的简短准确转写","assistant_text":"这里写助手回复"}\n'
        "user_text 用简体中文；如果音频里有英文、数字或专有名词，保留原样。"
    )

    gemini_parts = [
        {"text": f"{system_prompt}\n\n{prompt}"},
        {"inline_data": {"mime_type": mime_type, "data": audio_b64}},
        *[inline_file_part(path) for path in image_paths],
    ]

    if active_provider(config) == "gateway":
        fmt = gateway_format(config)
        if fmt == "gemini":
            text = gateway_gemini_generate(gemini_parts, config)
        elif fmt == "openai":
            audio_format = "wav" if audio_path.suffix.lower() == ".wav" else audio_path.suffix.lower().lstrip(".")
            openai_content = [
                {"type": "text", "text": prompt},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}},
                *[openai_image_part(path) for path in image_paths],
            ]
            text = gateway_openai_generate(
                config,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": openai_content},
                ],
                response_format_json=True,
            )
        else:
            raise RuntimeError(
                "Anthropic-format gateway does not accept audio in this app. "
                "Use Gateway · Gemini 格式 or Gateway · OpenAI 格式 for voice turns."
            )
    else:
        text = generate(gemini_parts, config)

    try:
        payload = parse_json_object(text)
    except json.JSONDecodeError:
        return "[audio input]", text.strip()

    user_text = str(payload.get("user_text") or "[audio input]").strip()
    assistant_text = str(payload.get("assistant_text") or "").strip()
    if not assistant_text:
        assistant_text = text.strip()
    return user_text, assistant_text


def summarize_session(session: dict, config: dict, session_config: dict) -> str:
    max_chars = int(session_config.get("summary_max_chars", 1600))
    transcript = "\n".join(
        f"{'用户' if item['role'] == 'user' else '助手'}: {item['content']}"
        for item in session.get("messages", [])
    )
    prompt = (
        "把下面的旧对话压缩成给实时语音助手使用的 session 摘要。"
        "保留用户偏好、正在讨论的主题、明确约定、待办和情绪线索。"
        "不要编造，不要保留无意义寒暄。"
        f"控制在 {max_chars} 个中文字符以内。只输出摘要文本。\n\n"
        f"已有摘要：\n{session.get('summary', '')}\n\n"
        f"对话：\n{transcript}"
    )
    return generate_text(prompt, config, temperature=0.2).strip()[:max_chars]
