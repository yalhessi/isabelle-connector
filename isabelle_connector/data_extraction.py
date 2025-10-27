from argparse import Namespace
import os

from isabelle_connector.config import INTERIM_DATA_DIR
from isabelle_connector.isabelle_types import Theory
from isabelle_connector.utils import path_to_theory_name, temp_theory


def transitions_theory(thy: Theory, configs: Namespace) -> Theory:
    """
    Get theorems from a theory.

    :param theory_name: name of the theory
    :returns: theorems from the theory
    """
    new_thy_name = f"Transitions_{path_to_theory_name(thy.name)}"
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
        name=new_thy_name,
        imports=configs.imports,
        working_directory=os.path.join(
            INTERIM_DATA_DIR, os.path.basename(configs.root_dir)
        ),
    )
    thy.add_ml_block(query)
    return thy


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


def template_and_type_extraction_theory(src_thy: Theory, configs: Namespace) -> Theory:
    name = src_thy.name
    path, base_name = name.rsplit("/", 1) if "/" in name else ("", name)
    session = hol_session(src_thy)
    import_name = f"{session}.{base_name}"

    new_thy_name = f"Extract_{path_to_theory_name(name)}"
    query = f"""
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
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=os.path.join(
            INTERIM_DATA_DIR, os.path.basename(configs.root_dir)
        ),
    )
    thy.add_ml_block(query)
    return thy
