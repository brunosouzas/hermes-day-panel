"""Test stand-in for Hermes core's ``hermes_yaml``, used only when pytest runs outside Hermes.

It keeps the core policy the plugin relies on: ruamel.yaml's safe loader, YAML 1.1,
duplicate keys refused. Inside Hermes the real module is imported instead.
"""

from typing import IO, Any

from ruamel.yaml import YAML


def safe_load(stream: "str | bytes | IO[str] | IO[bytes]") -> Any:
    yaml = YAML(typ="safe", pure=True)
    yaml.version = (1, 1)
    return yaml.load(stream)
