import os
from typing import Optional
from uuid import uuid4
import warnings

from isabelle_connector.isabelle_types import Theory


def _get_or_create_theory_name(theory_name: Optional[str]) -> str:
    return (
        "Temp" + str(uuid4()).replace("-", "") if theory_name is None else theory_name
    )


def get_working_dirs(dataset_dir):
    return [
        wd
        for wd in os.listdir(dataset_dir)
        if os.path.isdir(os.path.join(dataset_dir, wd))
    ]


def list_theory_files(root_dir):
    import glob

    theory_files = glob.glob(os.path.join(root_dir, "**/*.thy"), recursive=True)
    if not theory_files:
        warnings.warn(f"No theory files found in {root_dir}")
    return theory_files


def temp_theory(**kwargs):
    if "name" not in kwargs:
        kwargs["name"] = _get_or_create_theory_name(None)
    if "is_temp" not in kwargs:
        kwargs["is_temp"] = True
    return Theory(**kwargs)


def get_theory(theory_file, root_dir):
    root_dir = str(root_dir)  # TODO: is it better to keep root_dir as Path object?
    theory_name = theory_file.removesuffix(".thy").removeprefix(root_dir).strip("/")
    return Theory(
        name=theory_name,
        working_directory=root_dir,
        imports=[],
        queries=[],
        is_temp=False,
    )


def merge_thys(theories):
    theory = temp_theory(
        name="Merged" + _get_or_create_theory_name(None),
        working_directory=theories[0].working_directory,
        imports=[],
        queries=[],
        is_temp=True,
    )
    imports = set()
    for thy in theories:
        for imprt in thy.imports:
            imports.add(imprt)
        theory.queries.extend(thy.queries)
    theory.imports = list(imports)
    return theory


def flatten(l: list) -> list:
    return [item for sublist in l for item in sublist]


def path_to_theory_name(path):
    import re

    # remove all special characters
    return re.sub(r"\W+", "_", path).strip("_")
