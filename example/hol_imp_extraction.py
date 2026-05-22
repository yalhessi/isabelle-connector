#!/usr/bin/env python3
"""
Example: inspect and extract data from HOL-IMP using isabelle-connector.

HOL-IMP is a simple imperative language formalised in Isabelle/HOL.
It ships with every Isabelle installation (src/HOL/IMP/).

This example shows:
  - building temporary theories in Python
  - embedding ML queries to inspect the proof context
  - reading structured results from TheoryOutcome

Run with:
    python example/hol_imp_extraction.py
"""

import logging

from isabelle_connector import IsabelleConnector, Theory, TheoryOutcome
from isabelle_connector.utils import temp_theory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ---------------------------------------------------------------------------
# Theory content: three ML blocks, each producing a `val` that we can read
# ---------------------------------------------------------------------------

# 1. List the constructors of the `com` datatype (the IMP command language).
QUERY_CONSTRUCTORS = r"""
ML\<open>
val result_constructors =
  let
    fun type_string typ =
      Print_Mode.setmp [] (Syntax.string_of_typ @{context}) typ

    fun render_const c =
      (Long_Name.base_name c, type_string (Sign.the_const_type @{theory} c))
  in
    map render_const [
      @{const_name SKIP},
      @{const_name Assign},
      @{const_name Seq},
      @{const_name If},
      @{const_name While}
    ]
  end
\<close>
"""

# 2. Extract the names of theorems in the Big_Step theory.
QUERY_THEOREMS = r"""
ML\<open>
val result_theorems =
  Global_Theory.all_thms_of (Proof_Context.theory_of @{context}) true
  |> map_filter (fn (name, _) =>
       if String.isPrefix "Big_Step." name then SOME name else NONE)
  |> take 15
\<close>
"""

# 3. Look up the type of the big_step relation.
QUERY_TYPE = r"""
ML\<open>
val result_type =
  let
    val thy = @{theory}
    val ctxt = Proof_Context.init_global thy
  in
    Sign.the_const_type thy @{const_name big_step}
    |> Print_Mode.setmp [] (Syntax.string_of_typ ctxt)
  end
\<close>
"""


def build_theory(working_directory: str) -> Theory:
    """Assemble a temp theory that imports HOL-IMP and runs all queries."""
    return temp_theory(
        name="IMP_Extraction",
        # The Isabelle server session to use: HOL-IMP extends HOL with the IMP
        # theories.  The server will load it (and its HOL dependency) on demand.
        session="HOL-IMP",
        # Logical theory imports within that session.
        imports=["HOL-IMP.Big_Step"],
        queries=[
            QUERY_CONSTRUCTORS,
            QUERY_THEOREMS,
            QUERY_TYPE,
        ],
        working_directory=working_directory,
    )


def print_outcome(outcome: TheoryOutcome) -> None:
    if not outcome.ok:
        print("=== Errors ===")
        for err in outcome.errors:
            print(f"  {err}")
        return

    print("=== Raw ML output ===")
    for line in outcome.output:
        print(f"  {line}")

    print("\n=== Parsed ML values (Python objects) ===")
    for val in outcome.values:
        print(f"  {val!r}")


def main() -> None:
    working_dir = "/tmp/isabelle-connector-example"

    with IsabelleConnector(
        name="imp-example",
        working_directory=working_dir,
    ) as isabelle:
        thy = build_theory(working_dir)

        print(f"Theory file that will be sent to Isabelle:\n{'=' * 60}")
        print(thy.to_theory_text())
        print("=" * 60 + "\n")

        outcomes: dict[Theory, TheoryOutcome] = isabelle.use_theories(
            [thy],
            rm_after=True,
            use_cache=False,
        )

        outcome = outcomes[thy]
        print_outcome(outcome)


if __name__ == "__main__":
    main()
