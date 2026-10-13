"""JSON API behind the question editor page (churvey/web/questions.html). Sets are read and written in
~/.churvey/questions/ through churvey.questions, so the page and the CLI enforce the same rules."""

import json
import pathlib
import tempfile
from urllib.parse import unquote

from . import home, questions as Q
from .web import strings


def _name(path):
    return unquote(path.rsplit("/", 1)[-1])


def list_sets(path, body):
    out = []
    for p in Q.list_sets():
        try:
            qs = json.loads(p.read_text(encoding="utf-8"))
            out.append({"name": p.stem, "count": len(qs.get("questions", [])), "description": qs.get("description", "")})
        except ValueError:
            out.append({"name": p.stem, "count": None, "description": "(not valid JSON)"})
    return 200, out


def get_set(path, body):
    p = Q.set_path(_name(path))
    if not p.is_file():
        return 404, {"error": "no such set"}
    try:
        return 200, Q.load_saved(p)
    except Q.Invalid as e:
        return 400, {"errors": e.errors}


def put_set(path, body):
    """Save `body` as the set; it may be renamed (the old file is removed). 400 with the errors if invalid."""
    old = _name(path)
    errs, _ = Q.validate(Q.fill_ids(body) if isinstance(body, dict) else body)
    if errs:
        return 400, {"errors": errs}
    if body["name"] != old and Q.set_path(body["name"]).exists():
        return 400, {"errors": [f'a set named "{body["name"]}" already exists']}
    Q.save(body)
    if body["name"] != old and Q.set_path(old).exists():
        Q.set_path(old).unlink()
    return 200, body


def delete_set(path, body):
    p = Q.set_path(_name(path))
    if p.is_file():
        p.unlink()
    return 200, {"deleted": p.stem}


def new_set(path, body):
    name = Q.slugify((body or {}).get("name") or "new-set", 64)
    base, n = name, 2
    while Q.set_path(name).exists():
        name, n = f"{base}-{n}", n + 1
    qs = Q.new_set(name)
    Q.save(qs)
    return 200, qs


def import_file(path, body):
    """{filename, content} -> the parsed set (not saved: the page shows it and the user saves)."""
    fn = pathlib.Path((body or {}).get("filename") or "upload.txt").name
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / fn
        p.write_text((body or {}).get("content") or "", encoding="utf-8")
        try:
            return 200, Q.parse_file(p)
        except Q.Invalid as e:
            return 400, {"errors": e.errors}


def api():
    return {("GET", "/api/sets"): list_sets, ("GET", "/api/sets/"): get_set, ("PUT", "/api/sets/"): put_set,
            ("DELETE", "/api/sets/"): delete_set, ("POST", "/api/new"): new_set, ("POST", "/api/import"): import_file,
            ("GET", "/api/strings"): lambda p, b: (200, strings()),
            ("GET", "/api/chatbots"): lambda p, b: (200, [{"id": c, "label": home.LABELS[c]} for c in home.CHATBOTS])}
