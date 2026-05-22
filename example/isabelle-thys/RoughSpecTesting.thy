theory RoughSpecTesting
  imports Main RoughSpec (*"~~/src/HOL/IMP/AExp" "~~/src/HOL/Computational_Algebra/Formal_Laurent_Series" "~~/src/HOL/Analysis/Abstract_Topology_2"*) 
          (*"~~/src/HOL/Imperative_HOL/ex/List_Sublist"
            "~~/src/HOL/Datatype_Examples/Derivation_Trees/Gram_Lang"
"~~/src/HOL/Analysis/Connected"
*)
(*
"~~/src/HOL/Cardinals/Ordinal_Arithmetic"
"~~/src/HOL/IMP/Com"
*)
(* "HOL-Analysis.Euclidean_Space"*)
"HOL-Analysis.Sparse_In"
(*"HOL-Bali.AxSem"*)
begin
ML_file "Utils.ML"
ML \<open>
val thm0 = @{thm "Sparse_In.get_sparse_from_eventually"}
        val term0 = Thm.prop_of thm0
        val template0 = AbstractLemma.abstract_term_poly @{context} term0
        val prettytemplate0 = Syntax.pretty_term @{context} template0;
val pts = "\<forall>y_0\<in>x_1. ?H1 x_2 (?H2 y_0) \<Longrightarrow> ?H3 x_1 \<Longrightarrow> (\<And>y_2. ?H4 y_2 x_1 \<Longrightarrow> \<forall>y_3\<in>?H5 x_1 y_2. x_2 y_3 \<Longrightarrow> x_3) \<Longrightarrow> x_3"
(* "\<forall>x\<in>?A. eventually ?P (at x) \<Longrightarrow> open ?A \<Longrightarrow> (\<And>pts. pts sparse_in ?A \<Longrightarrow> \<forall>x\<in>?A - pts. ?P x \<Longrightarrow> ?thesis) \<Longrightarrow> ?thesis"*)
(* "\<forall>y_0\<in>x_1. eventually x_2 (at y_0) \<Longrightarrow> open x_1 \<Longrightarrow> (\<And>y_2. y_2 sparse_in x_1 \<Longrightarrow> \<forall>y_3\<in>x_1 - y_2. x_2 y_3 \<Longrightarrow> x_3) \<Longrightarrow> x_3"*)
(* want H1 - eventually, H2 at, H3 open, H4 sparse_in, H5 minus*)
 val consts = RoughSpec_Utils.const_names_of_term @{context} term0
val lemmas = RoughSpec.templateCandidatesPoly @{context} pts consts;
Syntax.pretty_term @{context} (hd lemmas);
val gen = hd lemmas;
val absgen = AbstractLemma.abstract_term_only_frees gen;
val abst = AbstractLemma.abstract_term_only_vars term0;
val abstcon = Envir.eta_contract abst;
val gencon = Envir.eta_contract absgen;
val aac = AbstractLemma.abstract_term_only_frees abstcon;
val con = Envir.eta_contract term0;
AbstractLemma.match_lemma term0 gencon;
Syntax.pretty_term @{context} absgen;
Syntax.pretty_term @{context} abst;

Syntax.pretty_term @{context} abstcon;
Syntax.pretty_term @{context} (AbstractLemma.abstract_term_only_frees abstcon);
Syntax.pretty_term @{context} gencon;
Syntax.pretty_term @{context} term0;
AbstractLemma.match_lemma term0 (hd lemmas);
(*
val thm0 = @{thm AxSem.ax_Call_known_DynT}
        val term0 = Thm.prop_of thm0
        val template0 = AbstractLemma.abstract_term_poly @{context} term0
        val prettytemplate0 = Syntax.pretty_term @{context} template0;
(* Some useful examples that required different changes:
"Ordinal_Arithmetic.dir_image_alt" (polymorphism)
Ordinal_Arithmetic.fin_support_Field_osum (filling type bigger than hole type)
"Complete_Lattices.INF2_D" (filling type can be smaller than hole type, eta contraction in equivalence check) *)
       val thm = @{thm Euclidean_Space.sum_Basis_prod_eq}
(* "sum ?f Basis = (\<Sum>i\<in>Basis. ?f (i, 0)) + (\<Sum>i\<in>Basis. ?f (0, i))*)
        val thm2 = @{thm Euclidean_Space.sum_if_inner}
val thm3 = @{thm Euclidean_Space.euclidean_isCont}
(*"(\<And>b. b \<in> Basis \<Longrightarrow> isCont (\<lambda>x. inner (?f x) b *\<^sub>R b) ?x) \<Longrightarrow> isCont ?f ?x"*)
(*"(\<And>y_0. y_0 \<in> Basis \<Longrightarrow> isCont (\<lambda>y_1. inner (x_1 y_1) y_0 *\<^sub>R y_0) x_2) \<Longrightarrow> isCont x_1 x_2"*)
        val term = Thm.prop_of thm3
        val template = AbstractLemma.abstract_term_poly @{context} term
        val prettytemplate = Syntax.pretty_term @{context} template;
        val consts = RoughSpec_Utils.const_names_of_term @{context} term
val pts = "?H1 x_1 ?H2 = ?H3 (?H1 (\<lambda>y_0. x_1 (y_0, ?H4)) ?H2) (?H1 (\<lambda>y_1. x_1 (?H4, y_1)) ?H2)"
val pts2 ="x_1 \<in> ?H1 \<Longrightarrow> x_2 \<in> ?H1 \<Longrightarrow> ?H2 (?H3 (\<lambda>y_0. if y_0 = x_1 then ?H4 (x_3 x_1) x_1 else ?H4 (x_4 y_0) y_0) ?H1) x_2 = (if x_2 = x_1 then x_3 x_2 else x_4 x_2)"
val pts3 = "(\<And>y_0. y_0 \<in> ?H1 \<Longrightarrow> ?H2 (\<lambda>y_1. ?H3 (?H4 (x_1 y_1) y_0) y_0) x_2) \<Longrightarrow> ?H2 x_1 x_2"
(* want H1 Basis, H2 isCont , H3 scaleR, H4 inner *)
val lemmas1 = RoughSpec.templateCandidatesPoly @{context} pts3 consts;
val lehm = hd lemmas1;
val look = Syntax.pretty_term @{context} lehm;
AbstractLemma.match_lemma term lehm;
List.exists (AbstractLemma.match_lemma term) lemmas1;

(*
val look = "(\<And>y_0. y_0 \<in> Basis \<Longrightarrow> isCont (\<lambda>y_1. inner (x_1 y_1) y_0 *\<^sub>R y_0) x_2) \<Longrightarrow> isCont x_1 x_2"
*)
(*
val at = AbstractLemma.abstract_term_only_vars term;
val al = AbstractLemma.abstract_term_only_frees lehm;
val lookat = Syntax.pretty_term @{context} at;
val lookal = Syntax.pretty_term @{context} al;
    val usefuns = filter (fn f => not (RoughSpec_Utils.is_keep_const f)) consts
    val tfuns = map (Syntax.read_term @{context}) usefuns (* Parse function names into terms *) 
    val tufuns = Proof_Context.standard_term_uncheck @{context} tfuns (* re-contract abbreviations *)
    val tuefs  = map Envir.eta_contract tufuns (* Eta contraction *)
    val traw = Syntax.parse_term @{context} pts3 (* Parse template into term *)
    val tstripped = Type.strip_constraints traw (* Strip away type constraints *)
    val unvar_template = AbstractLemma.unvarify_template tstripped
*)
val fillings = RoughSpec.findFillingsPoly @{context} tstripped tuefs
val hm2 = length fillings
    val maybeProps = map (RoughSpec.instaTerm @{context} tstripped) fillings
(* want H1 sum, H2 Basis, H3 plus, H4 zero*)
val fill = hd fillings
val sub = subst_Vars fill tstripped
    (*val typed_template = Syntax.check_term @{context} unvar_template*)
*)
(*
  fun all_holes_unvar (t: term) = get_holes (Term.add_frees t [])
  and get_holes vs = filter (fn (n,_) => String.isPrefix "H" n) vs
    val typed_holes    = all_holes_unvar typed_template
    val num_holes = List.length typed_holes

    val choices = RoughSpec_Utils.choose tuefs num_holes 
    val options : term list list = List.concat (map RoughSpec_Utils.permute choices) 
*)
(*
    val choices : term list list = RoughSpec_Utils.choose tuefs 4
    val options : term list list = List.concat (map RoughSpec_Utils.permute choices) 
    val hm = length options

*)
(*
val thm1 = @{thm "Complete_Lattices.INF2_D"}
(* "connected_component_set ?S ?x \<subseteq> ?S": thm *)
(* "connected_component_set {} ?x = {}": thm *)
(*  "connected (connected_component_set ?S ?x)": thm *)
val term1 = Thm.prop_of thm1
val template1 = AbstractLemma.abstract_term @{context} term1
val prettytemplate1 = Syntax.pretty_term @{context} template1
val prettytemplate = Print_Mode.setmp ["internal"] (Syntax.string_of_term @{context}) template1 
val pts1 =  "?H1 (?H2 x_1 x_2) x_3 x_4 \<Longrightarrow> x_5 \<in> x_2 \<Longrightarrow> x_1 x_5 x_3 x_4"
val symbols1 = RoughSpec_Utils.const_names_of_term @{context} term1
val lemmas1 = RoughSpec.templatePropsStringInputs @{context} pts1 symbols1;
List.exists (AbstractLemma.match_lemma term1) lemmas1; (*false*)

(*now using polymorphism ignoring abstraction*)
val template2 = AbstractLemma.abstract_term_poly @{context} term1
val prettytemplate2 = Syntax.pretty_term @{context} template2
val pts2 = "?H1 (?H2 x_1 x_2) x_3 x_4 \<Longrightarrow> x_5 \<in> x_2 \<Longrightarrow> x_1 x_5 x_3 x_4"
val lemmas2 = RoughSpec.templateCandidatesPoly @{context} pts2 symbols1;
List.exists (AbstractLemma.match_lemma term1) lemmas2; (* true *)
*)

(*
val thm = @{thm "List_Sublist.nths_Nil'"}
(* val thm = "nths ?xs ?inds = [] \<Longrightarrow> \<forall>i\<in>?inds. length ?xs \<le> i": thm *)
val term = Thm.prop_of thm
val prettythm = Syntax.pretty_term @{context} term
val template = AbstractLemma.abstract_term @{context} term
val hhh = Syntax.string_of_term @{context} template
val prettytemplate = AbstractLemma.pretty_template @{context} thm
(* copy-paste pretty template string *)
val prettytemplatestring =  "?H1 x_1 x_2 = ?H2 \<Longrightarrow> \<forall>i\<in>x_2. ?H3 (?H4 x_1) i"
val symbols = RoughSpec_Utils.const_names_of_term @{context} term
val lemmas = RoughSpec.templatePropsStringInputs @{context} prettytemplatestring symbols;
(* Empty list when Set.Ball not in keep_consts, after it's Unbound schematic variable: ?H3 *)
List.exists (AbstractLemma.match_lemma term) lemmas;
*)
(* This examples works out fine*)
(*
val thm2 = @{thm "List_Sublist.nths_eq_subseteq"}
(*"?inds' \<subseteq> ?inds \<Longrightarrow> nths ?xs ?inds = nths ?ys ?inds \<Longrightarrow> nths ?xs ?inds' = nths ?ys ?inds'" *)
val term2 = Thm.prop_of thm2
val prettythm2 = Syntax.pretty_term @{context} term2
val template2 = AbstractLemma.abstract_term @{context} term2
val prettytemplate2 = Syntax.pretty_term @{context} template2
(* copy-paste pretty template string *)
val prettytemplatestring2 =  "?H1 x_1 x_2 \<Longrightarrow> ?H2 x_3 x_2 = ?H2 x_4 x_2 \<Longrightarrow> ?H2 x_3 x_1 = ?H2 x_4 x_1"
val symbols2 = RoughSpec_Utils.const_names_of_term @{context} term2

val lemmas = RoughSpec.templatePropsStringInputs @{context} prettytemplatestring2 symbols2;
List.exists (AbstractLemma.match_lemma term2) lemmas;
*)
(* Example with existential quantification: *)
(*
val thm3 = @{thm "Gram_Lang.subtr_H"}
(* "inItr UNIV ?tr0.0 ?n \<Longrightarrow> subtr UNIV ?tr1.0 (H ?tr0.0 ?n) \<Longrightarrow> \<exists>n1. inItr UNIV ?tr0.0 n1 \<and> ?tr1.0 = H ?tr0.0 n1": thm *)
val term3 = Thm.prop_of thm3
val prettythm3 = Syntax.pretty_term @{context} term3
val template3 = AbstractLemma.abstract_term @{context} term3
val prettytemplate3 = Syntax.pretty_term @{context} template3
(* copy-paste pretty template string *)
val prettytemplatestring3 = "?H1 ?H2 x_1 x_2 \<Longrightarrow> ?H3 ?H2 x_3 (?H4 x_1 x_2) \<Longrightarrow> \<exists>y_0. ?H1 ?H2 x_1 y_0 \<and> x_3 = ?H4 x_1 y_0"
val symbols3 = RoughSpec_Utils.const_names_of_term @{context} term3
val lemmas3 = RoughSpec.templatePropsStringInputs @{context} prettytemplatestring3 symbols3;

(*
Error: Illegal internal variable in abstraction: "uu_"*)
List.exists (AbstractLemma.match_lemma term3) lemmas3;
*)
(*
val thm4 = @{thm "Gram_Lang.H_P"}
val term4 = Thm.prop_of thm4
val abbterm4 = hd (Proof_Context.standard_term_uncheck @{context} [term4])
val template4 = AbstractLemma.abstract_term @{context} term4
val prettythm = Syntax.pretty_term @{context} term4
val prettytemplate4 = Syntax.pretty_term @{context} template4
val ptstring =  "?H1 x_1 \<Longrightarrow> ?H2 ?H3 x_1 x_2 \<Longrightarrow> ?H4 (?H5 x_2 (?H6 (?H7 ?H8 ?H9) (?H10 (?H11 x_1 x_2)))) ?H12"
val pts4u = "?H1 x_1 \<Longrightarrow> ?H2 ?H3 x_1 x_2 \<Longrightarrow> (x_2, ?H4 (?H5 x_1 x_2)) \<in> ?H6"
val symbols4 = RoughSpec_Utils.const_names_of_term @{context} abbterm4
val symbols44 =  RoughSpec_Utils.const_names_of_term @{context} term4
val lemmas4u = RoughSpec.templatePropsStringInputs @{context} pts4u symbols4;
List.exists (AbstractLemma.match_lemma term4) lemmas4u;
*)
(* 
(* some examples for testing *)
val lemma1 = @{thm "List.length_rev"} (*"length (rev ?xs) = length ?xs"*)
val lemma2 = @{thm "List.length_append"} (*"length (?xs @ ?ys) = length ?xs + length ?ys"*)
val lemma3 = @{thm "List.length_0_conv"} (*"(length ?xs = 0) = (?xs = [])"*)
val lemma4 = @{thm "List.append_assoc"} (*"(?xs @ ?ys) @ ?zs = ?xs @ ?ys @ ?zs"*)

val test1 = Thm.cterm_of @{context} (AbstractLemma.abstract_term (Thm.prop_of lemma1))
val test2 = Thm.cterm_of @{context} (AbstractLemma.abstract_term (Thm.prop_of lemma2))
val test3 = Thm.cterm_of @{context} (AbstractLemma.abstract_term (Thm.prop_of lemma3))
val test4 = Thm.cterm_of @{context} (AbstractLemma.abstract_term (Thm.prop_of lemma4))
*)
(*
val thm = @{thm "AExp.aval_plus"}
val term = Thm.prop_of thm
val (tp,argterm) = Term.dest_comb term
val prettythm = Syntax.pretty_term @{context} term
val template = AbstractLemma.abstract_term term
val prettytemplate = Syntax.pretty_term @{context} template
(* copy-paste pretty template string *)
val prettytemplatestring =  "?H1 (?H2 x_1 x_2) x_3 = ?H3 (?H1 x_1 x_3) (?H1 x_2 x_3)"
val symbols = RoughSpec_Utils.const_names_of_term term
val t = Type.strip_constraints (Syntax.parse_term @{context} prettytemplatestring)
val unvar_template = AbstractLemma.unvarify_template t
val typed_template = Syntax.check_term @{context} unvar_template


val lemmas = RoughSpec.templatePropsStringInputs @{context} prettytemplatestring symbols;
List.exists (AbstractLemma.match_lemma term) lemmas;

val fltthm = @{thm "Formal_Laurent_Series.fls_integral_X_power"}
val fltterm = Thm.prop_of fltthm
val (_,fltargterm) = Term.dest_comb fltterm
val prettythm = Syntax.pretty_term @{context} fltterm
val flt = "?H1 (?H2 ?H3 x_1) =      ?H4 (?H5 (?H6 (?H7 (?H8 x_1)))) (?H2 ?H3 (?H8 x_1))"
val fltfs = ["Nat.Suc","Nat.semiring_1_class.of_nat", "Fields.inverse_class.inverse","Formal_Laurent_Series.fls_const","Groups.times_class.times",
                                    "Formal_Laurent_Series.fls_X","Power.power_class.power","Formal_Laurent_Series.fls_integral"]
val fltfuns =  map (Syntax.read_term @{context}) fltfs
val flttraw = Syntax.parse_term @{context} flt (* Parse template into term *)
val flttstripped = Type.strip_constraints flttraw (* Strip away type constraints *)
val fltchecked = Syntax.check_term 
val fs = RoughSpec.findFillings @{context} flttstripped fltfuns;
val l = length(fs);



val maybeps = map (RoughSpec.instaTerm @{context} flttstripped) fs
val lemmas2 = RoughSpec.templatePropsStringInputs @{context} flt fltfs;
List.exists (AbstractLemma.match_lemma fltterm) lemmas2;
(*
val l2 = RoughSpec.templatePropsStringInputs @{context} "?H1 (?H2 ?H3 x_1) =      ?H4 (?H5 (?H6 (?H7 (?H8 x_1)))) (?H2 ?H3 (?H8 x_1))" 
                                   ["Nat.Suc","Nat.semiring_1_class.of_nat", "Fields.inverse_class.inverse","Formal_Laurent_Series.fls_const","Groups.times_class.times",
                                    "Formal_Laurent_Series.fls_X","Power.power_class.power","Formal_Laurent_Series.fls_integral"]*)

val thm2 = @{thm "Abstract_Topology_2.retract_of_subset"}
val term2 = Thm.prop_of thm2
val temp2 = AbstractLemma.abstract_term term2
val prettytemplate = Syntax.pretty_term @{context} temp2

val symbs2 = RoughSpec_Utils.consts_of_term term2

val l2 = RoughSpec.all_holes temp2

(* Illegal schematic type variable: ?'a *)
val string_template =  "?H1 x_1 x_2 \<Longrightarrow> ?H2 x_1 x_3 \<Longrightarrow> ?H2 x_3 x_2 \<Longrightarrow> ?H1 x_1 x_3"
val string_consts = RoughSpec_Utils.const_names_of_term term2
val l2 = RoughSpec.templatePropsStringInputs @{context} string_template string_consts;
val same = List.nth(l2,2);
val check = AbstractLemma.same_term_untyped same term2;
(* Look into same_term, is same_term_untyped ok? optionally strip away trueprop thingy *)

val string_template =  "?H1 x_1 x_2 \<Longrightarrow> ?H2 x_1 x_3 \<Longrightarrow> ?H2 x_3 x_2 \<Longrightarrow> ?H1 x_1 x_3"
val string_consts = RoughSpec_Utils.const_names_of_term term2
val consts = map (fn x => Type.strip_constraints (Syntax.parse_term @{context} x)) string_consts
val typed_consts = map (Syntax.check_term @{context}) consts
(* [Const ("Orderings.ord_class.less_eq", "'a \<Rightarrow> 'a \<Rightarrow> bool"), Const ("Abstract_Topology_2.retract_of", "'a set \<Rightarrow> 'a set \<Rightarrow> bool")]: term list*)
val untyped_temp = Type.strip_constraints (Syntax.parse_term @{context} string_template)
val unvarified = AbstractLemma.unvarify_template untyped_temp
val typed_temp = Syntax.check_term @{context} unvarified
val holes = RoughSpec.all_holes_unvar typed_temp
val (h2n,h2t) = hd holes
val (c1n,c1t) = Term.dest_Const (hd typed_consts)
val (c2n,c2t) = Term.dest_Const (List.last typed_consts);
*)
\<close>

end