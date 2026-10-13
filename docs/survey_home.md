# Survey home

churvey is the single home of the chatbot-survey code: the Firefox extension, its zero-click launcher and its remote control.

## Layout

| Path | What |
|---|---|
| `ff/` | The Firefox probe extension (latest, taken from llm_bench 2026-10-13). |
| `churvey/survey/launch_browser.py` | Serves a run plan on loopback, starts Firefox on a dedicated profile, installs `ff/` as a temporary add-on over the remote debugging protocol, waits for results. Stdlib only. |
| `churvey/survey/ffctl.py` | Remote control for the running extension (`status`, `log`, `pause`, `resume`, `reload`, `stop`, `eval`). Never launches Firefox. |
| `pyproject.toml` | Package `churvey`; the wheel bundles `ff/` as `churvey/survey/_ff`. |
| `src/`, `manifest.json` | Older Chrome extension. Unrelated to `ff/`, left as is. |

The extension directory is found as `$CHURVEY_FF`, else `<repo>/ff` (source or editable checkout), else the bundled `_ff` (installed wheel).

```
python -m churvey.survey.launch_browser --run-plan path/to/run-plan.json
python -m churvey.survey.ffctl status
```

The default profile is `cn-harvest` under `~/Library/Application Support/Firefox/Profiles/`; the launcher's managed `user.js` marker is unchanged, so existing profiles keep working.

## How llm_bench consumes it

llm_bench depends on churvey as an editable install, the same way it uses `dev/tools/deepinfra`:

```
uv add --editable ../churvey
```

`cn_bench/launch_browser.py` and `cn_bench/ffctl.py` become two-line shims that call `churvey.survey.*`, so `daily.py` (which locates the launcher with `Path(__file__).with_name`) and every documented command keep working. `ff/` in llm_bench is replaced by a symlink to `../churvey/ff`, which keeps `dashboard/ingest/reparse_raw.py` (reads `ff/src/background/citations.js`) unchanged. Switch only when no run is live.

## What is next

- W1: robust capture (DOM fallback, Claude endpoint fix, failure statuses, headless), developed in `ff/` here.
- W2b: an installable CLI (`uv tool install git+https://github.com/danieldager/churvey`) with entry points for the two modules.
- Checks available offline: syntax check of every extension script through macOS `jsc`, manifest script existence, importing both modules, building the wheel. No `node` or `web-ext` on this machine, and there are no unit tests yet beyond `test/injector-harness.html` (a browser page).
