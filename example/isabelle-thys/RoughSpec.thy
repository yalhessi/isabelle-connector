theory RoughSpec
  imports Main
begin

ML_file "RoughSpecUtils.ML"
ML_file "Utils.ML"
ML_file "AbstractLemma.ML"
ML_file "RoughSpec.ML"

ML \<open>

  (* For testing *)
  fun rsPretty multi poly ts funs = map (Syntax.pretty_term @{context}) (RoughSpec.conjecture @{context} multi poly ts funs)
  fun prettyCands multi poly ts funs = map (Syntax.pretty_term @{context}) 
                                (RoughSpec.lemmanaid_candidates @{context} multi poly ts funs)
\<close>

end