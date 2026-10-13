# The churvey command

`churvey` drives the Firefox extension in `ff/` from a terminal. It installs with
`uv tool install git+https://github.com/danieldager/churvey` and needs only Python 3.9+ and Firefox.

## Where things live

Everything is in `~/.churvey/` (set `CHURVEY_HOME` to move it):

| Path | What |
|---|---|
| `profile/` | The Firefox profile churvey uses. Your sign-ins live here, never in your usual Firefox profile. |
| `config.json` | The chatbots you set up, and a history of setup / login sessions with their test results. |
| `questions/<name>.json` | Your question sets ([format](questions.md)). |
| `runs/<set>_<date>_<time>/` | One folder per run (below). |

None of this belongs in a git repository: the profile holds your cookies.

## Commands

| Command | What it does |
|---|---|
| `churvey setup [--chatbots a,b]` | Checks Firefox is installed, creates the profile, opens Firefox with a checklist page. Sign in to each chatbot there; the page shows each one turn from "Not signed in" to "Signed in". "Run the test" sends one short question to every signed-in chatbot; "Done" saves the ones that answered. |
| `churvey login [chatbot ...]` | The same page for just those chatbots, to sign in again. |
| `churvey doctor [--chatbots a,b] [--visible]` | One short question to each chatbot, no window. Prints `ok`, `logged_out`, `rate_limited`, `challenge` or `capture_failed` per chatbot and the command that fixes it. |
| `churvey run <set> [--chatbots a,b] [--repeat N] [--visible]` | Asks every question of the set (a saved name or any file) to each chatbot, N times. No window unless `--visible`. One line per answer as it lands. |
| `churvey status` / `pause <chatbot>` / `resume <chatbot>` / `reload <chatbot>` / `stop` | Control a run that is going on, from another terminal. |
| `churvey export <run> [--out FILE]` | Writes `responses.clean.jsonl`, one row per answer (below). `<run>` is a folder name in `runs/`, `latest`, or a path. |
| `churvey questions ...` | `new`, `list`, `show`, `add`, `edit`, `rm`, `import`, `export`, `validate`, `ui`. See [questions.md](questions.md). |

Chatbot names: `chatgpt`, `claude`, `gemini`, `mistral` (Le Chat; `lechat` also works), `grok`.

When a chatbot is blocked during a run, churvey stops asking it, finishes the others and says why:

```
  Claude is not signed in.
  churvey login claude
  Le Chat hit its message limit. « Messages limit reached ... »
  Wait for the limit to reset, then run again with --chatbots mistral
```

Exit codes: `run` 0 everything answered, 3 finished with a chatbot blocked, 1 did not finish; `doctor` 0 only if every chatbot answered.

## A run folder

| File | What |
|---|---|
| `questions.json` | An exact copy of the question set at the time of the run. Editing the set later never changes past runs. |
| `churvey-run.json` | Set name and `question_set_sha256` (hash of that copy), chatbots, repeat, private, headless, start and end time, exit code, blocked chatbots. |
| `run-plan.json` | What the extension was given. |
| `run_<time>.jsonl` | The extension's raw records (schema v6). |
| `run_<time>.run.json`, `.summary.txt`, `.raw-completions.json` | Run manifest with the extension log, a summary, the raw network streams (for re-parsing citations). |
| `responses.clean.jsonl` | Written by `churvey export`. |

`responses.clean.jsonl` has the fields the claim pipeline reads (same as llm_bench `dashboard/ingest/normalise_run.py`):
`question_id`, `question_user_fr` (the question as asked), `provider`, `model_label_if_visible`, `response_text`,
`citations` (displayed citations with url, title, cited text and the answer span they support), `displayed_urls`,
`fetched_urls`, `citation_extraction`, `searched`, `captured_at`, `capture_method` (`stream` | `poll` | `dom_fallback`),
`status`, `error`; plus `run_id`, `rep_index`, `item_key`, `group` and `question_set` {name, sha256}.

## The setup page

`churvey setup` serves the page on `127.0.0.1:8741-8749` (the extension looks for run plans on 8731-8735, so the two
never meet) and starts Firefox with its debugger port on the page port + 100. A worker attaches to the extension's
background page through that port and, every 2 seconds, for each chatbot tab:

1. injects a small sign-in check (`tabs.executeScript`, fresh on every poll, so a page that changed route without
   reloading is still read): ChatGPT `/api/auth/session` has a user, Claude `/api/organizations` lists an organisation;
   for the others, a visible "Sign in" / "Log in" / "Sign up" / "Se connecter" control means signed out;
2. asks the extension's own page check (`PAGE_STATUS`) for a message-limit banner or a captcha.

"Re-check" on a row polls at once. "Open site" asks the extension to open the chatbot or switch to its tab.
All page text is in `churvey/web/strings.json` under `en`; a French block can be added next to it (`?lang=fr`).

## Checks without a browser

```
uv run python -m unittest discover -s tests       # question sets, export, argument parsing
uv build                                          # the wheel bundles ff/, the schema and the pages
```

CI (`.github/workflows/ci.yml`) also runs `node --check` on every script. There is no node on Daniel's machine;
the same check runs there with macOS JavaScriptCore:
`/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc -e 'checkSyntax("file.js")'`.
