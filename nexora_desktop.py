# NEXORA Desktop v1.4 - MULTI MODEL
# Gemma 3 1B + Qwen 2.5 0.5B + Qwen 3.5 4B
# Windows / Python 3.12 / Ollama / Tkinter

import json
import base64
import ctypes
import ctypes.wintypes
import os
import queue
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

APP_NAME = "NEXORA"
APP_VERSION = "1.5 LOCAL + CLOUD"

GEMMA_MODEL = "gemma3:1b"
LIGHT_MODEL = "qwen2.5:0.5b"
CODING_MODEL = "qwen3.5:4b"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "NEXORA"
CHAT_DIR = DATA_DIR / "Riwayat_Chat"
APP_OUTPUT_DIR = DATA_DIR / "Hasil_Aplikasi"
DB_PATH = DATA_DIR / "nexora_history.db"
CONFIG_PATH = DATA_DIR / "settings.json"
SECRET_PATH = DATA_DIR / "api_key.dpapi"

for folder in (DATA_DIR, CHAT_DIR, APP_OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)

BG = "#080D18"
PANEL = "#101A2B"
PANEL2 = "#14223A"
BLUE = "#168BFF"
CYAN = "#39D7FF"
TEXT = "#E8F2FF"
MUTED = "#8DA5C4"
GREEN = "#35D49A"
RED = "#FF647C"

SYSTEM_PROMPT = """Kamu adalah NEXORA, asisten AI lokal milik pengguna.
Jawab dalam Bahasa Indonesia kecuali diminta bahasa lain.
Berikan jawaban yang jelas, berguna, dan langsung ke inti.
Untuk pemrograman, berikan kode lengkap yang dapat dijalankan dan jelaskan nama file serta cara menjalankannya.
Jangan mengaku telah menjalankan kode atau memeriksa file jika belum dilakukan.
Jika pengguna meminta aplikasi, prioritaskan solusi sederhana yang sesuai Windows dan Python.
Jaga identitas sebagai NEXORA. Jangan menyebut dirimu ChatGPT.
"""

MODEL_LABELS = {
    "Otomatis": "Otomatis",
    GEMMA_MODEL: "Gemma 3 1B",
    LIGHT_MODEL: "Qwen 2.5 0.5B",
    CODING_MODEL: "Qwen 3.5 4B",
    "Kolaborasi semua": "Kolaborasi semua model",
}

def http_json(url, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="GET" if data is None else "POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def get_installed_models():
    try:
        data = http_json(OLLAMA_TAGS_URL, timeout=8)
        names = []
        for item in data.get("models", []):
            name = item.get("name") or item.get("model")
            if name:
                names.append(name)
        return names, None
    except Exception as exc:
        return [], str(exc)

def model_is_installed(model, installed):
    return any(name == model for name in installed)

def extract_code(text):
    match = re.search(r"```(?:python|py)?\s*(.*?)```", text, re.I | re.S)
    return match.group(1).strip() if match else None

def choose_model(prompt, mode):
    p = prompt.lower()
    coding_words = (
        "buat aplikasi", "buat program", "buat website", "buat web",
        "kode", "coding", "python", "html", "css", "javascript",
        "debug", "error", "perbaiki", "script", "program", "project",
        "proyek", "aplikasi", "fungsi", "class ", "database", "tkinter"
    )
    if mode in ("Coding", "Proyek") or any(word in p for word in coding_words):
        return CODING_MODEL
    light_words = ("halo", "hai", "makasih", "terima kasih", "jam berapa",
                   "siapa namamu", "apa kabar", "selamat pagi", "selamat malam")
    if len(p) < 90 or any(word in p for word in light_words):
        return LIGHT_MODEL
    return GEMMA_MODEL

def ask_ollama(model, messages, timeout=600, num_predict=512):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.35,
            "num_predict": num_predict,
            "num_ctx": 4096
        }
    }
    result = http_json(OLLAMA_URL, payload, timeout=timeout)
    return (result.get("message") or {}).get("content", "").strip()


def load_settings():
    defaults = {
        "engine": "Local AI",
        "provider": "OpenAI",
        "cloud_model": "gpt-4o-mini",
        "local_model": "Otomatis",
        "api_key_saved": False,
    }
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        defaults.update({k: v for k, v in data.items() if k in defaults and k != "api_key_saved"})
    except Exception:
        pass
    defaults["api_key_saved"] = SECRET_PATH.exists()
    return defaults

def save_settings(settings):
    safe = {k: settings.get(k) for k in ("engine", "provider", "cloud_model", "local_model")}
    CONFIG_PATH.write_text(json.dumps(safe, indent=2, ensure_ascii=False), encoding="utf-8")

def protect_secret_windows(secret):
    """Encrypt API key using Windows DPAPI; key is bound to the current Windows user."""
    if os.name != "nt":
        raise RuntimeError("Penyimpanan API key terenkripsi ini hanya didukung di Windows.")
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    raw = secret.encode("utf-8")
    buf = ctypes.create_string_buffer(raw)
    in_blob = DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    crypt = ctypes.windll.crypt32.CryptProtectData
    crypt.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.wintypes.LPCWSTR,
                      ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
                      ctypes.wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt.restype = ctypes.wintypes.BOOL
    if not crypt(ctypes.byref(in_blob), "NEXORA API Key", None, None, None, 0,
                 ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        SECRET_PATH.write_bytes(encrypted)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)

def unprotect_secret_windows():
    if os.name != "nt" or not SECRET_PATH.exists():
        return ""
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    encrypted = SECRET_PATH.read_bytes()
    buf = ctypes.create_string_buffer(encrypted)
    in_blob = DATA_BLOB(len(encrypted), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    crypt = ctypes.windll.crypt32.CryptUnprotectData
    crypt.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.POINTER(ctypes.wintypes.LPWSTR),
                      ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
                      ctypes.wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt.restype = ctypes.wintypes.BOOL
    if not crypt(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)

def ask_cloud(provider, model, api_key, messages, timeout=120):
    if not api_key:
        raise RuntimeError("API key belum disimpan. Buka Pengaturan AI.")
    if provider == "Gemini":
        contents = []
        system_parts = []
        for m in messages:
            if m["role"] == "system":
                system_parts.append(m["content"])
            else:
                contents.append({"role": "model" if m["role"] == "assistant" else "user",
                                 "parts": [{"text": m["content"]}]})
        payload = {"contents": contents, "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048}}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        result = http_json(url, payload, timeout=timeout)
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Respons Gemini tidak berisi teks yang bisa dibaca.")
    if provider == "OpenAI":
        url = "https://api.openai.com/v1/chat/completions"
    elif provider == "OpenRouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
    else:
        raise RuntimeError("Penyedia API belum didukung.")
    payload = {"model": model, "messages": messages, "temperature": 0.4}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:700]
        if exc.code in (401, 403):
            raise RuntimeError("API key ditolak atau tidak punya izin. Periksa key dan akses model.")
        if exc.code == 429:
            raise RuntimeError("Batas penggunaan API tercapai atau saldo/kuota tidak cukup.")
        raise RuntimeError(f"API {provider} error HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Tidak dapat terhubung ke {provider}: {exc}")

class NexoraApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} Desktop {APP_VERSION}")
        self.root.geometry("1120x760")
        self.root.minsize(850, 600)
        self.root.configure(bg=BG)

        self.events = queue.Queue()
        self.busy = False
        self.current_file_context = ""
        self.current_file_name = ""
        self.voice_enabled = False
        self.installed_models = []
        self.settings = load_settings()
        self.selected_chat_id = None
        self._init_db()
        self._setup_style()
        self._build_ui()
        self._load_history_list()
        self._new_chat(silent=True)
        self._poll_events()
        threading.Thread(target=self._check_ollama, daemon=True).start()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(chat_id) REFERENCES chats(id)
                )
            """)
            conn.commit()

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2,
                        foreground=TEXT, arrowcolor=CYAN)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL2)],
                  foreground=[("readonly", TEXT)])
        style.configure("Vertical.TScrollbar", background=PANEL2,
                        troughcolor=BG, arrowcolor=CYAN)

    def _build_ui(self):
        # Layout utama memakai grid agar kotak chat dan tombol KIRIM
        # selalu mendapat ruang sendiri dan tidak tertutup area percakapan.
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.root, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        tk.Label(header, text="NEXORA", bg=BG, fg=CYAN,
                 font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(header, text=f"  YOUR LOCAL AI  •  {APP_VERSION}",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", pady=(9, 0))
        self.status_label = tk.Label(header, text="Memeriksa Ollama...",
                                     bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.status_label.pack(side="right", pady=(10, 0))

        main = tk.Frame(self.root, bg=BG)
        main.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)

        sidebar = tk.Frame(main, bg=PANEL, width=235)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        sidebar.grid_propagate(False)

        tk.Button(sidebar, text="+  Chat Baru", command=self._new_chat,
                  bg=BLUE, fg="white", activebackground=CYAN,
                  activeforeground=BG, relief="flat", font=("Segoe UI", 10, "bold"),
                  padx=10, pady=10, cursor="hand2").pack(fill="x", padx=12, pady=(14, 10))
        tk.Label(sidebar, text="RIWAYAT CHAT", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(8, 5))
        history_frame = tk.Frame(sidebar, bg=PANEL)
        history_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.history_list = tk.Listbox(
            history_frame, bg=PANEL, fg=TEXT, selectbackground="#174D7B",
            selectforeground="white", relief="flat", borderwidth=0,
            font=("Segoe UI", 9), activestyle="none"
        )
        self.history_list.pack(fill="both", expand=True)
        self.history_list.bind("<<ListboxSelect>>", self._on_history_select)

        tk.Button(sidebar, text="Buka file untuk konteks", command=self._open_file,
                  bg=PANEL2, fg=TEXT, activebackground="#1B3558",
                  relief="flat", font=("Segoe UI", 9), pady=8).pack(fill="x", padx=12, pady=(0, 6))
        tk.Button(sidebar, text="Folder hasil aplikasi", command=self._open_output_folder,
                  bg=PANEL2, fg=TEXT, activebackground="#1B3558",
                  relief="flat", font=("Segoe UI", 9), pady=8).pack(fill="x", padx=12, pady=(0, 12))

        chat_panel = tk.Frame(main, bg=BG)
        chat_panel.grid(row=0, column=1, sticky="nsew")
        chat_panel.grid_columnconfigure(0, weight=1)
        chat_panel.grid_rowconfigure(1, weight=1)

        toolbar = tk.Frame(chat_panel, bg=BG)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(toolbar, text="Mode", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        self.mode_var = tk.StringVar(value="Chat")
        self.mode_box = ttk.Combobox(toolbar, textvariable=self.mode_var,
                                     values=("Chat", "Coding", "Proyek"),
                                     state="readonly", width=10)
        self.mode_box.pack(side="left", padx=(0, 12))
        tk.Label(toolbar, text="Model", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        self.model_var = tk.StringVar(value="Otomatis")
        self.model_box = ttk.Combobox(
            toolbar, textvariable=self.model_var,
            values=("Otomatis", GEMMA_MODEL, LIGHT_MODEL, CODING_MODEL, "Kolaborasi semua"),
            state="readonly", width=22
        )
        self.model_box.pack(side="left")
        tk.Button(toolbar, text="Pengaturan AI", command=self._open_settings,
                  bg=PANEL2, fg=CYAN, relief="flat", padx=12, pady=6).pack(side="right", padx=(8, 0))
        tk.Button(toolbar, text="Simpan kode", command=self._save_code,
                  bg=PANEL2, fg=TEXT, relief="flat", padx=12, pady=6).pack(side="right")

        self.chat_text = tk.Text(
            chat_panel, bg=PANEL, fg=TEXT, insertbackground=CYAN,
            selectbackground="#174D7B", wrap="word", relief="flat",
            padx=16, pady=14, font=("Segoe UI", 10), spacing1=3, spacing3=8,
            state="disabled"
        )
        self.chat_text.grid(row=1, column=0, sticky="nsew")
        self.chat_text.tag_configure("user", foreground=CYAN, font=("Segoe UI", 10, "bold"))
        self.chat_text.tag_configure("assistant", foreground=GREEN, font=("Segoe UI", 10, "bold"))
        self.chat_text.tag_configure("body", foreground=TEXT)
        self.chat_text.tag_configure("system", foreground=MUTED, font=("Segoe UI", 9, "italic"))

        # Composer dipasang pada baris khusus; tidak bisa terdorong keluar
        # oleh widget percakapan yang mengembang.
        composer = tk.Frame(chat_panel, bg=PANEL, padx=10, pady=10)
        composer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        composer.grid_columnconfigure(0, weight=1)
        self.input_text = tk.Text(
            composer, height=3, bg=PANEL2, fg=TEXT, insertbackground=CYAN,
            relief="flat", wrap="word", font=("Segoe UI", 10), padx=10, pady=8
        )
        self.input_text.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.input_text.bind("<Control-Return>", lambda event: self._send())
        self.send_button = tk.Button(
            composer, text="KIRIM  ➤", command=self._send, bg=BLUE, fg="white",
            activebackground=CYAN, activeforeground=BG, relief="flat",
            font=("Segoe UI", 10, "bold"), padx=18, pady=12, cursor="hand2"
        )
        self.send_button.grid(row=0, column=1, sticky="ns")

        bottom = tk.Frame(chat_panel, bg=BG)
        bottom.grid(row=3, column=0, sticky="ew", pady=(7, 0))
        self.file_label = tk.Label(bottom, text="Konteks file: tidak ada",
                                   bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.file_label.pack(side="left")
        tk.Button(bottom, text="Reset konteks", command=self._clear_file_context,
                  bg=BG, fg=MUTED, activeforeground=CYAN, relief="flat",
                  font=("Segoe UI", 8)).pack(side="left", padx=8)
        tk.Button(bottom, text="Suara: OFF", command=self._toggle_voice,
                  bg=BG, fg=MUTED, activeforeground=CYAN, relief="flat",
                  font=("Segoe UI", 8)).pack(side="right")

    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Pengaturan Mesin AI - NEXORA")
        win.configure(bg=BG)
        win.geometry("560x500")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="PENGATURAN MESIN AI", bg=BG, fg=CYAN,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=22, pady=(18, 12))
        form = tk.Frame(win, bg=BG)
        form.pack(fill="both", expand=True, padx=22)
        form.grid_columnconfigure(1, weight=1)

        tk.Label(form, text="Mesin AI", bg=BG, fg=TEXT).grid(row=0, column=0, sticky="w", pady=8)
        engine_var = tk.StringVar(value=self.settings.get("engine", "Local AI"))
        engine_box = ttk.Combobox(form, textvariable=engine_var,
                                  values=("Local AI", "Cloud AI (API Key)"),
                                  state="readonly", width=30)
        engine_box.grid(row=0, column=1, sticky="ew", pady=8)

        tk.Label(form, text="Penyedia cloud", bg=BG, fg=TEXT).grid(row=1, column=0, sticky="w", pady=8)
        provider_var = tk.StringVar(value=self.settings.get("provider", "OpenAI"))
        provider_box = ttk.Combobox(form, textvariable=provider_var,
                                    values=("OpenAI", "Gemini", "OpenRouter"),
                                    state="readonly", width=30)
        provider_box.grid(row=1, column=1, sticky="ew", pady=8)

        tk.Label(form, text="Nama model", bg=BG, fg=TEXT).grid(row=2, column=0, sticky="w", pady=8)
        model_var = tk.StringVar(value=self.settings.get("cloud_model", "gpt-4o-mini"))
        model_entry = tk.Entry(form, textvariable=model_var, bg=PANEL2, fg=TEXT,
                               insertbackground=CYAN, relief="flat")
        model_entry.grid(row=2, column=1, sticky="ew", pady=8, ipady=7)

        tk.Label(form, text="API key baru", bg=BG, fg=TEXT).grid(row=3, column=0, sticky="w", pady=8)
        key_var = tk.StringVar()
        key_entry = tk.Entry(form, textvariable=key_var, show="•", bg=PANEL2, fg=TEXT,
                             insertbackground=CYAN, relief="flat")
        key_entry.grid(row=3, column=1, sticky="ew", pady=8, ipady=7)

        key_status = "API key tersimpan terenkripsi di Windows." if SECRET_PATH.exists() else "Belum ada API key tersimpan."
        key_status_label = tk.Label(form, text=key_status, bg=BG, fg=MUTED,
                                    font=("Segoe UI", 8), wraplength=330, justify="left")
        key_status_label.grid(row=4, column=1, sticky="w", pady=(0, 8))

        tk.Label(form, text="Model lokal", bg=BG, fg=TEXT).grid(row=5, column=0, sticky="w", pady=8)
        local_var = tk.StringVar(value=self.settings.get("local_model", "Otomatis"))
        local_box = ttk.Combobox(form, textvariable=local_var,
                                 values=("Otomatis", LIGHT_MODEL, GEMMA_MODEL, CODING_MODEL, "Kolaborasi semua"),
                                 state="readonly", width=30)
        local_box.grid(row=5, column=1, sticky="ew", pady=8)

        hint = ("API key disimpan menggunakan enkripsi Windows DPAPI untuk akun Windows ini. "
                "Key tidak ditulis ke settings.json dan jangan pernah dimasukkan ke GitHub.")
        tk.Label(win, text=hint, bg=BG, fg=MUTED, wraplength=510,
                 justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=22, pady=(6, 10))

        def save():
            engine = engine_var.get()
            provider = provider_var.get()
            model = model_var.get().strip()
            key = key_var.get().strip()
            if engine.startswith("Cloud") and not model:
                messagebox.showerror("Pengaturan", "Masukkan nama model cloud.", parent=win)
                return
            try:
                if key:
                    protect_secret_windows(key)
                self.settings.update({
                    "engine": "Cloud AI (API Key)" if engine.startswith("Cloud") else "Local AI",
                    "provider": provider,
                    "cloud_model": model or "gpt-4o-mini",
                    "local_model": local_var.get(),
                    "api_key_saved": SECRET_PATH.exists(),
                })
                save_settings(self.settings)
                self.model_var.set(local_var.get())
                self.status_label.configure(
                    text=("Cloud AI • " + provider if engine.startswith("Cloud") else "Local AI • Ollama"),
                    fg=CYAN
                )
                messagebox.showinfo("Pengaturan tersimpan",
                                    "Pengaturan NEXORA berhasil disimpan.", parent=win)
                win.destroy()
            except Exception as exc:
                messagebox.showerror("Gagal menyimpan", str(exc), parent=win)

        buttons = tk.Frame(win, bg=BG)
        buttons.pack(fill="x", padx=22, pady=(0, 18))
        tk.Button(buttons, text="Uji koneksi", command=lambda: self._test_cloud_settings(
            provider_var.get(), model_var.get().strip(), key_var.get().strip(), win),
            bg=PANEL2, fg=CYAN, relief="flat", padx=12, pady=9).pack(side="left")
        tk.Button(buttons, text="Simpan pengaturan", command=save,
                  bg=BLUE, fg="white", relief="flat", padx=14, pady=9).pack(side="right")

    def _test_cloud_settings(self, provider, model, key, parent):
        if not key:
            try:
                key = unprotect_secret_windows()
            except Exception as exc:
                messagebox.showerror("API key", str(exc), parent=parent)
                return
        if not key:
            messagebox.showwarning("API key", "Masukkan API key terlebih dahulu.", parent=parent)
            return
        self.status_label.configure(text="Menguji koneksi API...", fg=CYAN)
        def worker():
            try:
                answer = ask_cloud(provider, model, key,
                                   [{"role": "user", "content": "Balas singkat: koneksi berhasil."}],
                                   timeout=30)
                self.events.put(("test_ok", (provider, answer[:150])))
            except Exception as exc:
                self.events.put(("test_error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _append(self, role, content):
        self.chat_text.configure(state="normal")
        if role == "user":
            label, tag = "KAMU", "user"
        elif role == "assistant":
            label, tag = "NEXORA", "assistant"
        else:
            label, tag = "INFO", "system"
        self.chat_text.insert("end", label + "\n", tag)
        self.chat_text.insert("end", content.rstrip() + "\n\n", "body")
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def _new_chat(self, silent=False):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO chats(title, created_at) VALUES(?, ?)",
                ("Chat baru", datetime.now().isoformat(timespec="seconds"))
            )
            self.selected_chat_id = cur.lastrowid
            conn.commit()
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        self.chat_text.configure(state="disabled")
        self._append("system", "NEXORA siap. Pilih model Otomatis, model tertentu, atau Kolaborasi semua.")
        self._load_history_list()
        if not silent:
            self.input_text.focus_set()

    def _load_history_list(self):
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT id, title FROM chats ORDER BY id DESC LIMIT 100"
            ).fetchall()
        self.history_rows = rows
        self.history_list.delete(0, "end")
        for chat_id, title in rows:
            self.history_list.insert("end", f"{chat_id} · {title[:26]}")

    def _on_history_select(self, _event=None):
        selection = self.history_list.curselection()
        if not selection:
            return
        index = selection[0]
        chat_id, _title = self.history_rows[index]
        self.selected_chat_id = chat_id
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE chat_id=? ORDER BY id",
                (chat_id,)
            ).fetchall()
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        self.chat_text.configure(state="disabled")
        for role, content in rows:
            self._append(role if role in ("user", "assistant") else "system", content)
        if not rows:
            self._append("system", "Belum ada pesan di chat ini.")

    def _save_message(self, role, content, model=""):
        if not self.selected_chat_id:
            return
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO messages(chat_id, role, content, model, created_at) VALUES(?,?,?,?,?)",
                (self.selected_chat_id, role, content, model,
                 datetime.now().isoformat(timespec="seconds"))
            )
            if role == "user":
                count = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE chat_id=?",
                    (self.selected_chat_id,)
                ).fetchone()[0]
                if count <= 1:
                    title = content.replace("\n", " ").strip()[:38] or "Chat baru"
                    conn.execute("UPDATE chats SET title=? WHERE id=?",
                                 (title, self.selected_chat_id))
            conn.commit()
        self._load_history_list()

    def _send(self):
        if self.busy:
            return
        prompt = self.input_text.get("1.0", "end").strip()
        if not prompt:
            return
        self.input_text.delete("1.0", "end")
        self._append("user", prompt)
        self._save_message("user", prompt)
        mode = self.mode_var.get()
        selected_choice = self.model_var.get()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if self.current_file_context:
            messages.append({
                "role": "system",
                "content": "Isi file yang dipilih pengguna berikut adalah konteks. Gunakan seperlunya.\n"
                           f"NAMA FILE: {self.current_file_name}\n"
                           f"ISI FILE:\n{self.current_file_context[:16000]}"
            })
        # Ambil maksimal 12 pesan terakhir dari chat aktif.
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 12",
                (self.selected_chat_id,)
            ).fetchall()
        for role, content in reversed(rows):
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
        self.busy = True
        self.send_button.configure(state="disabled", text="MENUNGGU...")
        self.status_label.configure(text="AI sedang berpikir...", fg=CYAN)
        threading.Thread(
            target=self._worker, args=(messages, mode, selected_choice),
            daemon=True
        ).start()

    def _worker(self, messages, mode, selected_choice):
        try:
            if self.settings.get("engine") == "Cloud AI (API Key)":
                api_key = unprotect_secret_windows()
                provider = self.settings.get("provider", "OpenAI")
                model = self.settings.get("cloud_model", "gpt-4o-mini")
                self.events.put(("status", f"Menghubungi {provider} • {model}..."))
                answer = ask_cloud(provider, model, api_key, messages, timeout=180)
                if not answer:
                    raise RuntimeError("Penyedia cloud mengembalikan jawaban kosong.")
                self.events.put(("answer", answer, f"{provider} / {model}"))
                return
            installed, err = get_installed_models()
            if err:
                raise RuntimeError("Tidak dapat menghubungi Ollama. Pastikan aplikasi Ollama berjalan.\n" + err)
            self.installed_models = installed
            available = [m for m in (GEMMA_MODEL, LIGHT_MODEL, CODING_MODEL)
                         if model_is_installed(m, installed)]
            if not available:
                raise RuntimeError("Tidak ada model NEXORA yang ditemukan. Jalankan ollama list untuk memeriksa model.")
            if selected_choice == "Kolaborasi semua":
                answer, used = self._collaborate(messages, available)
            else:
                saved_local = self.settings.get("local_model", "Otomatis")
                if selected_choice == "Otomatis" and saved_local != "Otomatis":
                    preferred = saved_local
                elif selected_choice == "Otomatis":
                    preferred = choose_model(messages[-1]["content"], mode)
                else:
                    preferred = selected_choice
                candidates = [preferred] + [m for m in available if m != preferred]
                answer, used = "", ""
                errors = []
                for model in candidates:
                    if model not in available:
                        continue
                    self.events.put(("status", f"Mencoba {model}..."))
                    try:
                        answer = self._request_model(model, messages)
                        if answer:
                            used = model
                            break
                        errors.append(f"{model}: jawaban kosong")
                    except Exception as exc:
                        errors.append(f"{model}: {exc}")
                if not answer:
                    raise RuntimeError("Semua model gagal:\n" + "\n".join(errors))
            self.events.put(("answer", answer, used))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _request_model(self, model, messages, num_predict=512):
        # Timeout panjang karena inferensi CPU dapat lambat di RAM 4 GB.
        return ask_ollama(model, messages, timeout=600, num_predict=num_predict)

    def _collaborate(self, messages, available):
        results = []
        errors = []
        for model in (LIGHT_MODEL, GEMMA_MODEL, CODING_MODEL):
            if model not in available:
                continue
            self.events.put(("status", f"Kolaborasi: {model} sedang menjawab..."))
            try:
                answer = self._request_model(model, messages, num_predict=300)
                if answer:
                    results.append((model, answer))
            except Exception as exc:
                errors.append(f"{model}: {exc}")
        if not results:
            raise RuntimeError("Semua model kolaborasi gagal:\n" + "\n".join(errors))
        if len(results) == 1:
            return f"Kolaborasi hanya mendapat satu jawaban dari {results[0][0]}:\n\n{results[0][1]}", results[0][0]
        combined = "\n\n".join(
            f"MODEL: {model}\nJAWABAN:\n{answer}" for model, answer in results
        )
        merge_messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\nGabungkan jawaban beberapa model menjadi satu jawaban akhir yang akurat, tidak berulang, dan mudah dipahami. Jika ada perbedaan, sebutkan dengan hati-hati."},
            {"role": "user", "content": "Gabungkan jawaban model berikut untuk menjawab pertanyaan pengguna.\n\n" + combined}
        ]
        merger = GEMMA_MODEL if GEMMA_MODEL in available else results[0][0]
        self.events.put(("status", f"Menggabungkan jawaban dengan {merger}..."))
        try:
            final_answer = self._request_model(merger, merge_messages, num_predict=512)
            if final_answer:
                used = " + ".join(model for model, _ in results) + f" → ringkasan {merger}"
                return final_answer, used
        except Exception:
            pass
        fallback = "\n\n".join(f"**{model}**\n{answer}" for model, answer in results)
        return fallback, " + ".join(model for model, _ in results)

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "status":
                    self.status_label.configure(text=event[1], fg=CYAN)
                elif kind == "answer":
                    answer, used = event[1], event[2]
                    self._append("assistant", answer + (f"\n\n[Model: {used}]" if used else ""))
                    self._save_message("assistant", answer, used)
                    self.status_label.configure(text=f"Selesai • {used}", fg=GREEN)
                    if self.voice_enabled:
                        threading.Thread(target=self._speak, args=(answer,), daemon=True).start()
                    self.busy = False
                    self.send_button.configure(state="normal", text="KIRIM  ➤")
                elif kind == "error":
                    self._append("system", "Terjadi kesalahan:\n" + event[1])
                    self.status_label.configure(text="Gagal", fg=RED)
                    self.busy = False
                    self.send_button.configure(state="normal", text="KIRIM  ➤")
                elif kind == "test_ok":
                    self.status_label.configure(text="Uji API berhasil", fg=GREEN)
                    messagebox.showinfo("Koneksi berhasil", f"{event[1][0]} merespons:\n{event[1][1]}")
                elif kind == "test_error":
                    self.status_label.configure(text="Uji API gagal", fg=RED)
                    messagebox.showerror("Koneksi gagal", event[1])
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)

    def _check_ollama(self):
        installed, err = get_installed_models()
        self.installed_models = installed
        if err:
            self.events.put(("status", "Ollama belum terhubung"))
            return
        available = [m for m in (GEMMA_MODEL, LIGHT_MODEL, CODING_MODEL)
                     if model_is_installed(m, installed)]
        self.events.put(("status", f"Ollama siap • {len(available)}/3 model tersedia"))

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Pilih file untuk dijadikan konteks",
            filetypes=[
                ("File teks dan kode", "*.txt *.py *.md *.html *.css *.js *.json *.csv *.xml *.yaml *.yml *.ini *.log"),
                ("Semua file", "*.*")
            ]
        )
        if not path:
            return
        try:
            p = Path(path)
            self.current_file_context = p.read_text(encoding="utf-8", errors="replace")[:20000]
            self.current_file_name = p.name
            self.file_label.configure(text=f"Konteks file: {p.name}", fg=CYAN)
            self._append("system", f"File dimuat sebagai konteks: {p.name}")
        except Exception as exc:
            messagebox.showerror("Gagal membaca file", str(exc))

    def _clear_file_context(self):
        self.current_file_context = ""
        self.current_file_name = ""
        self.file_label.configure(text="Konteks file: tidak ada", fg=MUTED)
        self._append("system", "Konteks file dibersihkan.")

    def _save_code(self):
        text = self.chat_text.get("1.0", "end")
        code = extract_code(text)
        if not code:
            messagebox.showinfo("Simpan kode", "Belum ditemukan blok kode ```python ... ``` pada percakapan.")
            return
        suggested = f"nexora_code_{datetime.now():%Y%m%d_%H%M%S}.py"
        path = filedialog.asksaveasfilename(
            title="Simpan kode Python", initialdir=str(APP_OUTPUT_DIR),
            initialfile=suggested, defaultextension=".py",
            filetypes=[("Python", "*.py"), ("Semua file", "*.*")]
        )
        if not path:
            return
        try:
            Path(path).write_text(code + "\n", encoding="utf-8")
            messagebox.showinfo("Berhasil", f"Kode disimpan:\n{path}")
        except Exception as exc:
            messagebox.showerror("Gagal menyimpan", str(exc))

    def _project_prompt(self):
        prompt = self.input_text.get("1.0", "end").strip()
        if not prompt:
            prompt = "Buat aplikasi sederhana"
        self.mode_var.set("Proyek")
        self.model_var.set("Otomatis")
        if not prompt.lower().startswith("buat"):
            prompt = "Buat proyek aplikasi lengkap berdasarkan permintaan ini: " + prompt
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", prompt)
        self._send()

    def _open_output_folder(self):
        try:
            os.startfile(str(APP_OUTPUT_DIR))
        except Exception as exc:
            messagebox.showerror("Folder", str(exc))

    def _toggle_voice(self):
        self.voice_enabled = not self.voice_enabled
        # Tombol dibuat ulang secara visual sederhana lewat status label.
        self.status_label.configure(
            text=("Suara aktif" if self.voice_enabled else "Suara nonaktif"),
            fg=GREEN if self.voice_enabled else MUTED
        )
        if self.voice_enabled:
            messagebox.showinfo(
                "Suara NEXORA",
                "Fitur suara menggunakan pyttsx3 jika sudah terpasang.\n"
                "Jika belum, jalankan: python -m pip install pyttsx3"
            )

    def _speak(self, text):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(text[:2500])
            engine.runAndWait()
            engine.stop()
        except Exception as exc:
            self.events.put(("status", f"Suara tidak tersedia: {exc}"))

def main():
    root = tk.Tk()
    app = NexoraApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
