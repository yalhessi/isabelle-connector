from isabelle_connector.isabelle_theory import Theory
from isabelle_connector.isabelle_utils import temp_theory


def transitions_theory(thy: Theory, configs) -> Theory:
    """
    Get theorems from a theory.

    :param theory_name: name of the theory
    :returns: theorems from the theory
    """
    query = f"""
            let
                val filename = "{thy.working_directory}/{thy.name}.thy"
                val stream = TextIO.openIn filename
                val content = TextIO.inputAll stream
                val theory = @{{theory}}
                val transitions = Extract.parse_text theory content
                val results = map (fn (trans, string) => (Toplevel.name_of trans, string)) transitions;
            in
                ("{thy.name}", results)
            end"""

    thy = temp_theory(
        name=f"Transitions_{thy.name.replace('/', '_').replace('-', '_')}",
        imports=configs.imports,
        working_directory=configs.root_dir,
    )
    thy.add_ml_block(query)
    return thy
