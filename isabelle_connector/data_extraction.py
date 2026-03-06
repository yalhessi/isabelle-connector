from argparse import Namespace

from isabelle_connector.config import PROJ_ROOT
from isabelle_connector.decorators import theory_builder
from isabelle_connector.isabelle_types import Theory, TheoryConfig


@theory_builder(prefix="Transitions")
def transitions_theory(thy: Theory, theory_config: TheoryConfig) -> str:
    """
    Get theorems from a theory.

    :param theory_name: name of the theory
    :returns: theorems from the theory
    """
    theory_config.imports += [str(PROJ_ROOT / "isabelle-thys" / "Extract")]
    return f"""
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


def hol_session(hol_thy):
    # return "HOL"
    name = hol_thy.name
    if "/" not in name:
        return "HOL"

    path, base_name = name.rsplit("/", 1)
    if path.startswith("HOLCF/IOA"):
        session = "-".join(path.split("/")[1:])
    elif path.startswith("HOLCF"):
        session = "-".join(path.split("/"))
    elif path.startswith("MicroJava"):
        session = "-".join(["HOL", "MicroJava"])
    elif path.startswith("Decision_Procs"):
        session = "HOL-Decision_Procs"
    elif path.startswith("Corec_Examples"):
        session = "HOL-Corec_Examples"
    elif path.startswith("Types_To_Sets"):
        session = "HOL-Types_To_Sets"
    elif path.startswith("SPARK/Examples"):
        session = "HOL-SPARK-Examples"
    elif path.startswith("UNITY"):
        session = "HOL-UNITY"
    elif path.startswith("Imperative_HOL"):
        session = "HOL-Imperative_HOL"
    elif path.startswith("Datatype_Examples"):
        session = "HOL-Datatype_Examples"
    elif path.startswith("Auth"):
        session = "HOL-Auth"
    elif path.startswith("Matrix_LP"):
        session = "HOL-Matrix_LP"
    else:
        session = "-".join(["HOL"] + path.split("/"))

    return session


@theory_builder(prefix="Extract")
def template_and_type_extraction_theory(
    src_thy: Theory, theory_config: TheoryConfig
) -> str:
    name = src_thy.name
    base_name = name.rsplit("/", 1)[1] if "/" in name else name
    theory_config.imports += [
        str(PROJ_ROOT / "isabelle-thys" / "ExtractLemmas"),
        str(PROJ_ROOT / "isabelle-thys" / "RoughSpec"),
        f"{theory_config.session}.{base_name}",
    ]
    return f"""
        let
            fun type_of_const symbol =
              let 
                val t = Syntax.read_term @{{context}} symbol
                val typ = Term.type_of t
              in 
                typ
              end 

            val thms = Extract_Lemmas.get_all_thms "{base_name}" @{{context}}
            val results = map (fn (name, thm) => 
            let 
                val term = Thm.prop_of thm
                val template = AbstractLemma.abstract_term_poly @{{context}} term
                val template_str = Print_Mode.setmp [] (Syntax.string_of_term @{{context}}) template
                val symbols = RoughSpec_Utils.const_names_of_term @{{context}} term
                val typs = map (type_of_const) symbols
            in
            (
                "{name}",
                name,
                thm,
                symbols,
                typs,
                template_str
            )
            end) thms;
        in
            results
        end"""
