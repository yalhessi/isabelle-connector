(* Utility functions for RoughSpec and working with Templates *)
signature ROUGHSPEC_UTILS =
sig
  val indexOf : ''a list -> ''a -> int -> int
  val has_eq  : Term.term -> bool 
  val crossProd : ('a list) list -> ('a list) list
  val is_keep_const : string -> bool
  val const_names_of_term : Proof.context -> term -> string list
  val is_funtype : typ -> bool
  val choose : 'a list -> int -> 'a list list
  val permute : 'a list -> 'a list list
  val zip : 'a list -> 'b list -> ('a * 'b) list
  val untyped_fun : Proof.context -> term -> term option
end

structure RoughSpec_Utils: ROUGHSPEC_UTILS =
struct
  (* Returns a list of all possible combinations of one element from each list in the input *)
  fun crossProd ([]: ('a list) list) = [[]]
    | crossProd (xs :: xss) =  List.concat (map (fn ys => map (fn x => x :: ys) xs) (crossProd xss))
  (* Helper function to find index of element in list *)
  fun indexOf [] _ _ = raise Empty
   |  indexOf (a::xs) x n = if (a = x) then n else indexOf xs x (n+1);

  (* TODO: we don't actually use this? *)
  (* Search for equality signs*)
  fun has_eq (Const ("HOL.eq",_)) = true
   |  has_eq (f$t)                = has_eq f orelse has_eq t
   |  has_eq _                    = false

   (* Certain functions are kept in template structure (and not used to fill in holes).
    TODO: Is this precisely what we want?
          (Set.Ball and Set.Bex are bounded quantifiers defined in HOL/Set, pretty-printed the same as 
           regular quantifiers )
    *)
    fun is_keep_const name =
      String.isPrefix "HOL." name orelse String.isPrefix "Pure." name orelse 
      String.isPrefix "Set.Ball" name orelse String.isPrefix "Set.Bex" name orelse
      String.isPrefix "Orderings.ord_class.less" name orelse String.isPrefix "Orderings.ord_class.less_eq" name orelse
      String.isPrefix "Orderings.ord_class.greater" name orelse String.isPrefix "Orderings.ord_class.greater_eq" name orelse
      String.isPrefix "Set.member" name orelse String.isPrefix "Product_Type.Pair" name;

    fun const_names_of_term ctxt te = 
    let 
      val abbterm = hd (Proof_Context.standard_term_uncheck ctxt [te]) (* abbreviate abbreviations*)
      val all_funs = Term.add_const_names abbterm []
      val use_funs = filter (fn a => not (is_keep_const a)) all_funs
    in use_funs
    end
   (*
   fun consts_of_term te = 
   let
     val all_funs = Term.add_consts te []
     val use_funs = filter (fn (cn,ct) => not (is_keep_const cn)) all_funs
     val const_funs = map (fn x => Const x) use_funs
   in const_funs
   end
  *)
   fun is_funtype (Type ("fun", [_, _])) = true
     | is_funtype _ = false;

  (* choose as n returns a list of all possibilities of choosing n elements from as *)
  fun choose _ 0  = [[]]
  |   choose [] _ = []
  |   choose (x :: xs) n = (map (fn ys => x :: ys) (choose xs (n-1))) @ (choose xs n)

  (* permute x returns a list containing all the permutations of x *)
  fun permute [] = [[]]
  |   permute (x :: xs) = List.concat (List.map (fn ys => interleave x ys) (permute xs))
  and interleave a [] = [[a]]
  |   interleave a (x :: xs) = (a :: x :: xs) :: (List.map (fn ys => x :: ys) (interleave a xs))


  fun zip [] _   = []
   |  zip _ []   = []
   |  zip (x::xs) (y::ys) = (x,y)::(zip xs ys)


  fun untyped_fun ctxt c = case c of
      Const (cn,_) => SOME
                      (Type.strip_constraints
                        (Envir.eta_contract
                           (hd (Proof_Context.standard_term_uncheck ctxt
                                [(Syntax.parse_term ctxt cn)]
                               )
                           )
                         )
                      )
      | _           => NONE

end