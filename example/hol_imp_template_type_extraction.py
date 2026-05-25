#!/usr/bin/env python3
"""Extract theorem templates and typed constants for all HOL-IMP theories.

The script builds one temporary Isabelle theory per HOL-IMP source theory.  Each
generated theory imports the HOL-IMP source theory, loads the example extraction
ML support files, then emits a Python-parseable ML value containing:

  - source theory name
  - theorem/fact name
  - proposition text
  - non-built-in constants with the types used in the theorem
  - polymorphic abstract template text

Run from the repository root with a working Isabelle on PATH:

    python example/hol_imp_template_type_extraction.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from isabelle_connector.isabelle_connector import IsabelleConnector
from isabelle_connector.isabelle_types import Theory, TheoryOutcome
from isabelle_connector.logging_utils import configure_logging
from isabelle_connector.utils import path_to_theory_name, temp_theory

LOGGER = logger
SUPPORT_THEORY_DIR = Path(__file__).resolve().parent / "isabelle-thys"
DEFAULT_WORKING_DIR = Path("/tmp/isabelle-connector-hol-imp-template-types")
SUPPORT_ML_COMMANDS = [
    'ML_file "RoughSpecUtils.ML"',
    'ML_file "AbstractLemma.ML"',
]


def ml_raw_string_literal(text: str) -> str:
    """Return an Isabelle/ML string literal for arbitrary text."""
    escaped_chars: list[str] = []
    for char in text:
        if char == "\\":
            escaped_chars.append("\\092")
        elif char == '"':
            escaped_chars.append('\\"')
        elif char == "\n":
            escaped_chars.append("\\n")
        elif char == "\t":
            escaped_chars.append("\\t")
        elif char == "\r":
            escaped_chars.append("\\r")
        else:
            escaped_chars.append(char)
    return '"' + "".join(escaped_chars) + '"'


def isabelle_home() -> Path:
    """Find ``ISABELLE_HOME`` from the environment or ``isabelle getenv``."""
    if env_home := os.environ.get("ISABELLE_HOME"):
        return Path(env_home)

    if shutil.which("isabelle") is None:
        raise RuntimeError("Could not find Isabelle: set ISABELLE_HOME or put isabelle on PATH")

    output = subprocess.check_output(
        ["isabelle", "getenv", "-b", "ISABELLE_HOME"],
        text=True,
    ).strip()
    if not output:
        raise RuntimeError("Isabelle did not report ISABELLE_HOME")
    return Path(output)


def default_hol_imp_dir() -> Path:
    return isabelle_home() / "src" / "HOL" / "IMP"


def copy_support_theories(working_dir: Path) -> None:
    """Copy example Isabelle/ML support files next to generated theories."""
    working_dir.mkdir(parents=True, exist_ok=True)
    for src in SUPPORT_THEORY_DIR.iterdir():
        if src.is_file():
            shutil.copy2(src, working_dir / src.name)


def discover_hol_imp_theories(
    hol_imp_dir: Path,
    *,
    only: list[str] | None = None,
    limit: int | None = None,
) -> list[Theory]:
    names = sorted(path.stem for path in hol_imp_dir.glob("*.thy"))
    if only:
        requested = set(only)
        names = [name for name in names if name in requested]
        missing = sorted(requested.difference(names))
        if missing:
            raise ValueError(f"Unknown HOL-IMP theories: {', '.join(missing)}")
    if limit is not None:
        names = names[:limit]

    return [
        Theory(
            name=name,
            session="HOL-IMP",
            working_directory=str(hol_imp_dir),
            is_temp=False,
        )
        for name in names
    ]


def template_type_extraction_theory(src_thy: Theory, working_dir: Path) -> Theory:
    """Build a temp theory that extracts templates and typed symbols."""
    base_name = src_thy.name.rsplit("/", 1)[-1]
    import_name = f"{src_thy.session}.{base_name}"
    query = f"""
val result =
  let
    val ctxt = @{{context}}

    fun term_string term =
      Print_Mode.setmp [] (Syntax.string_of_term ctxt) term

    fun typ_string typ =
      Print_Mode.setmp [] (Syntax.string_of_typ ctxt) typ

    fun used_consts term =
      let
        val abbrev_term = hd (Proof_Context.standard_term_uncheck ctxt [term])
      in
        Term.add_consts abbrev_term []
        |> filter (fn (name, _) => not (RoughSpec_Utils.is_keep_const name))
        |> map (fn (name, typ) => (name, typ_string typ))
      end

    fun has_vars term =
      (case term of
        Var _ => true
      | Abs (_, _, body) => has_vars body
      | left $ right => has_vars left orelse has_vars right
      | _ => false)

    fun source_fact (fact_name, thm) =
      String.isPrefix ({ml_raw_string_literal(base_name)} ^ ".") fact_name
      andalso has_vars (Thm.prop_of thm)

    fun extract_one (fact_name, thm) =
      let
        val prop = Thm.prop_of thm
        val template = AbstractLemma.abstract_term_poly ctxt prop
      in
        (fact_name, term_string prop, used_consts prop, term_string template)
      end

    val thms =
      Global_Theory.all_thms_of (Proof_Context.theory_of ctxt) true
      |> filter source_fact
  in
    ({ml_raw_string_literal(src_thy.name)}, map extract_one thms)
  end
"""
    thy = temp_theory(
        name=f"Template_Types_{path_to_theory_name(src_thy.name)}",
        session=src_thy.session,
        imports=[import_name],
        queries=list(SUPPORT_ML_COMMANDS),
        working_directory=str(working_dir),
    )
    thy.add_ml_block(query)
    return thy


def outcome_records(outcome: TheoryOutcome) -> list[dict[str, Any]]:
    if outcome.value is None:
        return []

    source_theory, rows = outcome.value
    records = []
    for fact_name, proposition, typed_consts, template in rows:
        records.append(
            {
                "theory": source_theory,
                "fact": fact_name,
                "proposition": proposition,
                "typed_constants": [
                    {"name": const_name, "type": const_type}
                    for const_name, const_type in typed_consts
                ],
                "template": template,
            }
        )
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=DEFAULT_WORKING_DIR,
        help="Directory for generated theories, support files, logs, and default output.",
    )
    parser.add_argument(
        "--hol-imp-dir",
        type=Path,
        default=None,
        help="Path to Isabelle's src/HOL/IMP directory. Defaults to ISABELLE_HOME/src/HOL/IMP.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSONL output path. Defaults to WORKING_DIR/hol_imp_template_types.jsonl.",
    )
    parser.add_argument(
        "--theories",
        nargs="+",
        default=None,
        help="Optional subset of HOL-IMP theory basenames, e.g. AExp Big_Step.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N theories.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Generated theories per Isabelle use_theories call. Values >1 run serially.",
    )
    parser.add_argument("--recache", action="store_true", help="Ignore existing cached results.")
    parser.add_argument(
        "--keep-theories",
        action="store_true",
        help="Keep generated .thy files after processing.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(level="WARNING", enable_package_logs=False)

    working_dir = args.working_dir.resolve()
    output_path = (
        args.output.resolve()
        if args.output is not None
        else working_dir / "hol_imp_template_types.jsonl"
    )
    hol_imp_dir = (args.hol_imp_dir or default_hol_imp_dir()).resolve()
    if not hol_imp_dir.is_dir():
        raise FileNotFoundError(f"HOL-IMP directory does not exist: {hol_imp_dir}")

    copy_support_theories(working_dir)
    source_theories = discover_hol_imp_theories(
        hol_imp_dir,
        only=args.theories,
        limit=args.limit,
    )
    extraction_theories = [
        template_type_extraction_theory(src_thy, working_dir) for src_thy in source_theories
    ]

    LOGGER.info("Extracting {} HOL-IMP theories", len(extraction_theories))
    with IsabelleConnector(
        name="hol-imp-template-types",
        working_directory=str(working_dir),
        session_dirs=["$ISABELLE_HOME/src/HOL"],
    ) as isabelle:
        outcomes = isabelle.use_theories(
            extraction_theories,
            batch_size=args.batch_size,
            rm_after=not args.keep_theories,
            recache=args.recache,
        )

    records: list[dict[str, Any]] = []
    failed = []
    for thy in extraction_theories:
        outcome = outcomes[thy]
        if outcome.errors:
            failed.append((thy.name, outcome.errors))
            continue
        records.extend(outcome_records(outcome))

    write_jsonl(output_path, records)
    LOGGER.info("Wrote {} theorem records to {}", len(records), output_path)

    if failed:
        print("\nFailed extraction theories:")
        for theory_name, errors in failed:
            print(f"- {theory_name}")
            for error in errors:
                print(f"  {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
