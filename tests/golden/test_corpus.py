"""Valida la estructura del corpus golden (sin red)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CORPUS = Path(__file__).parent / "urls.yaml"

REQUIRED_KEYS = {"id", "method", "path", "tags", "expect"}
VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


@pytest.fixture(scope="module")
def corpus() -> dict:
    with CORPUS.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_corpus_tiene_entradas_suficientes(corpus):
    assert len(corpus["urls"]) >= 40


def test_identificadores_unicos(corpus):
    ids = [entry["id"] for entry in corpus["urls"]]
    assert len(ids) == len(set(ids))


def test_entradas_bien_formadas(corpus):
    for entry in corpus["urls"]:
        assert set(entry) >= REQUIRED_KEYS, entry
        assert entry["method"] in VALID_METHODS, entry
        assert entry["path"].startswith("/"), entry
        assert isinstance(entry["tags"], list) and entry["tags"], entry
        assert isinstance(entry["expect"], dict), entry


def test_cubre_todas_las_familias(corpus):
    tags = {tag for entry in corpus["urls"] for tag in entry["tags"]}
    assert {
        "viewer",
        "actions",
        "proxy",
        "database",
        "email",
        "static",
        "legacy",
    } <= tags
