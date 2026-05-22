signature EXTRACT_LEMMAS =
sig
  val get_all_thms: string -> Proof.context -> (string * thm) list
  val get_all_eqs:  string -> Proof.context -> (string * thm) list
  val get_declared_thms: string -> (string * string list) list -> Proof.context -> (string * thm) list
  val get_persisted_thm: string -> string -> Proof.context -> thm option
end

structure Extract_Lemmas : EXTRACT_LEMMAS =
struct
  (* Patterns to search for and to avoid *)
  val eqpattern = Find_Theorems.Pattern(Proof_Context.read_term_pattern 
                  @{context} "Trueprop(_ = _)");
  val badeqpattern = Find_Theorems.Pattern(Proof_Context.read_term_pattern 
                     @{context} "Pure.eq");
  val undefpattern = Find_Theorems.Pattern(Proof_Context.read_term_pattern 
                     @{context} "Trueprop(_ = undefined)");
  val thmpattern = Find_Theorems.Pattern(Proof_Context.read_term_pattern
                   @{context} "Trueprop(_)");
  
  (* Try to avoid some utility theorems, associated with various tools 
   - TODO have another look at whether more things should be added to the list 
     TODO maybe after changes to namefilter this is no longer needed? 
     Are we potentially filtering out things we want?              
  *)
  val badnames =  ["*nitpick*","*Nitpick*", "*full_exhaustive*", "*_def*", "Enum.finite*",
                   "*Quickcheck*", "ATP*","*Nunchaku*","*Code*", "*BNF*","*SMT*"]
  val unwanted_names : (bool * Term.term Find_Theorems.criterion) list = 
    map (Library.pair false) (map (fn s  => Find_Theorems.Name s) badnames);
  fun has_vars t =
    case t of
      Var _           => true
    | Abs (_,_,body)  => has_vars body
    | f$t2            => has_vars f orelse has_vars t2
    | _               => false

  fun compact_string text =
    String.explode text
    |> filter_out Char.isSpace
    |> String.implode

  fun parse_interval text =
    let
      val text' = compact_string text
      fun parse_int chunk = Int.fromString chunk
    in
      if text' = "" then NONE
      else if String.isSuffix "-" text' then
        String.substring (text', 0, size text' - 1)
        |> parse_int
        |> Option.map Facts.From
      else
        (case String.fields (fn c => c = #"-") text' of
          [i] => parse_int i |> Option.map Facts.Single
        | [i, j] =>
            (case (parse_int i, parse_int j) of
              (SOME i', SOME j') => SOME (Facts.FromTo (i', j'))
            | _ => NONE)
        | _ => NONE)
    end

  fun parse_selection text =
    let
      val chunks =
        text
        |> compact_string
        |> String.fields (fn c => c = #",")
        |> filter_out (fn chunk => chunk = "")
      val intervals = map parse_interval chunks
    in
      if null chunks orelse exists is_none intervals then NONE
      else SOME (map the intervals)
    end

  fun find_last_char text ch =
    let
      fun loop i =
        if i < 0 then NONE
        else if String.sub (text, i) = ch then SOME i
        else loop (i - 1)
    in
      loop (size text - 1)
    end

  fun parse_fact_ref fact_name =
    if String.isSuffix ")" fact_name then
      (case find_last_char fact_name #"(" of
        NONE => Facts.named fact_name
      | SOME i =>
          let
            val base_name = String.substring (fact_name, 0, i)
            val selection =
              String.substring (fact_name, i + 1, size fact_name - i - 2)
          in
            case parse_selection selection of
              SOME intervals => Facts.Named ((base_name, Position.none), SOME intervals)
            | NONE => Facts.named fact_name
          end)
    else Facts.named fact_name

  fun lookup_persisted_fact thy raw_name =
    let
      val facts = Global_Theory.facts_of thy
      val context = Context.Theory thy
      val candidate_names =
        [raw_name, Global_Theory.intern_fact thy raw_name]
        |> distinct (op =)
    in
      get_first (fn name =>
        Option.map (pair name) (Facts.lookup context facts name)) candidate_names
    end

  fun lookup_persisted_thm current_thy fact_name fact_ref thy =
    case fact_ref of
      Facts.Fact _ => NONE
    | Facts.Named ((raw_name, _), selection) =>
        (case lookup_persisted_fact thy raw_name of
          NONE => NONE
        | SOME (resolved_name, {thms, ...}) =>
            let
              val selected_ref =
                Facts.Named ((resolved_name, Position.none), selection)
              val selected_thms =
                Facts.select selected_ref thms
                |> map (Thm.transfer current_thy)
            in
              try (Facts.the_single (fact_name, Position.none)) selected_thms
            end
            handle ERROR _ => NONE)

  (* We currently identify target facts by the rendered fact reference string that
     comes out of extraction, e.g. "Foo.bar" or "Foo.bar(2)". That is convenient
     for the dataset pipeline, but it is not yet a canonical persisted theorem
     identifier. In generated theories, some such names resolve immediately in the
     current context because they are re-exported or aliased by imports, while
     other concealed facts need to be recovered from the original source theory's
     global fact table. Thus the current implementation first tries ordinary
     context lookup, then falls back to persisted lookup in the declared source
     theory, transferring the resulting theorem back into the current theory.

     A cleaner long-term design would be to persist an exact theorem locator
     during extraction, for example the internal fact name plus a concrete
     selection index in the source theory. Then retrieval could go directly
     through the source theory alone (e.g. via Global_Theory.get_thm_name),
     avoiding the current-vs-source branching and the reparsing of "foo(2)"
     style references. *)
  fun get_persisted_thm thy_name fact_name ctxt =
    let
      val fact_ref = parse_fact_ref fact_name
      val current_thy = Proof_Context.theory_of ctxt
      val source_thy = Thy_Info.get_theory thy_name
      val lookup_theories =
        if Context.theory_long_name current_thy = Context.theory_long_name source_thy
        then [current_thy]
        else [current_thy, source_thy]
    in
      (case try (Proof_Context.get_thm ctxt) fact_name of
        SOME thm => SOME thm
      | NONE => get_first (lookup_persisted_thm current_thy fact_name fact_ref) lookup_theories)
    end
  
  fun selected_thms_of_fact current_thy thy raw_name =
    case lookup_persisted_fact thy raw_name of
      NONE => NONE
    | SOME (resolved_name, {thms, ...}) =>
        let
          val selected_thms = map (Thm.transfer current_thy) thms
          val rendered =
            if length selected_thms = 1 then
              [(resolved_name, hd selected_thms)]
            else
              map_index
                (fn (i, thm) =>
                  (resolved_name ^ "(" ^ Int.toString (i + 1) ^ ")", thm))
                selected_thms
        in
          SOME rendered
        end

  fun candidate_suffix_match candidate printed_name =
    printed_name = candidate orelse String.isSuffix ("." ^ candidate) printed_name

  fun distinct_named_thms entries =
    fold_rev
      (fn (name, thm) => fn acc =>
        if exists (fn (name', _) => name = name') acc then acc else (name, thm) :: acc)
      entries
      []

  fun suffix_selected_thms candidates ctxt =
    let
      val all_named_thms =
        Find_Theorems.all_facts_of ctxt
        |> map (fn (thm_name, thm) => (Thm_Name.print thm_name, thm))

      fun matches_for candidate =
        all_named_thms
        |> filter (fn (printed_name, _) => candidate_suffix_match candidate printed_name)
        |> distinct_named_thms
    in
      get_first
        (fn candidate =>
          let
            val matches = matches_for candidate
          in
            if null matches then NONE else SOME matches
          end)
        candidates
    end

  fun get_declared_thms source_thy_name declarations ctxt =
    let
      val current_thy = Proof_Context.theory_of ctxt
      val source_thy = Thy_Info.get_theory source_thy_name
      val lookup_theories =
        if Context.theory_long_name current_thy = Context.theory_long_name source_thy
        then [current_thy]
        else [current_thy, source_thy]

      fun resolve_candidates candidates =
        (case get_first
            (fn candidate =>
              get_first (fn thy => selected_thms_of_fact current_thy thy candidate) lookup_theories)
            candidates of
          SOME resolved => SOME resolved
        | NONE => suffix_selected_thms candidates ctxt)

      val thms =
        declarations
        |> maps (fn (declared_name, candidates) =>
            case resolve_candidates candidates of
              SOME resolved => resolved
            | NONE => [])
    in
      thms
      |> filter (fn (name, thm) => Thm.prop_of thm |> has_vars)
    end
  

  fun get_all_eqs namefilter ctxt =
    let  
      val (_, eqs) = Find_Theorems.find_theorems ctxt NONE (SOME 16000) true 
                     ([(true,eqpattern),(false,badeqpattern),(false,undefpattern)]@[(true,Find_Theorems.Name (namefilter))]@unwanted_names)
      in map_filter (fn (thm_name,thm) => 
                          if  Thm.prop_of thm |> has_vars (* Remove plain definitions *)
                          then SOME (Thm_Name.print thm_name, thm)
                          else NONE) eqs
      end;
  
  fun get_all_thms namefilter ctxt =
    let val (_,thms) = Find_Theorems.find_theorems ctxt NONE (SOME 16000) true
                      ([(true,thmpattern),(false,badeqpattern),(false,undefpattern)]@[(true,Find_Theorems.Name (namefilter))]@unwanted_names)
      in map_filter (fn (thm_name,thm) => 
                          if  Thm.prop_of thm |> has_vars (* Remove plain definitions *) 
                          then 
                            if String.isPrefix namefilter (#1 thm_name)
                            then SOME (Thm_Name.print thm_name, thm)
                            else NONE
                          else NONE) thms
      end;
  
end
