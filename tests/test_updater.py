"""Update-checker unit tests."""

from __future__ import annotations

from clawdeck.services.updater import is_newer, parse_semver


def test_parse_semver_basics():
    assert parse_semver("1.2.3") == (1, 2, 3)
    assert parse_semver("v1.2.3") == (1, 2, 3)
    assert parse_semver("V1.2.3") == (1, 2, 3)
    assert parse_semver("1.2") == (1, 2, 0)


def test_parse_semver_strips_suffix():
    assert parse_semver("1.2.3-alpha") == (1, 2, 3)
    assert parse_semver("1.2.3+build.1") == (1, 2, 3)


def test_parse_semver_rejects_garbage():
    assert parse_semver("garbage") is None
    assert parse_semver("") is None
    assert parse_semver("v") is None


def test_is_newer_true():
    assert is_newer("v0.3.0", "0.2.5") is True
    assert is_newer("1.0.0", "0.9.9") is True


def test_is_newer_false():
    assert is_newer("0.2.0", "0.3.0") is False
    assert is_newer("0.1.0", "0.1.0") is False
    assert is_newer("bogus", "0.1.0") is False
