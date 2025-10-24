# import os
# import dotenv
# import multiprocessing

# dotenv_loaded = False
# def load_env():
#     global dotenv_loaded
#     if not dotenv_loaded:
#         dotenv.load_dotenv('.env')
#         dotenv_loaded = True

# def getenv(*args, **kwargs):
#     load_env()
#     return os.getenv(*args, **kwargs)

# def get_run_id(model_name, dataset_name, dataset_config):
#     def extract_name(name):
#         return name.split("/")[-1] if "/" in name else name

#     dataset_name = extract_name(dataset_name)
#     model_name = extract_name(model_name)
#     return f"{dataset_name}-{dataset_config}-{model_name}"


# def get_isabelle_dir():
#     return getenv("ISABELLE_DIR", "/isabelle")

# def get_output_dir():
#     return getenv("OUTPUT_DIR", "/output")

# def get_pisa_port():
#     return int(getenv("PISA_PORT", 8000))

# def current_process_offset():
#     return multiprocessing.current_process()._identity[0]

# def flatten_dict(d_list: list[dict]) -> dict:
#     return {k: v for d in d_list for k, v in d.items()}

def flatten(l: list) -> list:
    return [item for sublist in l for item in sublist]

# def prepare_notebook():
#     import isabelle_connector.reload_recursive    
#     import nest_asyncio
#     nest_asyncio.apply()
#     import warnings
#     warnings.filterwarnings(action="once")
#     # import multiprocessing
#     # multiprocessing.set_start_method("spawn")
    
def path_to_theory_name(path):
    import re

    # remove all special characters
    return re.sub(r"\W+", "_", path).strip("_")