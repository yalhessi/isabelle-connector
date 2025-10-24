theory RoughSpecExamples
  imports Main RoughSpec
begin
(* Some examples to try things out *)

ML \<open>
(* Example functions*)
val add_fn = "Groups.plus_class.plus"
val rev_fn = "List.rev"; 
val nil_fn = "List.list.Nil";
val length_fn = "List.length";
val app_fn = "List.append";


(* Example templates *)
(* Just instantiating this and updating the type of the variable correctly is a good first goal *)
val template0 = "?H0(x)"

(* Template for commutativity, want to be able to instantiate with for example + and also @, 
   which would update the variable types in different ways.
   Trying to instaniate with a function of the wrong type like length or rev
   should not output a candidate lemma 
   So we want (pseudocode)
   templateProps template1 [+,length,rev,@] = [x_1 + x_2 = x_2 + x_1, x_1 @ x_2 = x_2 @ x_1]*)
val template_commute = "?H1 x_1 x_2  = ?H1 x_2 x_1"
val comm_cands = prettyCands true template_commute [rev_fn,nil_fn,add_fn,app_fn,length_fn]

val hej = Syntax.read_term @{context} "x - y"

val template_assoc = "?H0 (?H0 x_1 x_2) x_3 = ?H0 x_1 (?H0 x_2 x_3)"
val template_invert = "?H0 (?H1 x_0) = x_0"
val template_distrib = "?H0 (?H1 x_1) (?H1 x_2) = ?H1 (?H0 x_1 x_2)"
val tempalte_id_r = "?H0 x_1 ?H1 = x_1"
val template_id_l = "?H0 ?H1 x_1 = x_1"
val template_list_hom =  "?H0 (x_1 @ x_2) = ?H1 (?H0 x_1) (?H0 x_2)"
val template_nest_comm = "?H0(?H1 x_1 x_2)=?H0(?H1 x_2 x_1)"
val map_fn = "List.map";
val sort_fn = "List.sort"
val nub_fn = "List.remdups";

(* Example from section 2 of RoughSpec paper *)
val excands = prettyCands true template_nest_comm [rev_fn,app_fn,length_fn]
val exprops = rsPretty true template_nest_comm [rev_fn,app_fn,length_fn]
(* val excands = ["rev (x_1 @ x_2) = rev (x_2 @ x_1)", "(@) (x_1 @ x_2) = (@) (x_2 @ x_1)", "length (x_1 @ x_2) = length (x_2 @ x_1)"]: Pretty.T list
val exprops = ["length (x_1 @ x_2) = length (x_2 @ x_1)"]: Pretty.T list *)


(* Example from section 1 of RoughSpec paper 
When we run RoughSpec on a signature of five list functions ++,
reverse, map, sort and nub, using the templates (1)–(3) above as
well as commutativity, we get the following output: *)


(* Searching for commutativity properties...
1. sort (xs ++ ys) = sort (ys ++ xs) *)
val comm_cands = prettyCands true template_nest_comm [app_fn,rev_fn,map_fn,sort_fn,nub_fn];
(* Want sort (xs @ ys) = sort (ys @ xs), why doesn't that appear? *)
val comm_props = rsPretty true template_nest_comm [app_fn,rev_fn,map_fn,sort_fn,nub_fn];

(*
(* Debugging *)
val nctraw = Syntax.parse_term @{context} template_nest_comm (* Parse template into term *)
val nctstripped = Type.strip_constraints nctraw (* Strip away type constraints *);
val comm_fills = findFillings nctstripped [app_fn,rev_fn,map_fn,sort_fn,nub_fn];
(* Want sort for H0, @ for H1 *)
List.length comm_fills;
(* 25, 5 functions to fill 2 holes *)
val myfilling = List.nth (comm_fills,15);
val substituted = subst_Vars myfilling nctstripped;
*)
(* Syntax.check_term @{context} (Type.strip_constraints substituted);*)
(* Inconsistent sort constraints for type variable "'a" *)

(*Searching for associativity properties...
2. (xs ++ ys) ++ zs = xs ++ (ys ++ zs)
3. sort (sort (xs ++ ys) ++ zs) =
sort (xs ++ sort (ys ++ zs))
4. nub (nub (xs ++ ys) ++ zs) =
nub (xs ++ nub (ys ++ zs)) *)
val assoc_cands = prettyCands true template_assoc [app_fn,rev_fn,map_fn,sort_fn,nub_fn];
val assoc_props = rsPretty true template_assoc [app_fn,rev_fn,map_fn,sort_fn,nub_fn];
(* ["(x_1 @ x_2) @ x_3 = x_1 @ x_2 @ x_3"] *)
val template_assoc_nest =
"?H0 (?H1 (?H0 (?H1 x_1 x_2)) x_3) = ?H0 (?H1 x_1 (?H0 (?H1 x_2 x_3)))"
val an_cands = prettyCands true template_assoc_nest [app_fn,rev_fn,map_fn,sort_fn,nub_fn];
val an_props = rsPretty true template_assoc_nest [app_fn,rev_fn,map_fn,sort_fn,nub_fn];


(* Searching for inverse function properties...
5. reverse (reverse xs) = xs *)

val inv_cands = prettyCands true template_invert [app_fn,rev_fn,map_fn,sort_fn,nub_fn];
val inv_props = rsPretty true template_invert [app_fn,rev_fn,map_fn,sort_fn,nub_fn];

(* ["rev (rev x_0) = x_0"] *)
(*
Searching for distributivity properties...
6. map f xs ++ map f ys = map f (xs ++ ys)
7. sort (sort xs ++ sort ys) = sort (xs ++ ys)
8. nub (nub xs ++ nub ys) = nub (xs ++ ys) *)

val dist_cands = prettyCands true template_distrib [app_fn,rev_fn,map_fn,sort_fn, nub_fn];
val dist_props = rsPretty true template_distrib [app_fn,rev_fn,map_fn,sort_fn, nub_fn]; 
(* [] *)
val template_nestdist = "?H0 (?H1 (?H0 x_1) (?H0 x_2)) = ?H0 (?H1 x_1 x_2)"
val ndist_cands = prettyCands true template_nestdist [app_fn,rev_fn,map_fn,sort_fn, nub_fn];
val ndist_props = rsPretty true template_nestdist [app_fn,rev_fn,map_fn,sort_fn, nub_fn]; 
(*["sort (sort x_1 @ sort x_2) = sort (x_1 @ x_2)", "remdups (remdups x_1 @ remdups x_2) = remdups (x_1 @ x_2)"] *)

val template_mapdist = "?H0 (?H1 x_1 x_2) (?H1 x_1 x_3) = ?H1 x_1 (?H0 x_2 x_3)"
val mdist_cands = prettyCands true template_mapdist [app_fn,rev_fn,map_fn,sort_fn, nub_fn];
val mdist_props = rsPretty true template_mapdist [app_fn,rev_fn,map_fn,sort_fn, nub_fn]; 
(* ["map x_1 x_2 @ map x_1 x_3 = map x_1 (x_2 @ x_3)"] *)

\<close>
end