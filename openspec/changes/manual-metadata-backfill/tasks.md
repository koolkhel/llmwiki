## 1. Templates

- [x] 1.1 Update `vault/AGENTS.md` (the Authors and Chronology rule per D1, Timeline "undated"), `workflows/ingest.md` (copy or leave empty and tell the human, per D2), and `workflows/lint.md` (the report-only metadata check, per D3). Verify with `grep` that "look for a byline", "look for a date in the text" and "check the text for a byline" no longer appear in any template.
- [x] 1.2 Re-run `scripts/known_hashes.py` and update tests: the existing author and chronology template tests change to the new wording, and new tests cover the delta scenarios (no guessing of authors or dates; lint is report-only, with no instruction to set `published` or add authors). Verify that the full suite passes, including the registry-completeness and agent-neutral naming tests.

## 2. Docs and delivery

- [x] 2.1 README: describe manual metadata verification (what `wiki source-meta --all` and the `missing_*` warnings are for). In a scratch vault, `wiki upgrade` from the previous template version reports `AGENTS.md` and the ingest/lint workflows as updated. Commit, push, and confirm CI passes.
