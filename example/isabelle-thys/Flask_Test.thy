
theory Flask_Test
  imports Main
begin

(* Load the ML file *)
ML_file "GetTemplates.ML"

(* Example usage of Flask_API *)
ML_val ‹
  val terms = [
      Syntax.read_term @{context} "(+)"   (* Term for addition *)
    ];
  val response = Get_Templates.get_templates terms;
  writeln ("API Response: " ^ response);
›

end
