import json
import os
from typing import Any


ENV_KEY = 'JG_GLOBAL_STATE'


def load() -> dict:
    try:
        return json.loads(os.environ[ENV_KEY])
    except KeyError:
        return dict()


def save(state) -> None:
    os.environ[ENV_KEY] = json.dumps(state)


def set(name, value) -> None:
    data = load()
    data[name] = value
    save(data)


def get(*args) -> Any:
    return load().get(*args)