## ADDED Requirements

### Requirement: Stored PDFs stay out of git
The vault `.gitignore` written by `wiki init`, and brought to existing vaults by `wiki upgrade`, SHALL ignore `raw/.orig/*.pdf`, so that captured PDF originals stay on the machine that captured them while their extracted raw files are committed. Other files under `raw/.orig/` SHALL NOT be ignored.

#### Scenario: Fresh vault
- **WHEN** a PDF is captured in a vault created by `wiki init` and the human commits with `git add -A`
- **THEN** the raw `.md` file is committed and the PDF under `raw/.orig/` is not

#### Scenario: Stored HTML still committed
- **WHEN** a web page is captured in the same vault
- **THEN** its `.html` original under `raw/.orig/` is not ignored by git

#### Scenario: Existing vault
- **WHEN** `wiki upgrade` runs on a vault whose `.gitignore` is an untouched earlier template
- **THEN** `.gitignore` is updated to include `raw/.orig/*.pdf`

### Requirement: Schema covers PDF sources
The `AGENTS.md` schema SHALL list `.pdf` among the sources `wiki add-source` accepts, and state that only single-column PDFs with a text layer are supported and that stored PDFs are not committed. The ingest workflow SHALL:
- accept a PDF path;
- tell the agent, when capture fails with `multi_column` or `no_text_layer`, to stop and report to the human rather than extract the text another way;
- for a PDF raw file, have the agent ask the human for the publication date when the text does not state one;
- for a long raw file, have the agent read it section by section rather than in one pass, and use its references section to look up the works the text cites rather than summarising it.

#### Scenario: Schema mentions PDFs
- **WHEN** `AGENTS.md` is inspected after init or upgrade
- **THEN** it lists `.pdf` as an accepted source and states the single-column, text-layer limitation

#### Scenario: Ingest workflow guides long papers
- **WHEN** the ingest workflow text is inspected
- **THEN**:
  - it covers the `multi_column` and `no_text_layer` refusals;
  - it asks the human for a missing publication date of a PDF;
  - it describes reading long sources section by section and using the references only for lookups
