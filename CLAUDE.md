# CLAUDE.md

## Question sets (churvey)

Question sets are plain JSON files in `~/.churvey/questions/<name>.json` (or `$CHURVEY_HOME/questions/`), format
`churvey/questions@1`, schema in `schema/questions.schema.json`, guide in `docs/questions.md`.

When asked to create or change a question set:

- Edit the JSON file directly, or use `churvey questions add / rm / import`.
- Always run `churvey questions validate <name>` after editing, and fix every error it reports.
- Keep existing `id`s unchanged; runs and exports join on them. New questions may omit `id` (generated from the text).
- `text` is exactly what is typed into the chatbot. Anything else (answer key, premise_true / premise_false, source,
  notes) goes in `meta`; no other question fields are allowed.
- Use `group` to tie together questions that belong to one item (e.g. the open and false-premise forms).
- Do not edit run folders under `~/.churvey/runs/`: they hold frozen copies of the sets they used.
