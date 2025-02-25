signature EXTRACT_LEMMAS =
sig
  val get_all_thms: string -> Proof.context -> (string * thm) list
  val get_all_eqs:  string -> Proof.context -> (string * thm) list
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
  

  fun get_all_eqs namefilter ctxt =
    let  
      val (_, eqs) = Find_Theorems.find_theorems ctxt NONE (SOME 16000) true 
                     ([(true,eqpattern),(false,badeqpattern),(false,undefpattern)]@[(true,Find_Theorems.Name (namefilter))]@unwanted_names)
      in map_filter (fn (factref,thm) => 
                          if  Thm.prop_of thm |> has_vars (* Remove plain definitions *)
                          (* then SOME (Facts.ref_name factref, thm) *)
                          then SOME (Facts.string_of_ref factref, thm)
                          else NONE) eqs
      end;
  
  fun get_all_thms namefilter ctxt =
    let val (_,thms) = Find_Theorems.find_theorems ctxt NONE (SOME 16000) true
                      ([(true,thmpattern),(false,badeqpattern),(false,undefpattern)]@[(true,Find_Theorems.Name (namefilter))]@unwanted_names)
      in map_filter (fn (factref,thm) => 
                          if  Thm.prop_of thm |> has_vars (* Remove plain definitions *) 
                          then 
                            if String.isPrefix namefilter (Facts.ref_name factref)
                            (* then SOME (Facts.ref_name factref, thm) *)
                            then SOME (Facts.string_of_ref factref, thm)
                            else NONE
                          else NONE) thms
      end;
  
end