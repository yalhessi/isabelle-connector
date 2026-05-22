theory Extract
  imports Main
begin
declare [[ML_print_depth=10000]]

ML_file "Extract.ML";
ML_file "ExtractLemmas.ML";
ML_file "Utils.ML";

end