import json
import os
import warnings

from isabelle_client.socket_communication import IsabelleResponse

from isabelle_connector.isabelle_types import IsabelleMessage, Theory


def extract_messages_from_responses(
    thys: list[Theory], responses: list[IsabelleResponse]
) -> dict[Theory, list[IsabelleMessage]]:
    messages = {thy: [] for thy in thys}
    thy_dict = {thy.name: thy for thy in thys}
    thy_file_dict = {os.path.join(thy.working_directory, f"{thy.name}.thy"): thy for thy in thys}
    for response in responses:
        match response.response_type:
            case "FINISHED":
                data = json.loads(response.response_body)
                pending_errors: dict[Theory, list[IsabelleMessage]] = {thy: [] for thy in thys}
                for error in data.get("errors", []):
                    error_file = error.get("pos", {}).get("file")
                    if error_file is None:
                        continue
                    current_thy = thy_file_dict.get(error_file)
                    if current_thy is not None:
                        pending_errors[current_thy].append(error)
                for node in data["nodes"]:
                    name = node["theory_name"].removeprefix("Draft.")
                    # Skip output of imported theories
                    if name not in thy_dict:
                        continue
                    current_thy = thy_dict[name]
                    current_messages = list(node["messages"])
                    current_messages.extend(pending_errors[current_thy])
                    pending_errors[current_thy] = []
                    status = node.get("status", {})
                    if not current_messages and not status.get("ok", True):
                        current_messages.append(
                            {
                                "kind": "error",
                                "message": (
                                    "Theory processing failed without an explicit "
                                    f"message: {current_thy.name}"
                                ),
                            }
                        )
                    current_thy.write_cache(current_messages)
                    messages[current_thy] = current_messages
                for current_thy, current_errors in pending_errors.items():
                    if not current_errors:
                        continue
                    current_messages = list(messages[current_thy])
                    current_messages.extend(current_errors)
                    current_thy.write_cache(current_messages)
                    messages[current_thy] = current_messages
            case "ERROR" | "FAILED":
                warnings.warn(f"Received ERROR response: {response.response_body}")
            case _:
                continue
    return messages
