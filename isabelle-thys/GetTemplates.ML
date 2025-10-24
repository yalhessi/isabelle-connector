structure Get_Templates = struct
  (* Helper function to escape JSON strings *)
  fun json_escape s = String.translate (fn #"\"" => "\\\"" | c => str c) s

  (* Convert list of function names into a JSON payload *)
  fun create_json_payload function_names =
    let
      val json_names = map (fn name => "\"" ^ json_escape name ^ "\"") function_names
      val json_body = "{ \"function_names\": [" ^ String.concatWith ", " json_names ^ "] }"
    in
      json_body
    end

  (* Call Flask API using curl and return response *)
  fun call fns =
    let
      (* Prepare JSON payload *)
      val json_payload = create_json_payload fns 

      (* Shell command to call our API API using curl *)
      (*NOTE THIS URL IS CURRENTLY HARDCODED*)
      val curl_command = "curl -s -X POST -H \"Content-Type: application/json\" " ^
                         "-d '" ^ json_payload ^ "' " ^
                         "http://127.0.0.1:5000/generate_templates"

      val result = Isabelle_System.bash_output curl_command |> fst
    in
      result
    end

  (* Main function: Accept Terms, check their type, and call API *)
  fun get_templates terms =
    let
      (* Filter and validate constants of function type *)
      fun is_fun_const t =
        case Term.head_of t of
          Const (name, Type ("fun", _)) => SOME name
        | _ => NONE

      val function_names = 
        List.mapPartial is_fun_const terms

      (* Error if no valid function constants are found *)
      val _ = if null function_names then
                error "No valid function constants of type 'fun' provided."
              else ()

      (* Call the API *)
      val response = call function_names
    in
      response
    end
end;
