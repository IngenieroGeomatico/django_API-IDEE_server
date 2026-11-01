"""Fixtures compartidas."""

from __future__ import annotations

import pytest
from django.test import RequestFactory

from apps.core.params import Parametros


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


@pytest.fixture
def make_params():
    def factory(query_string: str) -> Parametros:
        return Parametros.desde_query_string(query_string)

    return factory


@pytest.fixture
def make_request(rf):
    def factory(path: str = "/", *, accept: str | None = None, **headers: str):
        extra = {f"HTTP_{key.upper().replace('-', '_')}": value for key, value in headers.items()}
        if accept is not None:
            extra["HTTP_ACCEPT"] = accept
        return rf.get(path, **extra)

    return factory
