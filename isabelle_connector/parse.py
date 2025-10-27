import ast
import json
import warnings

from isabelle_client.socket_communication import IsabelleResponse
from isabelle_connector.isabelle_types import IsabelleMessage, Theory


def parse_ml_value(message):
    # clean up the message
    cleaned_message = message.replace("true", "True").replace("false", "False")
    val_name, val_rest = cleaned_message.split("=", 1)
    val_value, val_type = (elem.strip() for elem in val_rest.rsplit(":", 1))
    try:
        # silence syntax warnings during literal_eval (e.g., for \<open>)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SyntaxWarning)
            val = ast.literal_eval(val_value)
        return val, True
    except Exception as e:
        return cleaned_message, False


def is_ml_value(message):
    return message.startswith("val ")


def extract_messages_from_responses(
    thys: list[Theory], responses: list[IsabelleResponse]
) -> dict[Theory, list[IsabelleMessage]]:
    messages = {thy: [] for thy in thys}
    thy_dict = {thy.name: thy for thy in thys}
    for response in responses:
        match response.response_type:
            case "FINISHED":
                data = json.loads(response.response_body)
                for node in data["nodes"]:
                    name = node["theory_name"].removeprefix("Draft.")
                    # Skip output of imported theories
                    if name not in thy_dict:
                        continue
                    current_thy = thy_dict[name]
                    current_messages = node["messages"]
                    current_thy.write_cache(current_messages)
                    messages[current_thy] = current_messages
            case "ERROR" | "FAILED":
                warnings.warn(f"Received ERROR response: {response.response_body}")
            case _:
                continue
    return messages


def extract_ml_values_from_messages(messages: dict[Theory, list[IsabelleMessage]]):
    values, errs = {thy: [] for thy in messages}, {thy: [] for thy in messages}
    for thy in messages:
        for message in messages[thy]:
            match message["kind"]:
                case "writeln":
                    clean_message = message["message"].replace("\n", " ")
                    if is_ml_value(clean_message):
                        ml_val, success = parse_ml_value(clean_message)
                        if success:
                            values[thy].append(ml_val)
                case "error":
                    errs[thy].append(message["message"])
    return values, errs
