signature EXTRACT =
sig
    val parse_text: theory -> string -> (Toplevel.transition * string) list
    val get_used_consts: Proof.context -> string list -> string list 
    val get_used_consts_one: Proof.context -> string -> string list 
    val consts_of_term: Proof.context -> term -> string list
end

structure Extract : EXTRACT =
struct
  (* fun read_file path =
    let
      val file = Path.explode path
      val _ = if not (File.exists file) then error ("File " ^ path ^ " does not exist") else ()
      val _ = if not (File.is_file file) then error ("File " ^ path ^ " is not a file") else ()
      val _ = if not (File.is_readable file) then error ("File " ^ path ^ " is not readable") else ()
      val text = File.read file
    in
      text
    end *)

  fun parse_text thy text =
    let
      val transitions = Outer_Syntax.parse_text thy (K thy) Position.start text
      fun addtext symbols trs =
        case trs of
          [tr] => [(tr, implode symbols)]
        | [] => []
        | (tr::nextTr::trs) => 
            let
                val (this,rest) = Library.chop (Position.distance_of (Toplevel.pos_of tr, Toplevel.pos_of nextTr) |> Option.valOf) symbols
            in (tr, implode this) :: addtext rest (nextTr::trs) end
      in addtext (Symbol.explode text) transitions 
    end

  fun get_used_consts_one ctxt inner =
    let
      fun remove(_, []) = []
        | remove(x, y::l) =
          if x = y then
            remove(x, l)
          else
            y::remove(x, l);
      fun removeDup [] = []
        | removeDup(x::l) = x::removeDup(remove(x, l));

      fun string_to_term s =
        Syntax.parse_term ctxt s handle ERROR _ => Syntax.read_term ctxt s;

      fun term_to_string t =
        Print_Mode.setmp [] (Syntax.string_of_term ctxt) t;

      fun consts_of_term te = 
        let
          fun leaves (left $ right) = (leaves left) @ (leaves right)
          |   leaves t = [t];
          fun filter_out (Const ("_type_constraint_", _)) = false
          | filter_out (Const _) = true
          | filter_out _ = false;
          val all_leaves = leaves te;
          val filtered_leaves = filter filter_out all_leaves;
          fun string_of_term t = 
              (Print_Mode.setmp [] (Syntax.string_of_term ctxt) t)
      in
          map term_to_string filtered_leaves
      end;
    in
      removeDup (consts_of_term (string_to_term inner))
    end


  fun get_used_consts ctxt inners =
    let
      fun remove(_, []) = []
        | remove(x, y::l) =
          if x = y then
            remove(x, l)
          else
            y::remove(x, l);
      fun removeDup [] = []
        | removeDup(x::l) = x::removeDup(remove(x, l));

      fun string_to_term s =
        Syntax.parse_term ctxt s;

      fun term_to_string t =
        Print_Mode.setmp [] (Syntax.string_of_term ctxt) t;

      fun consts_of_term te = 
        let
          fun leaves (left $ right) = (leaves left) @ (leaves right)
          |   leaves t = [t];
          fun filter_out (Const ("_type_constraint_", _)) = false
          | filter_out (Const _) = true
          | filter_out _ = false;
          val all_leaves = leaves te;
          val filtered_leaves = filter filter_out all_leaves;
          fun string_of_term t = 
              (Print_Mode.setmp [] (Syntax.string_of_term ctxt) t)
      in
          map term_to_string filtered_leaves
      end;

      val type_to_list = fn ty =>
      let
        fun type_t (Type ty) = [#1 ty] @ (flat (map type_t (#2 ty)))
        | type_t (TFree _) = []
        | type_t (TVar _) = [];
        fun filter_out_universal_type_symbols symbol =
      case symbol of
        "fun" => false
        | "prop" => false
        | "itself" => false
        | "dummy" => false
        | "proof" => false
        | "Pure.proof" => false
        | _ => true;
      in
        filter filter_out_universal_type_symbols (type_t ty)
      end;


    in
      removeDup (List.concat (map (fn inner => 
          consts_of_term (string_to_term inner) handle ERROR _ => type_to_list (Syntax.parse_typ ctxt inner) handle ERROR _ => []
        ) inners))
    end

  fun consts_of_term ctxt te =
    let
      fun leaves (left $ right) = (leaves left) @ (leaves right)
      |   leaves t = [t];
      fun filter_out (Const ("_type_constraint_", _)) = false
      | filter_out (Const _) = true
      | filter_out _ = false;
      val all_leaves = leaves te;
      val filtered_leaves = filter filter_out all_leaves;
      fun string_of_term t = 
          (Print_Mode.setmp [] (Syntax.string_of_term ctxt) t)
    in
        map string_of_term filtered_leaves
    end
end