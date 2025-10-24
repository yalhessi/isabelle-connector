signature ROUGHSPEC =
sig
  val instaTerm : Proof.context -> term -> (indexname * term) list -> term option
  val all_holes : term -> (indexname * typ) list
  val all_holes_unvar : term -> (string * typ) list
  val findFillings : Proof.context -> bool -> term -> term list -> (indexname * term) list list
  val templateProps : Proof.context -> bool -> bool -> term -> term list -> term list
  val lemmanaid_candidates : Proof.context -> bool -> bool -> string -> string list -> term list
  val templatePropsStringInputs : Proof.context -> string -> string list -> term list
  val templateCandidatesMulti : Proof.context -> string -> string list -> term list 
  val templateCandidatesPoly : Proof.context -> string -> string list -> term list
  val conjecture : Proof.context -> bool -> bool -> string -> string list -> term list
  val simple_counter_check : Proof.context -> term -> bool
  val findFillingsPoly : Proof.context -> term -> term list -> (indexname * term) list list
end
structure RoughSpec: ROUGHSPEC =
struct
  (* Takes a term and a list of filling pairs (Hole, function)
     Returns (option) the term with the holes filled.
  *)
  (* Assume that input term has already been stripped of type constraints *)
  fun instaTerm ctxt (t: term) (fillings: (indexname * term) list) = 
  let 
      val substituted = subst_Vars fillings t
      (* leverage the built in type inference to infer Free var types *)
      val checked = (SOME (Syntax.check_term ctxt substituted ))
                    handle ERROR _  => NONE
    in checked
  end
  
  (* Find all holes in a term (a hole is a var with the name "H")*)
  (* Return type  (indexname * typ) list *)
  fun all_holes (t: term) = get_holes (Term.add_vars t [])
  and get_holes vs = filter (fn ((n,_),_) => n = "H") vs
  
  fun all_holes_unvar (t: term) = get_holes (Term.add_frees t [])
  and get_holes vs = filter (fn (n,_) => String.isPrefix "H" n) vs
  
  (* If one type is a funtype the other should also be, 
     and if so their binder_types should be of equal length *)
  fun isFeasibleFill (htyp: typ) (f: term) = case f of 
    Const (_,ct) =>
      let
        val fh = RoughSpec_Utils.is_funtype htyp
        val fc = RoughSpec_Utils.is_funtype ct in
        if fh 
        then (fc andalso length(Term.binder_types htyp) = length(Term.binder_types ct))
        else (not fc)
      end
    | _ => false

    fun isFeasibleFillMulti (htyp: typ) (f: term) = case f of 
    Const (_,filltype) =>
      let
        val funhole = RoughSpec_Utils.is_funtype htyp
        val funfill = RoughSpec_Utils.is_funtype filltype in
        if funhole 
        (* setting \<le> instead of = here lets hole type variables be filled with function types, more coverage but also more timeouts? *)
        then funfill 
          (*(fc andalso length(Term.binder_types htyp) <= length(Term.binder_types ct))
        *)
        else true (*(not fc orelse  length(Term.binder_types ct) = 1)*) (* OR true OR (not fc) OR set length longer! *)
      end
    | _ => false

  (* Take in typed hole (Free), typed consts, return (indexname * term) list 
     containing the hole's indexname and the untyped function terms *)
  fun feasibleFill ctxt (multi: bool) (funs: term list) (hole: (string * typ)) =
  let
    val (hname,htyp) = hole
    val fits =  if multi then filter (isFeasibleFillMulti htyp) funs 
                         else filter (isFeasibleFill htyp) funs
    val hidx = case Int.fromString (String.extract(hname,1,NONE)) of
                 NONE => 0
               | SOME k => k
    val hidname = ("H",hidx)
    val untyped_fits = List.mapPartial (RoughSpec_Utils.untyped_fun ctxt) fits
    in map (fn f => (hidname,f)) untyped_fits   
  end
  (* Takes template and list of functions
    (TODO: divided into functions in current exploration scope and background functions),
    returns a list of maps (lists of filling pairs) with hole names as keys
    and possible fillings for those holes as values
  *)
  fun findFillings ctxt (multi: bool) (t: term) (funs: term list) =
  let 
    val unvar_template = AbstractLemma.unvarify_template t
    val typed_template = Syntax.check_term ctxt unvar_template
    val typed_holes    = all_holes_unvar typed_template
    (* all feasible fillings for all holes ((indexname * term) list) list *)
    val allFillings = map (feasibleFill ctxt multi funs) typed_holes
  in RoughSpec_Utils.crossProd allFillings
  end

  fun findFillingsPoly ctxt (t: term) (funs: term list) =
  let
    val holes = all_holes t
    val num_holes = List.length holes

    (* choose appropriate number of hole filling functions *)
    val choices : term list list = RoughSpec_Utils.choose funs num_holes
    (* all possible options for hole filling *)
    val options : term list list = List.concat (map RoughSpec_Utils.permute choices) 

    val unvar_template = AbstractLemma.unvarify_template t
    val typed_template = (SOME (Syntax.check_term ctxt unvar_template ))
                          handle ERROR _ => NONE
    fun checkOption cx h f = case feasibleFill cx true [f] h of
            []  => NONE
          | [p] => SOME p
          | _   => NONE
     (* returns ((indexname * term) list) *)
     fun checkOptions _ _ [] = []
       |   checkOptions _ [] _ = []
       |   checkOptions cx (h :: hhs) (f :: ffs) = case (checkOption cx h f) of
              NONE   => [NONE]
            | SOME p => (SOME p) :: (checkOptions cx hhs ffs)
     fun findOptionsTyped tt ops =
     let
       val typed_holes    = all_holes_unvar tt
       val possibilities = map (checkOptions ctxt typed_holes) ops
       val feasibles = filter (fn xs =>
                              not (exists (fn x => not (Option.isSome x)) xs))
                              possibilities
     in map (map Option.valOf) feasibles
     end

     val holenames = map (fn (iname,_) => iname) holes

     val results = case typed_template of
         NONE => map (fn l => RoughSpec_Utils.zip holenames
                              (List.mapPartial (RoughSpec_Utils.untyped_fun ctxt) l))
                     options
       | SOME tt => findOptionsTyped tt options

   (* (indexname * term) list list*)
  in results
  end

  (* Take a template and a list of functions, return a list of properties (type term?) 
     generated by using the functions to fill the holes of the template *)
  (* TODO: consider division between background and foreground functions *)
  fun templateProps ctxt (multi: bool) (poly: bool) (t: term) (funs: term list) = 
  let 
    val fillingsMap = if poly then findFillingsPoly ctxt t funs
                      else findFillings ctxt multi t funs
    val maybeProps = map (instaTerm ctxt t) fillingsMap
    val someProps  = filter Option.isSome maybeProps
    val props      = map Option.valOf someProps
  in props
  end

  (* Template and functions are all given as strings *)
  fun lemmanaid_candidates ctxt (multi: bool) (poly: bool) (ts: string) (funs: string list) =
  let
    val usefuns = filter (fn f => not (RoughSpec_Utils.is_keep_const f)) funs
    val tfuns = map (Syntax.read_term ctxt) usefuns (* Parse function names into terms *) 
    val tufuns = Proof_Context.standard_term_uncheck ctxt tfuns (* re-contract abbreviations *)
    val tuefs  = map Envir.eta_contract tufuns (* Eta contraction *)
    val traw = Syntax.parse_term ctxt ts (* Parse template into term *)
    val tstripped = Type.strip_constraints traw (* Strip away type constraints *)
    in templateProps ctxt multi poly tstripped tuefs
  end
  
  (* Template and functions are all given as strings 
     - hole fillings restricted to fit hole type precisely *)
  fun templatePropsStringInputs ctxt (ts: string) (funs: string list) =
      lemmanaid_candidates ctxt false false ts funs 

  (* Template and functions are all given as strings 
     - hole fillings can have more type arguments than hole *)
  fun templateCandidatesMulti ctxt (ts: string) (funs: string list) =
      lemmanaid_candidates ctxt true false ts funs 

  fun templateCandidatesPoly ctxt (ts: string) (funs: string list) =
      lemmanaid_candidates ctxt true true ts funs

  (* uses counterexample checking to check correctness of generated conjecture 
     assumes conjecture is syntax-correct
     lemma_conj is of type term, limit_time is boolean,
     which_tester should be "random" or "exhaustive"
     returns false if counterexample is found, true if none is found.
  *)
  (* TODO: use both nitpick and quickcheck? *)
  (* TODO: how to adjust time limit? (default is 30 seconds) *)
  fun counter_check limit_time which_tester ctxt lemma_conj = 
    let 
      val ctxt' = Context.proof_map (Quickcheck.set_active_testers [which_tester]) ctxt
      val test_result = Quickcheck.test_terms ctxt' (limit_time, false) [] [(lemma_conj,[])]
      in case test_result of
        NONE => true
       |SOME _ => false
    end

  fun simple_counter_check ctxt conj = counter_check true "random" ctxt conj

  (* conjecture function: for a given context, template (string) and list of functions, *)
  (* output conjectures that pass counterexample check *)
  fun conjecture ctxt (multi: bool) (poly: bool) (ts: string) (funs: string list) = 
  let 
    val cands = lemmanaid_candidates ctxt multi poly ts funs 
    in filter (fn p => counter_check true "random" ctxt p) cands
  end

end