from __future__ import annotations

import pytest

from apps.core.problems import Forbidden, InvalidParameter
from apps.proxy.validators import validate_proxy_url


def test_validate_proxy_url_rejects_bad_scheme():
    with pytest.raises(InvalidParameter):
        validate_proxy_url("ftp://example.com/x")


def test_validate_proxy_url_rejects_private_ip(settings):
    settings.API_IDEE = {**settings.API_IDEE, "PROXY_ALLOWED_HOSTS": [], "PROXY_ALLOWED_PORTS": []}
    with pytest.raises(Forbidden):
        validate_proxy_url("http://127.0.0.1/x")


def test_validate_proxy_url_rejects_embedded_credentials():
    with pytest.raises(InvalidParameter):
        validate_proxy_url("http://user:pass@example.com/x")
