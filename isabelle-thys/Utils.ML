signature Utils =
sig
    val read_template: string -> term
    val string_of_term: term -> string
    val consts_of_term: term -> term list
end

structure Utils: Utils =
struct    
    fun read_template template_str =
    Syntax.parse_term @{context} template_str |> Type.strip_constraints |> HOLogic.mk_Trueprop

    fun string_of_term t =
         Print_Mode.setmp [] (Syntax.string_of_term @{context}) t;

    fun remove(_, []) = []
    | remove(x, y::l) =
        if x = y then
        remove(x, l)
        else
        y::remove(x, l);
    fun removeDup [] = []
    | removeDup(x::l) = x::removeDup(remove(x, l));
    
    fun consts_of_term te = 
            let
            fun leaves (left $ right) = (leaves left) @ (leaves right)
            |   leaves t = [t];
            fun filter_out (Const ("_type_constraint_", _)) = false
            | filter_out (Const _) = true
            | filter_out _ = false;
            val all_leaves = leaves te;
            val filtered_leaves = filter filter_out all_leaves;
        in
            removeDup filtered_leaves
        end;
end