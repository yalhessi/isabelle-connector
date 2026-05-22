import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from isabelle_connector.isabelle_types import Theory
from isabelle_connector.utils import (
    path_to_theory_name,
    temp_theory,
)


@dataclass
class ExtractionConfig:
    """Configuration for theory-factory functions in this module.

    :param imports: Import strings prepended to every generated theory,
        e.g. ``["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"]``.
    :param working_directory: Directory where temp ``.thy`` files are written.
    """

    imports: list[str] = field(default_factory=list)
    working_directory: str = ""


def hash_roughspec_params(template: str, consts: list[str]) -> str:
    return hashlib.sha256((template + ",".join(consts)).encode("utf-8")).hexdigest()


def hash_params(params: list[str]) -> str:
    return hashlib.sha256((",".join(params)).encode("utf-8")).hexdigest()


_PLACEHOLDER_VAR_RE = re.compile(r"(?<![A-Za-z0-9_.'])([a-z]+_[0-9]+)(?![A-Za-z0-9_.'])")


def freshen_placeholder_vars(text: str, suffix: str) -> str:
    """Give each generated lemma its own placeholder-variable namespace.

    RoughSpec conjectures reuse names like ``x_1`` and ``y_0`` across unrelated
    lemmas. When we paste multiple conjectures into one theorem as assumptions,
    Isabelle identifies same-named variables across assumptions and the goal,
    which can create artificial type clashes. We avoid that by renaming only
    these generated placeholder variables per pasted lemma.
    """

    return _PLACEHOLDER_VAR_RE.sub(
        lambda match: f"{match.group(1)}_{suffix}",
        text,
    )


def ml_string_literal(text: str) -> str:
    if "\\<open>" in text or "\\<close>" in text:
        raise ValueError(
            f"Cannot embed Isabelle cartouche delimiters inside @{{verbatim ...}}: {text!r}"
        )
    return f"@{{verbatim \\<open>{text}\\<close>}}"


def ml_raw_string_literal(text: str) -> str:
    escaped_chars: list[str] = []
    for char in text:
        if char == "\\":
            # Keep arbitrary Isabelle-style escapes inside an ML string literal
            # without requiring the surrounding theory text itself to lex them.
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


def ml_string_list_literal(texts: list[str]) -> str:
    return "[" + ", ".join(ml_string_literal(text) for text in texts) + "]"


def ml_raw_string_list_literal(texts: list[str]) -> str:
    return "[" + ", ".join(ml_raw_string_literal(text) for text in texts) + "]"


def sibling_theory_basenames(src_thy: Theory) -> list[str]:
    name = src_thy.name
    path, base_name = name.rsplit("/", 1) if "/" in name else ("", name)
    theory_dir = Path(src_thy.working_directory) / path
    if not theory_dir.is_dir():
        return []
    return sorted(
        thy_path.stem for thy_path in theory_dir.glob("*.thy") if thy_path.stem != base_name
    )


def historical_lemma_object_printer_ml(src_thy: Theory) -> str:
    local_siblings = sibling_theory_basenames(src_thy)
    return f"""
        val imported_local_theories = {ml_raw_string_list_literal(local_siblings)}

        fun historical_display_term term =
          let
            fun has_schematic_type T =
              exists_subtype (fn TVar _ => true | _ => false) T

            fun rewrite t =
              (case t of
                Const (c, T) =>
                  let
                    val qualifier = Long_Name.qualifier c
                  in
                    if member (op =) imported_local_theories qualifier then
                      Free (Long_Name.base_name c, T)
                    else if c = "Groups.zero_class.zero" andalso has_schematic_type T then
                      Type.constraint T t
                    else
                      t
                  end
              | t => t)

            fun map_term (Abs (x, T, body)) = rewrite (Abs (x, T, map_term body))
              | map_term (t $ u) = rewrite (map_term t $ map_term u)
              | map_term t = rewrite t
          in
            map_term term
          end

        fun string_of_historical_lemma_object ctxt term =
          Print_Mode.setmp [Syntax_Trans.no_bracketsN] (Syntax.string_of_term ctxt)
            (historical_display_term term)
    """


def persisted_thm_lookup_ml(binding: str, theory_name: str, fact_name: str) -> str:
    return (
        f"val {binding} = Extract_Lemmas.get_persisted_thm "
        f"{ml_string_literal(theory_name)} {ml_string_literal(fact_name)} @{{context}}"
    )


def transitions_theory(thy: Theory, configs: ExtractionConfig) -> Theory:
    """Build a theory that parses the transitions of *thy* using ``Extract``.

    :param thy: Source theory whose transitions should be extracted.
    :param configs: Extraction config (imports, working directory).
    :returns: A temp theory whose ML result is ``(name, [(kind, text), ...])``.
    """
    new_thy_name = f"Transitions_{path_to_theory_name(thy.name)}"
    query = f"""
            let
                val filename = {ml_string_literal(f"{thy.working_directory}/{thy.name}.thy")}
                val stream = TextIO.openIn filename
                val content = TextIO.inputAll stream
                val theory = @{{theory}}
                val transitions = Extract.parse_text theory content
                val results = map (fn (trans, string) => (Toplevel.name_of trans, string)) transitions;
            in
                ({ml_string_literal(thy.name)}, results)
            end"""

    new_thy = temp_theory(
        name=new_thy_name,
        imports=configs.imports,
        working_directory=configs.working_directory,
    )
    new_thy.add_ml_block(query)
    return new_thy


def template_and_type_extraction_theory(src_thy: Theory, configs: ExtractionConfig) -> Theory:
    name = src_thy.name
    path, base_name = name.rsplit("/", 1) if "/" in name else ("", name)
    session = src_thy.session
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

            val thms = Extract_Lemmas.get_all_thms {ml_string_literal(base_name)} @{{context}}
            val results = map (fn (name, thm) => 
            let 
                val term = Thm.prop_of thm
                val template = AbstractLemma.abstract_term_poly @{{context}} term
                val template_str = Print_Mode.setmp [] (Syntax.string_of_term @{{context}}) template
                val symbols = RoughSpec_Utils.const_names_of_term @{{context}} term
                val typs = map (type_of_const) symbols
            in
            (
                {ml_string_literal(name)},
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
        working_directory=configs.working_directory,
    )
    thy.add_ml_block(query)
    return thy


def rediscover_conjecture(conj: str, thy: Theory, configs: ExtractionConfig) -> Theory:
    name = thy.name
    path, base_name = thy.name.rsplit("/", 1) if "/" in name else ("", name)
    session = thy.session
    import_name = f"{session}.{base_name}"
    new_thy_name = f"Rediscover_Conj_{path_to_theory_name(name)}_{path_to_theory_name(conj)}"
    query = f"""
        let
            {persisted_thm_lookup_ml("thm_opt", import_name, conj)}
        in
            case thm_opt of
              NONE => ("inaccessible_fact", [])
            | SOME thm =>
                let
                    val term = Thm.prop_of thm
                    val template = AbstractLemma.abstract_term_poly @{{context}} term
                    val prettytemplate = Print_Mode.setmp [] (Syntax.string_of_term @{{context}}) template
                    val consts = RoughSpec_Utils.const_names_of_term @{{context}} term
                in
                    if not (can (Poly_Template.read_from_string @{{context}}) prettytemplate)
                    then ("malformed_template", [])
                    else
                        let
                            val lemma_pairs = Timeout.apply_physical (Time.fromSeconds 60) (RoughSpec_ForwardChecking.templateCandidatesPolyWithCommands @{{context}} prettytemplate) consts
                            val lemmas = map fst lemma_pairs
                            val lemmas_commands = map snd lemma_pairs
                            val result = if List.null lemmas then "empty" else (List.exists (AbstractLemma.match_lemma term) lemmas |> Bool.toString)
                        in
                            (result, lemmas_commands)
                        end
                end
        end handle
            Timeout.TIMEOUT _ => ("timeout", [])
            | _ => ("error", [])
        """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.queries.append("declare [[ML_catch_all]]")
    thy.add_ml_block(query)
    return thy


def roughspec(
    template: str,
    consts: list[str],
    thy: Theory,
    configs: ExtractionConfig,
    timeout_seconds: int = 60,
) -> Theory:
    """Generate RoughSpec candidate lemmas for *template* and *consts*.

    :param template: Polymorphic lemma template string.
    :param consts: Constants to instantiate the template with.
    :param thy: Source theory providing the session and import context.
    :param configs: Extraction config (imports, working directory).
    :param timeout_seconds: Isabelle-side timeout for candidate generation.
    :returns: A temp theory whose ML result is ``(status, [lemma_commands])``.
    """
    name = thy.name
    path, base_name = thy.name.rsplit("/", 1) if "/" in name else ("", name)
    session = thy.session
    import_name = f"{session}.{base_name}"
    new_thy_name = (
        f"RoughSpec_{path_to_theory_name(name)}_{hash_roughspec_params(template, consts)}"
    )
    consts_ml_list = ml_raw_string_list_literal(consts)
    query = f"""
        let
            val template = {ml_raw_string_literal(template)}
            val consts = {consts_ml_list}
        in
            if not (can (Poly_Template.read_from_string @{{context}}) template)
            then ("malformed_template", [])
            else
                let
                    val lemmas = Timeout.apply_physical (Time.fromSeconds {timeout_seconds}) (RoughSpec.templateCandidatesPoly @{{context}} template) consts
                    val lemmas_terms = map (Print_Mode.setmp [] (Syntax.string_of_term @{{context}})) lemmas
                    val lemmas_commands = map (fn t => "lemma " ^ (Library.quote t)) lemmas_terms
                in
                    ("True", lemmas_commands)
                end
        end handle
            Timeout.TIMEOUT _ => ("timeout", [])
            | _ => ("error", [])
        """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.queries.append("declare [[ML_catch_all]]")
    thy.add_ml_block(query)
    return thy


def roughspec_with_match_lemma(
    template: str,
    consts: list[str],
    gold_standard: str,
    thy: Theory,
    configs: ExtractionConfig,
) -> Theory:
    name = thy.name
    path, base_name = thy.name.rsplit("/", 1) if "/" in name else ("", name)
    session = thy.session
    import_name = f"{session}.{base_name}"
    new_thy_name = f"RoughSpec_Match_{path_to_theory_name(name)}_{hash_params([template] + consts + [gold_standard])}"
    consts_ml_list = ml_raw_string_list_literal(consts)
    query = f"""
        let
            val template = {ml_raw_string_literal(template)}
            val consts = {consts_ml_list}
        in
            if not (can (Poly_Template.read_from_string @{{context}}) template)
            then ("malformed_template", [], [])
            else
                let
                    {persisted_thm_lookup_ml("gold_thm_opt", import_name, gold_standard)}
                in
                    case gold_thm_opt of
                      NONE => ("inaccessible_fact", [], [])
                    | SOME gold_thm =>
                        let
                            val gold_term = Thm.prop_of gold_thm
                            val lemma_pairs = Timeout.apply_physical (Time.fromSeconds 60) (RoughSpec_ForwardChecking.templateCandidatesPolyWithCommands @{{context}} template) consts
                            val lemmas = map fst lemma_pairs
                            val matched_lemmas = List.map (AbstractLemma.match_lemma gold_term) lemmas
                            val lemmas_commands = map snd lemma_pairs
                            val result = if List.exists (fn x => x) matched_lemmas then "true" else "false"
                        in
                            (result, lemmas_commands, matched_lemmas)
                        end
                end
        end handle
            Timeout.TIMEOUT _ => ("timeout", [], [])
            | _ => ("error", [], [])
        """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.queries.append("declare [[ML_catch_all]]")
    thy.add_ml_block(query)
    return thy


def apply_proof(conj: str, proof: str, thy: Theory, configs: ExtractionConfig) -> Theory:
    name = thy.name
    path, base_name = thy.name.rsplit("/", 1) if "/" in name else ("", name)
    session = thy.session
    import_name = f"{session}.{base_name}"
    new_thy_name = f"Apply_Proof_{path_to_theory_name(name)}_{hash_params([conj, proof])}"
    query = f"""
        {conj}
        {proof}
        oops
        """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.queries.append(query)
    return thy


def equivalence_theory(
    assm_conj: str,
    conc_conj: str,
    src_thy: Theory,
    configs: ExtractionConfig,
) -> Theory:
    name = src_thy.name
    path, base_name = name.rsplit("/", 1) if "/" in name else ("", name)
    session = src_thy.session
    import_name = f"{session}.{base_name}"

    new_thy_name = f"Equivalence_{path_to_theory_name(name)}_{hash_params([assm_conj, conc_conj])}"
    assm_body = freshen_placeholder_vars(assm_conj.removeprefix("lemma "), "assm0")
    conc_body = freshen_placeholder_vars(conc_conj.removeprefix("lemma "), "conc")
    query = f"""
    lemma assumes {assm_body}
        shows {conc_body}
        sledgehammer
        oops
    """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.queries.append(query)
    return thy


def equivalence_theory_from_assumptions(
    assm_conjs: list[str],
    conc_conj: str,
    src_thy: Theory,
    configs: ExtractionConfig,
) -> Theory:
    name = src_thy.name
    path, base_name = name.rsplit("/", 1) if "/" in name else ("", name)
    session = src_thy.session
    import_name = f"{session}.{base_name}"

    new_thy_name = f"Equivalence_From_Assumptions_{path_to_theory_name(name)}_{hash_params(assm_conjs + [conc_conj])}"
    assm_bodies = "\n".join(
        [
            f"assumes {freshen_placeholder_vars(assm_conj.removeprefix('lemma '), f'assm{i}')}"
            for i, assm_conj in enumerate(assm_conjs)
        ]
    )
    conc_body = freshen_placeholder_vars(conc_conj.removeprefix("lemma "), "conc")
    query = f"""
    lemma {assm_bodies}
        shows {conc_body}
        sledgehammer [max_facts = 1] (assms) 
        oops
    """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.queries.append(query)
    return thy


def equivalence_theory_from_one_fact(
    conj: str,
    src_thy: Theory,
    configs: ExtractionConfig,
    hints: list[str] | None = None,
) -> Theory:
    name = src_thy.name
    path, base_name = name.rsplit("/", 1) if "/" in name else ("", name)
    session = src_thy.session
    import_name = f"{session}.{base_name}"

    hints = hints or []
    new_thy_name = (
        f"Equivalence_From_Fact_{path_to_theory_name(name)}_{hash_params([conj] + hints)}"
    )
    body = conj.removeprefix("lemma ")
    hint_str = f"(add: {' '.join(hints)})" if hints else ""
    query = f"""
    lemma {body}
        sledgehammer [max_facts = 1] {hint_str}
        oops
    """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.queries.append(query)
    return thy


def lemma_object_to_body(
    lemma_name: str,
    src_thy: Theory,
    configs: ExtractionConfig,
) -> Theory:
    name = src_thy.name
    path, base_name = name.rsplit("/", 1) if "/" in name else ("", name)
    session = src_thy.session
    import_name = f"{session}.{base_name}"
    historical_printer_ml = historical_lemma_object_printer_ml(src_thy)

    new_thy_name = f"Lemma_Body_{path_to_theory_name(name)}_{hash_params([lemma_name])}"
    query = f"""
    let
        val ctxt' = @{{context}}
        {historical_printer_ml}
        {persisted_thm_lookup_ml("lemma_opt", import_name, lemma_name)}
    in
        case lemma_opt of
          NONE => Library.quote "<inaccessible_fact>"
        | SOME lemma =>
            let
                val printable_lemma =
                  lemma
                  |> Thm.transfer' ctxt'
                  |> Thm.strip_shyps
                val term = Thm.prop_of printable_lemma
                val term_str = string_of_historical_lemma_object ctxt' term
                val body = Library.quote term_str
            in
                body
            end
    end
    """
    thy = temp_theory(
        name=new_thy_name,
        session=session,
        imports=configs.imports + [import_name],
        working_directory=configs.working_directory,
    )
    thy.add_ml_block(query)
    return thy
