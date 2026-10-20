"""Test stand-in for Hermes core's ``hermes_yaml``, used only when pytest runs outside Hermes.

It mirrors core's ``safe_load``: ruamel.yaml's safe loader, YAML 1.1, duplicate keys refused,
the C parser first and the pure parser when the C one rejects the document. Inside Hermes the
real module is imported instead.
"""

from typing import IO, Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError  # core exposes it under the same name


def _load(document: "str | bytes", *, pure: bool) -> Any:
    yaml = YAML(typ="safe", pure=pure)
    yaml.version = (1, 1)
    return yaml.load(document)


def safe_load(stream: "str | bytes | IO[str] | IO[bytes]") -> Any:
    document = stream if isinstance(stream, (str, bytes)) else stream.read()
    try:
        return _load(document, pure=False)
    except YAMLError:
        return _load(document, pure=True)
