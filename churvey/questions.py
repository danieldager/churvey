"""Question sets: the `churvey/questions@1` format, importers, validation, hashing, and the ff/ run plan.

A set is one JSON file (schema/questions.schema.json):

    {"schema": "churvey/questions@1", "name": "pilot20", "description": "...", "language": "fr",
     "defaults": {"chatbots": ["chatgpt", ...], "repeat": 1, "private": true},
     "questions": [{"id": "slug", "text": "...", "tags": ["..."], "group": "...", "meta": {...}}]}

Only `text` is required per question; ids are stable slugs, generated from the text when missing.
"""

import csv
import hashlib
import io
import json
import pathlib
import re
import unicodedata

from . import home

SCHEMA = "churvey/questions@1"
TOP_KEYS = {"schema", "name", "description", "language", "defaults", "questions"}
DEFAULT_KEYS = {"chatbots", "repeat", "private"}
Q_KEYS = {"id", "text", "tags", "group", "meta"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
PLAN_PASSTHROUGH = ("followup_of", "attachments")   # meta keys the extension acts on


class Invalid(Exception):
    """A set that fails validation; .errors is a list of human-readable lines."""

    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


def slugify(text, maxlen=48):
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = s[:maxlen].rstrip("-")
    return s or "q"


def new_set(name, description="", language=None, questions=None, defaults=None):
    qs = {"schema": SCHEMA, "name": slugify(name, 64), "description": description}
    if language:
        qs["language"] = language
    qs["defaults"] = defaults or {"chatbots": list(home.CHATBOTS), "repeat": 1, "private": True}
    qs["questions"] = questions or []
    return fill_ids(qs)


def fill_ids(qs):
    """Give every question without an id a slug of its text, unique within the set. Existing ids never change."""
    taken = {q.get("id") for q in qs.get("questions", []) if isinstance(q, dict) and q.get("id")}
    for q in qs.get("questions", []):
        if isinstance(q, dict) and not q.get("id") and isinstance(q.get("text"), str):
            base = slugify(q["text"])
            qid, n = base, 2
            while qid in taken:
                qid, n = f"{base}-{n}", n + 1
            q["id"] = qid
            taken.add(qid)
    return qs


# --- validation ----------------------------------------------------------------------------------------------

def question_lines(text):
    """Line number (1-based) where each object of the top-level "questions" array starts, by scanning the raw JSON."""
    m = re.search(r'"questions"\s*:\s*\[', text)
    if not m:
        return []
    out, depth, i, in_str = [], 0, m.end(), False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "{[":
            if depth == 0 and c == "{":
                out.append(text.count("\n", 0, i) + 1)
            depth += 1
        elif c in "}]":
            if depth == 0:
                break
            depth -= 1
        i += 1
    return out


def validate(qs, source_text=None):
    """(errors, warnings) for a parsed set. `source_text` (the file) adds line hints."""
    errs, warns = [], []
    lines = question_lines(source_text) if source_text else []
    if not isinstance(qs, dict):
        return ["the file must be a JSON object { ... }"], warns
    if qs.get("schema") != SCHEMA:
        errs.append(f'"schema" must be "{SCHEMA}" (found {json.dumps(qs.get("schema"))})')
    for k in sorted(set(qs) - TOP_KEYS):
        errs.append(f'unknown top-level field "{k}" (allowed: {", ".join(sorted(TOP_KEYS))})')
    name = qs.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errs.append(f'"name" must be a short lowercase slug like "my-questions" (found {json.dumps(name)})')
    for k in ("description", "language"):
        if k in qs and not isinstance(qs[k], str):
            errs.append(f'"{k}" must be a string')
    d = qs.get("defaults", {})
    if not isinstance(d, dict):
        errs.append('"defaults" must be an object')
    else:
        for k in sorted(set(d) - DEFAULT_KEYS):
            errs.append(f'unknown field "defaults.{k}" (allowed: {", ".join(sorted(DEFAULT_KEYS))})')
        cb = d.get("chatbots", [])
        if not isinstance(cb, list) or any(c not in home.CHATBOTS for c in cb):
            errs.append(f'"defaults.chatbots" must be a list drawn from {home.CHATBOTS} (found {json.dumps(cb)})')
        r = d.get("repeat", 1)
        if not isinstance(r, int) or isinstance(r, bool) or r < 1:
            errs.append(f'"defaults.repeat" must be a whole number >= 1 (found {json.dumps(r)})')
        if not isinstance(d.get("private", True), bool):
            errs.append('"defaults.private" must be true or false')
    qlist = qs.get("questions")
    if not isinstance(qlist, list):
        errs.append('"questions" must be a list')
        return errs, warns
    if not qlist:
        warns.append("no questions yet")
    seen = {}
    for i, q in enumerate(qlist):
        where = f"question {i + 1}" + (f" (line {lines[i]})" if i < len(lines) else "")
        if not isinstance(q, dict):
            errs.append(f"{where}: must be an object {{\"text\": ...}}")
            continue
        for k in sorted(set(q) - Q_KEYS):
            errs.append(f'{where}: unknown field "{k}" (put extra data in "meta")')
        t = q.get("text")
        if not isinstance(t, str) or not t.strip():
            errs.append(f'{where}: "text" is required and must be a non-empty string')
        qid = q.get("id")
        if qid is None:
            warns.append(f"{where}: no id; one will be generated from the text")
        elif not isinstance(qid, str) or not ID_RE.match(qid):
            errs.append(f'{where}: id {json.dumps(qid)} must be lowercase letters, digits, "-", "_" or "." (max 80)')
        elif qid in seen:
            errs.append(f'{where}: duplicate id "{qid}" (also question {seen[qid] + 1})')
        else:
            seen[qid] = i
        tags = q.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
            errs.append(f'{where}: "tags" must be a list of strings')
        if "group" in q and not isinstance(q["group"], str):
            errs.append(f'{where}: "group" must be a string')
        if "meta" in q and not isinstance(q["meta"], dict):
            errs.append(f'{where}: "meta" must be an object {{...}}')
    return errs, warns


def checked(qs, source_text=None):
    """Fill ids, validate, raise Invalid on errors; return the set."""
    errs, _ = validate(fill_ids(qs) if isinstance(qs, dict) else qs, source_text)
    if errs:
        raise Invalid(errs)
    return qs


def content_hash(qs):
    """sha256 of the canonical JSON (sorted keys, no whitespace): the set's identity in a run."""
    b = json.dumps(qs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(b).hexdigest()


# --- import --------------------------------------------------------------------------------------------------

def from_txt(text, name):
    qs = [{"text": ln.strip()} for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return new_set(name, questions=qs)


def from_csv(text, name):
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return new_set(name)
    head = [c.strip().lower() for c in rows[0]]
    if "text" in head:
        cols, rows = head, rows[1:]
    else:
        cols = ["text"] if len(rows[0]) == 1 else ["id", "text", "tags", "group"][:len(rows[0])]
    qs = []
    for r in rows:
        rec = dict(zip(cols, (c.strip() for c in r)))
        q = {"text": rec.get("text", "")}
        if rec.get("id"):
            q["id"] = rec["id"]
        if rec.get("tags"):
            q["tags"] = [x.strip() for x in re.split(r"[;|]", rec["tags"]) if x.strip()]
        if rec.get("group"):
            q["group"] = rec["group"]
        extra = {k: v for k, v in rec.items() if k not in Q_KEYS and k and v}
        if extra:
            q["meta"] = extra
        qs.append(q)
    return new_set(name, questions=qs)


def from_run_plan(plan, name):
    """An ff/ run plan ({"providers", "questions", "repetitions", "config"}): unknown question keys go to meta."""
    qs = []
    for q in plan.get("questions", []):
        out = {k: q[k] for k in ("id", "text", "tags", "group") if k in q}
        meta = {k: v for k, v in q.items() if k not in Q_KEYS}
        if meta:
            out["meta"] = meta
        qs.append(out)
    chatbots = [p for p in plan.get("providers", []) if p in home.CHATBOTS] or list(home.CHATBOTS)
    private = (plan.get("config") or {}).get("private", True)
    return new_set(name, questions=qs, defaults={"chatbots": chatbots, "repeat": max(1, int(plan.get("repetitions") or 1)), "private": bool(private)})


def parse_file(path, name=None):
    """Any supported file -> a validated set. `name` defaults to the file stem."""
    path = pathlib.Path(path)
    text = path.read_text(encoding="utf-8-sig")
    stem = path.name.split(".")[0]
    name = name or stem
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return checked(from_txt(text, name))
    if suffix == ".csv":
        return checked(from_csv(text, name))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise Invalid([f"{path.name}: not valid JSON at line {e.lineno}, column {e.colno}: {e.msg}"])
    if isinstance(data, dict) and data.get("schema") == SCHEMA:
        if name != stem:
            data["name"] = slugify(name, 64)
        return checked(data, text)
    if isinstance(data, dict) and "questions" in data and "providers" in data:
        return checked(from_run_plan(data, name))
    raise Invalid([f'{path.name}: not a question set (needs "schema": "{SCHEMA}") nor an ff/ run plan'])


# --- storage -------------------------------------------------------------------------------------------------

def set_path(name):
    return home.questions_dir() / f"{name}.json"


def dump(qs):
    return json.dumps(qs, indent=2, ensure_ascii=False) + "\n"


def save(qs):
    checked(qs)
    home.ensure()
    p = set_path(qs["name"])
    p.write_text(dump(qs), encoding="utf-8")
    return p


def list_sets():
    d = home.questions_dir()
    return sorted(d.glob("*.json")) if d.is_dir() else []


def load(name_or_path):
    """A saved set by name, or any supported file by path. Returns (set, path)."""
    p = pathlib.Path(name_or_path).expanduser()
    if p.is_file():
        return parse_file(p), p
    sp = set_path(name_or_path)
    if sp.is_file():
        return load_saved(sp), sp
    names = ", ".join(x.stem for x in list_sets()) or "none yet"
    raise SystemExit(f"no question set '{name_or_path}' (saved sets: {names}). Import one: churvey questions import FILE")


def load_saved(p):
    text = p.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise Invalid([f"{p.name}: not valid JSON at line {e.lineno}, column {e.colno}: {e.msg}"])
    return checked(data, text)


# --- run plan ------------------------------------------------------------------------------------------------

ORDER_GAP = 3   # questions of one group are kept at least this many other questions apart, where the set allows


def spaced_order(questions, gap=ORDER_GAP):
    """The questions reordered so that two of the same `group` (e.g. an open question and its false-premise twin) are
    never asked back to back: at least `gap` other questions between them where the set allows. Greedy: at each step
    the eligible question whose group has the most questions left (so the tail does not crowd), ties in file order.
    A set with follow-ups (meta.followup_of) keeps its order, since a follow-up must come right after its parent."""
    if any("followup_of" in q.get("meta", {}) for q in questions):
        return list(questions)
    left, out = list(questions), []
    while left:
        recent = {q.get("group") for q in out[-gap:] if q.get("group")}
        todo = {}
        for q in left:
            if q.get("group"):
                todo[q["group"]] = todo.get(q["group"], 0) + 1
        ok = [q for q in left if not q.get("group") or q["group"] not in recent]
        if ok:
            pick = max(ok, key=lambda q: (todo.get(q.get("group"), 0), -left.index(q)))
        else:   # cannot keep the gap: the question whose group was asked longest ago
            last = {q.get("group"): i for i, q in enumerate(out)}
            pick = min(left, key=lambda q: (last.get(q.get("group"), -1), left.index(q)))
        left.remove(pick)
        out.append(pick)
    return out


def min_group_gap(questions):
    """Fewest other questions between two of the same group (None if no group repeats)."""
    seen, best = {}, None
    for i, q in enumerate(questions):
        g = q.get("group")
        if g in seen:
            best = i - seen[g] - 1 if best is None else min(best, i - seen[g] - 1)
        if g:
            seen[g] = i
    return best


def to_run_plan(qs, chatbots, repeat, private):
    questions = []
    for q in spaced_order(qs["questions"]):
        item = {"id": q["id"], "text": q["text"], "tags": list(q.get("tags", []))}
        if q.get("group"):
            item["group"] = q["group"]
        for k in PLAN_PASSTHROUGH:
            if k in q.get("meta", {}):
                item[k] = q["meta"][k]
        questions.append(item)
    return {"providers": list(chatbots), "questions": questions, "personas": [], "repetitions": int(repeat),
            "config": {"private": bool(private)}}
