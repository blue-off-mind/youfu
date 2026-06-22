# Security Policy

## Secrets

Do not commit real API keys, voice IDs, tokens, recordings, logs, or session files.

Use local environment variables or the settings window instead:

- `GEMINI_API_KEY`
- `AI_GATEWAY_API_KEY`
- `DEEPSEEK_API_KEY`
- `ELEVENLABS_API_KEY`

The repository intentionally ignores runtime data such as `logs/`, `outputs/`, `sessions/`, `tmp/`, `dist/`, `build/`, and `release/`.

## Reporting

If you find a leaked secret or a security issue in this project, open a private report with the repository owner instead of posting the secret in a public issue.
