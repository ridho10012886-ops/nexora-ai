# NEXORA AI — Local + Cloud

NEXORA desktop assistant for Windows, with Local AI via Ollama and optional Cloud AI APIs.

## Features
- Local AI via Ollama and installed models.
- Optional cloud providers: OpenAI API, Google Gemini API, OpenRouter.
- Provider and model name settings.
- API key stored using Windows DPAPI for the current Windows user; the key is not written into `settings.json`.
- API connection test and readable error messages.
- Chat history stored locally under `%LOCALAPPDATA%\NEXORA`.
- `.gitignore` excludes local settings, API-key blobs, and conversation databases.

## Run
Requires Windows and Python 3.12+.
1. Install Ollama from https://ollama.com/download for Local AI.
2. Download at least one supported local model, e.g. `ollama pull qwen2.5:0.5b`.
3. Run `python app\nexora_desktop.py`.

Cloud AI is optional. Add your own API key through **Pengaturan AI**. API usage may incur charges according to the provider. The app sends conversation context to the selected cloud provider only when Cloud AI is selected.

## Build EXE
```bat
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile --name NEXORA app\nexora_desktop.py
```
The EXE will be in `dist\NEXORA.exe`.

## Security notes
- Never commit API keys, settings, chat databases, or DPAPI secret files to GitHub.
- Windows DPAPI binds the encrypted API key to the current Windows user on that device. Users may need to enter the key again on another PC or Windows account.
- This app does not embed a shared developer API key.
- Review provider terms, privacy policies, pricing, and model availability before using a provider.
