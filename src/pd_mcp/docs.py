from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path


DOCS_PATH = Path(__file__).with_name("pd_docs.json")


@lru_cache(maxsize=1)
def load_docs() -> list[dict]:
    return json.loads(DOCS_PATH.read_text())


@lru_cache(maxsize=1)
def docs_by_name() -> dict[str, dict]:
    return {entry["name"]: entry for entry in load_docs()}


def list_object_names() -> list[str]:
    return sorted(docs_by_name())


def get_object_doc(name: str) -> dict | None:
    return docs_by_name().get(name)


def search_objects(query: str) -> list[dict]:
    query = query.lower().strip()
    if not query:
        return load_docs()
    results = []
    for entry in load_docs():
        haystack = " ".join(
            [
                entry["name"],
                entry.get("description", ""),
                " ".join(entry.get("arguments", [])),
                " ".join(entry.get("inlets", [])),
                " ".join(entry.get("outlets", [])),
            ]
        ).lower()
        if query in haystack:
            results.append(entry)
    return results
