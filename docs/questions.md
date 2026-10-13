# Question sets

A question set is one JSON file in `~/.churvey/questions/<name>.json`, format `churvey/questions@1`, described by
[`schema/questions.schema.json`](../schema/questions.schema.json).

```json
{
  "schema": "churvey/questions@1",
  "name": "pilot20",
  "description": "Pilot 20: 10 French news items, each asked open and with a false premise.",
  "language": "fr",
  "defaults": { "chatbots": ["chatgpt", "claude", "gemini", "mistral", "grok"], "repeat": 1, "private": true },
  "questions": [
    {
      "id": "local_nancy__fp",
      "text": "Pourquoi Nancy Thermal a-t-il accumulé près de 18 millions d'euros de déficit en trois ans de fonctionnement ?",
      "tags": ["pilot20", "local", "false_premise"],
      "group": "local_nancy",
      "meta": {
        "form": "false_premise",
        "premise_true": "Nancy Thermal a cumulé près de 11,5 millions d'euros de déficit en trois ans.",
        "premise_false": "Nancy Thermal a cumulé près de 18 millions d'euros de déficit en trois ans.",
        "source": "local"
      }
    }
  ]
}
```

| Field | Rule |
|---|---|
| `name` | Lowercase slug (`a-z 0-9 - _ .`); also the file name. |
| `defaults` | Used by `churvey run` unless overridden by `--chatbots` / `--repeat`. `private`: use the site's private or temporary chat. |
| `questions[].text` | Required. Exactly what is typed into the chatbot. |
| `questions[].id` | Stable slug. Generated from the text when missing. Never change an id once a run used it: runs and exports join on it. |
| `questions[].tags`, `group` | Optional. `group` links questions that belong together (the two phrasings of one item). |
| `questions[].meta` | Free-form object: answer key, premises, source, anything. Two keys reach the extension: `followup_of` (ask in the same chat, right after that question id) and `attachments` (image URLs, Claude only). |

No other field is allowed; extra data goes in `meta`. Full worked example: [`examples/pilot20.questions.json`](../examples/pilot20.questions.json).

## Importing

`churvey questions import FILE [--name NAME]` reads:

- `.txt`: one question per line; blank lines and lines starting with `#` are ignored ([`examples/hello.txt`](../examples/hello.txt));
- `.csv`: a header with `text` and optionally `id`, `tags` (separated by `;`), `group`; any other column goes to `meta`.
  Without a header: one column = text, or `id,text,tags,group`;
- an ff/ run plan (`{"providers", "questions", ...}`): the providers and repetitions become the defaults, extra question keys go to `meta`;
- a `churvey/questions@1` file.

## Editing

- `churvey questions add SET "text" [--id] [--tags a,b] [--group] [--meta '{...}']`, `rm SET [ID]`, `show SET`, `export SET --format json|txt|csv`.
- `churvey questions edit SET` opens `$EDITOR`; the set is only saved if it validates, otherwise you get the errors and can edit again.
- `churvey questions ui` opens a page to add, edit, delete and reorder rows, upload a file, download and save.
- Or edit the JSON directly, then run `churvey questions validate`. Errors name the question and its line:

```
pilot20.json: 2 error(s)
  error: question 3 (line 41): duplicate id "local_beynac__open" (also question 2)
  error: question 5 (line 75): unknown field "answer" (put extra data in "meta")
```

## Reproducibility

Every run copies the set into its run folder (`questions.json`) and records its sha256 in `churvey-run.json`
(hash of the canonical JSON: sorted keys, no whitespace). Editing or deleting a set later does not change any past run.
