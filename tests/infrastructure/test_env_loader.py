"""Tests for the stdlib .env loader."""

from __future__ import annotations

from pathlib import Path

from orion.infrastructure.env import load_env, parse_env_line


def test_parse_env_line_basic() -> None:
    assert parse_env_line("FOO=bar") == ("FOO", "bar")
    assert parse_env_line("FOO=with spaces") == ("FOO", "with spaces")
    assert parse_env_line('FOO="quoted value"') == ("FOO", "quoted value")
    assert parse_env_line("FOO='single'") == ("FOO", "single")
    assert parse_env_line("export FOO=bar") == ("FOO", "bar")


def test_parse_env_line_ignores_junk() -> None:
    assert parse_env_line("") is None
    assert parse_env_line("# comment") is None
    assert parse_env_line("NO_EQUALS_SIGN") is None
    assert parse_env_line("=novalue") is None


def test_parse_env_line_strips_inline_comment() -> None:
    assert parse_env_line("FOO=bar # trailing") == ("FOO", "bar")
    assert parse_env_line('FOO="not # stripped"') == ("FOO", "not # stripped")


def test_load_env_missing_file_is_noop(tmp_path: Path) -> None:
    assert load_env(tmp_path / "missing.env", environ={}) == {}


def test_load_env_applies_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("A_KEY=alpha\nB_KEY=beta\n", encoding="utf-8")
    applied = load_env(env_file, environ={})
    assert applied == {"A_KEY": "alpha", "B_KEY": "beta"}


def test_load_env_never_overrides_existing(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("A_KEY=new\n", encoding="utf-8")
    applied = load_env(env_file, environ={"A_KEY": "existing"})
    assert applied == {}
    assert load_env(env_file, override=True, environ={"A_KEY": "existing"}) == {"A_KEY": "new"}


def test_load_env_skips_malformed_lines(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GOOD=1\nBROKEN\n#comment\n\nALSO_GOOD=2\n", encoding="utf-8")
    assert load_env(env_file, environ={}) == {"GOOD": "1", "ALSO_GOOD": "2"}
