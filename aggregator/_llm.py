"""Minimal DeepInfra chat helper — reuses the grader's plumbing/key.

Same model + endpoint + .env as analysis/validate_grader.py, kept self-contained
so aggregator/ has no cross-dir import. Non-reasoning, JSON-friendly.
"""
import json
import re
import ssl
import urllib.request

ENV = "/Users/daniel.dager/dev/disinform/factchecking_with_LLMs/src/.env"
MODEL = "deepseek-ai/DeepSeek-V4-Flash"
URL = "https://api.deepinfra.com/v1/openai/chat/completions"
SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")


def _key():
    with open(ENV) as f:
        for ln in f:
            m = re.match(r"DEEPINFRA_API_KEY\s*=\s*(\S+)", ln)
            if m:
                return m.group(1)
    raise SystemExit("DEEPINFRA_API_KEY not found in " + ENV)


def chat(system, user, temperature=0.0):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]
