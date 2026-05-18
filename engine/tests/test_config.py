from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from engine.config import SessionConfig, load_config


def _base() -> dict:
    return {
        "credentials": {"stake_access_token": "abc123"},
        "session": {
            "currency": "btc",
            "top_target_usd": 10000,
            "secondary_target_usd": 3000,
            "stop_loss": {"enabled": False, "mode": "fixed_floor", "value": 100},
            "persona": "steady",
            "games_enabled": ["dice", "keno", "limbo"],
            "vibes": {
                "text": "lucky",
                "lucky_numbers": [7, 23],
                "bake_into_seed": True,
                "influence_game_choice": True,
            },
        },
    }


def test_valid_config_parses():
    cfg = SessionConfig.model_validate(_base())
    assert cfg.session.currency == "btc"
    assert cfg.session.top_target_usd == Decimal("10000")
    assert cfg.session.games_enabled == ["dice", "keno", "limbo"]


def test_placeholder_token_rejected():
    d = _base()
    d["credentials"]["stake_access_token"] = "REPLACE_ME"
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_secondary_must_be_below_top():
    d = _base()
    d["session"]["secondary_target_usd"] = 10000
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_unknown_currency_rejected():
    d = _base()
    d["session"]["currency"] = "xrp"
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_phase1_persona_only_steady():
    d = _base()
    d["session"]["persona"] = "degen"
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_phase1_games_restricted():
    d = _base()
    d["session"]["games_enabled"] = ["dice", "plinko"]
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_duplicate_games_rejected():
    d = _base()
    d["session"]["games_enabled"] = ["dice", "dice"]
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_stop_loss_value_must_be_positive_when_enabled():
    d = _base()
    d["session"]["stop_loss"] = {"enabled": True, "mode": "fixed_floor", "value": 0}
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_stop_loss_pct_bounds():
    d = _base()
    d["session"]["stop_loss"] = {"enabled": True, "mode": "pct_of_start", "value": 150}
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)


def test_load_config_from_yaml(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(_base()))
    cfg = load_config(p)
    assert cfg.session.persona == "steady"


def test_env_var_overrides_placeholder(tmp_path: Path, monkeypatch):
    """STAKE_ACCESS_TOKEN env var replaces a placeholder in the YAML."""
    d = _base()
    d["credentials"]["stake_access_token"] = "REPLACE_ME"
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(d))
    monkeypatch.setenv("STAKE_ACCESS_TOKEN", "real-token-from-env")
    cfg = load_config(p)
    assert cfg.credentials.stake_access_token == "real-token-from-env"


def test_env_var_overrides_yaml_token(tmp_path: Path, monkeypatch):
    """Env var takes precedence even when the YAML has a real-looking token."""
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(_base()))
    monkeypatch.setenv("STAKE_ACCESS_TOKEN", "env-wins")
    cfg = load_config(p)
    assert cfg.credentials.stake_access_token == "env-wins"


def test_token_override_arg_beats_env_var(tmp_path: Path, monkeypatch):
    """Explicit token_override arg beats the env var."""
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(_base()))
    monkeypatch.setenv("STAKE_ACCESS_TOKEN", "env-token")
    cfg = load_config(p, token_override="explicit-token")
    assert cfg.credentials.stake_access_token == "explicit-token"


def test_empty_env_var_falls_back_to_yaml(tmp_path: Path, monkeypatch):
    """An empty env var is treated as unset; YAML token is used instead."""
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(_base()))
    monkeypatch.setenv("STAKE_ACCESS_TOKEN", "")
    cfg = load_config(p)
    assert cfg.credentials.stake_access_token == "abc123"


def test_negative_lucky_numbers_rejected():
    d = _base()
    d["session"]["vibes"]["lucky_numbers"] = [-1, 7]
    with pytest.raises(ValidationError):
        SessionConfig.model_validate(d)
