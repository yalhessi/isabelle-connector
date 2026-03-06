from functools import wraps
import hashlib
import time
from typing import Callable

from isabelle_connector.isabelle_types import Theory, TheoryConfig
from isabelle_connector.utils import temp_theory


def timing(f):
    def wrap(*args, **kw):
        ts = time.time()
        result = f(*args, **kw)
        te = time.time()
        print(f"func:{f.__name__} took: {te - ts} sec")
        return result

    return wrap


def _build_fingerprint(*args, **kwargs) -> str:
    payload = repr((args, kwargs))
    return hashlib.sha256(payload.encode("utf8")).hexdigest()


def theory_builder(prefix: str):
    def decorator(builder: Callable[..., str]):
        @wraps(builder)
        def wrapper(*args, **kwargs) -> Theory:
            theory_config: TheoryConfig = kwargs["theory_config"]

            theory_name = f"{prefix}_{_build_fingerprint(*args, **kwargs)}"
            query = builder(*args, **kwargs)

            theory_kwargs = {
                "name": theory_name,
                "imports": theory_config.imports,
                "working_directory": theory_config.working_directory,
                "session": theory_config.session,
            }
            thy = temp_theory(**theory_kwargs)
            thy.add_ml_block(query)
            return thy

        return wrapper

    return decorator
