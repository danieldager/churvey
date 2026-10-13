"""The churvey data directory (~/.churvey, or $CHURVEY_HOME) and the chatbot list."""

import json
import os
import pathlib

CHATBOTS = ["chatgpt", "claude", "gemini", "mistral", "grok"]   # ids the extension knows (ff/src/shared/providers.js)
LABELS = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini", "mistral": "Le Chat", "grok": "Grok"}
SITES = {"chatgpt": "https://chatgpt.com/", "claude": "https://claude.ai/new", "gemini": "https://gemini.google.com/app",
         "mistral": "https://chat.mistral.ai/chat", "grok": "https://grok.com/"}
ALIASES = {"lechat": "mistral", "le-chat": "mistral", "le_chat": "mistral", "openai": "chatgpt", "anthropic": "claude",
           "google": "gemini", "bard": "gemini", "xai": "grok"}


def root():
    return pathlib.Path(os.environ.get("CHURVEY_HOME") or pathlib.Path.home() / ".churvey").expanduser()


def profile_dir():
    return root() / "profile"


def questions_dir():
    return root() / "questions"


def runs_dir():
    return root() / "runs"


def config_path():
    return root() / "config.json"


def ensure():
    for d in (root(), profile_dir(), questions_dir(), runs_dir()):
        d.mkdir(parents=True, exist_ok=True)


def load_config():
    p = config_path()
    return json.loads(p.read_text()) if p.is_file() else {}


def save_config(cfg):
    ensure()
    config_path().write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


def chatbot_id(name):
    """Canonical id for a user-typed chatbot name; SystemExit with the valid names if unknown."""
    k = name.strip().lower()
    k = ALIASES.get(k, k)
    if k not in CHATBOTS:
        raise SystemExit(f"unknown chatbot '{name}'. Choose from: {', '.join(CHATBOTS)} (Le Chat is 'mistral')")
    return k


def parse_chatbots(text):
    """'a,b' -> canonical ids, order kept, duplicates dropped. Empty -> []."""
    out = []
    for part in (text or "").split(","):
        if part.strip():
            k = chatbot_id(part)
            if k not in out:
                out.append(k)
    return out
