theory ExtractLemmas  
  imports Main
begin
declare [[ML_print_depth=10000]]

ML_file "RoughSpecUtils.ML"
ML_file "Extract.ML";
ML_file "ExtractLemmas.ML";
ML_file "Utils.ML";

(* testing *)
(*
ML \<open>
val t1 = @{thm Binomial.binomial_mono};
Template.thm2template t1;
Long_Template.thm2template t1;
\<close>
*)
end
