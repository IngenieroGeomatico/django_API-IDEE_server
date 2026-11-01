from __future__ import annotations

from apps.core.limits import Limits, load_limits


def test_load_limits_returns_limits():
    limits = load_limits()
    assert isinstance(limits, Limits)
    assert limits.max_layers > 0


def test_limits_from_settings_override(settings):
    settings.API_IDEE = {**settings.API_IDEE, "MAX_LAYERS": 7}
    limits = Limits.from_settings()
    assert limits.max_layers == 7
