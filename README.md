# isabelle-connector

A Python library for processing Isabelle theories programmatically.  Build
and process theories in Python.

Built on top of [isabelle-client](https://github.com/inpefess/isabelle-client) and inspired by https://github.com/inpefess/isabelle-client/blob/master/isabelle_client/isabelle_connector.py


---

## Environment

You can use `isabelle-connector` on any platform with Python 3.12+ and Isabelle 2024+ installed. 
For example, on Ubuntu:

```bash
conda create -n isabelle python=3.12
conda activate isabelle
```
---

## Installation

```bash
pip install -r requirements.txt
```

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ISABELLE_HOME` | *(from PATH)* | Override the Isabelle installation path |
| `AFP_BASE` | *(from AFP)* | Base directory for AFP theories |

---

## Quick start

```python
from isabelle_connector import IsabelleConnector, TheoryOutcome
from isabelle_connector.utils import temp_theory

# Build a theory entirely in Python
thy = temp_theory(
    name="MyQuery",
    session="HOL",
    imports=["Main"],
    working_directory="/tmp/my-isabelle-work",
    queries=[r'ML\<open> val answer = 6 * 7 \<close>'],
)

# Process it through Isabelle
with IsabelleConnector() as isabelle:
    outcomes = isabelle.use_theories([thy])

outcome: TheoryOutcome = outcomes[thy]

if outcome.ok:
    print(outcome.values)   # [42]
else:
    print(outcome.errors)
```

`IsabelleConnector` starts its own Isabelle server subprocess on construction
and stops it when the context manager exits (or when `.close()` is called).

---

## Key concepts

### `Theory`

Represents a `.thy` file — either an existing file on disk or one constructed
in memory.  Use `temp_theory(**kwargs)` to build one in Python:

| Field | Description |
|---|---|
| `name` | Theory name (also the filename stem) |
| `session` | Isabelle session to start, e.g. `"HOL"`, `"HOL-IMP"` |
| `imports` | List of theories to import, e.g. `["Main"]`, `["HOL-IMP.Big_Step"]` |
| `working_directory` | Directory where the `.thy` file is written |
| `queries` | List of Isabelle commands / ML blocks forming the theory body |

Call `thy.to_theory_text()` to preview the exact text that will be written to
disk and sent to Isabelle.

### `TheoryOutcome`

The result of processing a single `Theory`:

| Member | Type | Description |
|---|---|---|
| `ok` | `bool` | `True` when there are no errors |
| `errors` | `list[str]` | Error messages from Isabelle |
| `output` | `list[str]` | All `writeln` output lines |
| `values` | `list[Any]` | ML `val` bindings parsed into Python objects |

### `IsabelleConnector`

The main entry point.  Notable constructor parameters:

| Parameter | Default | Description |
|---|---|---|
| `session_dirs` | `["$ISABELLE_HOME/src/HOL", "$AFP_BASE/thys"]` | Directories searched when starting sessions |
| `session_rotation_size` | `1000` | Start a fresh session every N theories to bound server-side state |
| `max_open_sessions` | `50` | Global cap on concurrently-open server sessions |
| `working_directory` | *(auto temp dir)* | Where server logs and temp files go |

---

## Examples

### `example/hol_imp_extraction.py`

Connects to a `HOL-IMP` session, builds a theory that imports
`HOL-IMP.Big_Step`, and runs three ML queries:

- list the constructors and types of the `com` datatype
- collect the first 15 theorem names in the `Big_Step` namespace
- look up the type of the `big_step` relation

```bash
python example/hol_imp_extraction.py
```

### `example/hol_imp_template_type_extraction.py`

A more complete extraction pipeline: iterates over every theory in `HOL-IMP`,
builds one temp theory per source theory, runs ML to extract lemma
propositions, abstract templates, and typed constants, then writes the results
to JSON.

```bash
python example/hol_imp_template_type_extraction.py --help
```

