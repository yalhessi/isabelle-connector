signature ABSTRACT_LEMMA =
sig
  val abstract_lemma: Proof.context -> thm -> term
  val abstract_lemma_poly: Proof.context -> thm -> term
  val abstract_term: Proof.context -> term -> term
  val abstract_term_poly: Proof.context -> term -> term
  val same_term: term -> term -> bool
  val same_term_untyped: term -> term -> bool
  val unvarify_template: term -> term
  val match_lemma: term -> term -> bool
  val pretty_template: Proof.context -> thm -> Pretty.T
end
structure AbstractLemma: ABSTRACT_LEMMA = struct

(* Lookup or insert a term (either a hole or a variable) 
   into a Termtab *)
fun lookup_or_add hole env t = 
  case Termtab.lookup env t of
    SOME var => (env, var)
  | NONE => let
          val typ = Term.fastype_of t;
          val idx = Termtab.size env + 1;
          val new_var = if hole 
            then Var (("H",idx), typ)
            else Free (("x_"  ^ Int.toString(idx)), typ)
          val env' = Termtab.update (t, new_var) env;
        in
          (env', new_var)
        end

(* Fold function to traverse the term and modify it *)
fun fold_terms f hole_env var_env bound_count term =
  case term of
    t $ u =>
      let
        val ((henv', venv', t'),bc') = fold_terms f hole_env var_env bound_count t;
        val ((henv'', venv'',u'),bc'') = fold_terms f henv' venv' bc' u;
      in
        ((henv'', venv'', t' $ u'),bc'')
      end
  | Abs (_, T, t) =>
      let 
        val ((henv', venv', t'),bc') = fold_terms f hole_env var_env (bound_count+1) t;
        val a' = ("y_" ^ Int.toString(bound_count))
      in
        ((henv', venv', Abs (a', T, t')), bc')
      end
  | _ =>
      (f hole_env var_env term,bound_count);

(* Replace constants with holes
   and make all vars Free + rename them 
   TODO: what if the term contained a Free originally? Rename that in the same system?
*)
fun replace hole_env var_env t = case t of
  Const (cn,ct) =>
  let
    val (henv',t') = if not (RoughSpec_Utils.is_keep_const cn) then
                        lookup_or_add true hole_env (Const (cn,ct)) 
                     else (hole_env,t)
  in (henv',var_env,t')
  end
  | Var v =>
    let
      val (venv',t') = lookup_or_add false var_env (Var v)
    in (hole_env,venv',t')
    end
  | _ => (hole_env, var_env, t)

(* Replace constants with holes, using 1 hole label per function symbol (even if polymorphic).
   Make all vars Free + rename them.
*)
fun replace_poly hole_env var_env t = case t of
  Const (cn,_) =>
  let
    val (henv',t') = if not (RoughSpec_Utils.is_keep_const cn) then
                        lookup_or_add true hole_env (Const (cn,Term.dummyT)) 
                     else (hole_env,t)
  in (henv',var_env,t')
  end
  | Var v =>
    let
      val (venv',t') = lookup_or_add false var_env (Var v)
    in (hole_env,venv',t')
    end
  | _ => (hole_env, var_env, t)

(*  Make all vars Free + rename them *)
fun replace_only_vars hole_env var_env t = case t of
  Var v =>
    let
      val (venv',t') = lookup_or_add false var_env (Var v)
    in (hole_env,venv',t')
    end
  | _ => (hole_env, var_env, t)

(*  Rename Frees *)
fun replace_only_frees hole_env var_env t = case t of
  Free v =>
    let
      val (venv',t') = lookup_or_add false var_env (Free v)
    in (hole_env,venv',t')
    end
  | _ => (hole_env, var_env, t)

(* Templatify term *)
fun abstract_term ctxt (t: term) =
  let
    val abbrev_term = hd (Proof_Context.standard_term_uncheck ctxt [t]) (*Abbreviate abbreviations*)
    val ((_,_, modified_term),_) = fold_terms replace Termtab.empty Termtab.empty 0 abbrev_term
  in
    modified_term
  end

(* Templatify term using 1 hole name per function name, even for polymorphic functions *)
fun abstract_term_poly ctxt (t: term) =
  let
    val abbrev_term = hd (Proof_Context.standard_term_uncheck ctxt [t]) (*Abbreviate abbreviations*)
    val ((_,_, modified_term),_) = fold_terms replace_poly Termtab.empty Termtab.empty 0 abbrev_term
  in
    modified_term
  end

(* Templatify lemma. 
   A polymorphic function occurring with different types will generate a different hole label for each type. *)
fun abstract_lemma ctxt (l: thm) = abstract_term ctxt (Thm.prop_of l)

fun pretty_template ctxt (l: thm) = Syntax.pretty_term ctxt (abstract_lemma ctxt l)

(* Templatify lemma using 1 hole name per function name, even for polymorphic functions *)
fun abstract_lemma_poly ctxt (l: thm) = abstract_term_poly ctxt (Thm.prop_of l)

(* Make all vars Free + rename them *)
fun abstract_term_only_vars (t: term) =
  let
    val ((_,_, modified_term),_) = fold_terms replace_only_vars Termtab.empty Termtab.empty 0 t
  in
    modified_term
  end

(*  Rename Frees *)
fun abstract_term_only_frees (t: term) =
  let
    val ((_,_, modified_term),_) = fold_terms replace_only_frees Termtab.empty Termtab.empty 0 t
  in
    modified_term
  end

fun same_term t1 t2 = Term.aconv (abstract_term_only_vars t1, abstract_term_only_vars t2)
    
fun same_term_untyped t1 t2 = Term.aconv_untyped (abstract_term_only_vars t1, abstract_term_only_vars t2)

fun same_term_untyped_rename_frees t1 t2 = Term.aconv_untyped (abstract_term_only_vars t1, abstract_term_only_frees t2)

(* Used to modify template holes from Var to Free to allow for type inference *)
fun unvarify_template term = case term of
    t $ u => (unvarify_template t) $ (unvarify_template u)
  | Var ((id,idx),typ) => Free (id  ^ Int.toString(idx),typ)
  | Abs (a, T, t) => Abs (a, T, unvarify_template t)
  | _ => term

fun match_lemma t_original t_generated = case t_original of 
   Const ("HOL.Trueprop",_) $ t => match_lemma t t_generated
  | _ => same_term_untyped_rename_frees t_original t_generated orelse same_term_untyped_rename_frees (Envir.eta_contract t_original) t_generated 
         orelse same_term_untyped_rename_frees (Envir.eta_contract t_original) (Envir.eta_contract t_generated)
end

