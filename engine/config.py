"""Session config schema and loader.

YAML on disk → validated `SessionConfig` object. Validation errors halt before
any Stake API call is made.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

Currency = Literal["btc", "eth", "sol", "usdt", "ltc", "doge", "trx"]
Persona = Literal["steady"]  # Phase 1: steady only. Phase 2 widens this.
Game = Literal["dice", "keno", "limbo"]  # Phase 1: 3 games only.
StopLossMode = Literal["fixed_floor", "pct_of_start", "session_loss_cap"]


class Credentials(BaseModel):
    stake_access_token: str = Field(min_length=1)

    @field_validator("stake_access_token")
    @classmethod
    def _reject_placeholder(cls, v: str) -> str:
        if v.strip().upper() in {"REPLACE_ME", "REPLACE-ME", ""}:
            raise ValueError("stake_access_token is not set — paste your real x-access-token")
        return v


class StopLoss(BaseModel):
    enabled: bool = False
    mode: StopLossMode = "fixed_floor"
    value: Decimal = Decimal("0")

    @model_validator(mode="after")
    def _value_positive_when_enabled(self) -> "StopLoss":
        if self.enabled and self.value <= 0:
            raise ValueError("stop_loss.value must be > 0 when enabled")
        if self.mode == "pct_of_start" and self.enabled and not (0 < self.value < 100):
            raise ValueError("stop_loss.value must be between 0 and 100 for pct_of_start")
        return self


class Vibes(BaseModel):
    text: str = ""
    lucky_numbers: list[int] = Field(default_factory=list)
    bake_into_seed: bool = True
    influence_game_choice: bool = True

    @field_validator("lucky_numbers")
    @classmethod
    def _numbers_positive(cls, v: list[int]) -> list[int]:
        if any(n < 0 for n in v):
            raise ValueError("lucky_numbers must be non-negative")
        return v


class Session(BaseModel):
    currency: Currency
    top_target_usd: Decimal = Field(gt=0)
    secondary_target_usd: Decimal = Field(gt=0)
    stop_loss: StopLoss = Field(default_factory=StopLoss)
    persona: Persona
    games_enabled: list[Game] = Field(min_length=1)
    vibes: Vibes = Field(default_factory=Vibes)

    @field_validator("games_enabled")
    @classmethod
    def _games_unique(cls, v: list[Game]) -> list[Game]:
        if len(set(v)) != len(v):
            raise ValueError("games_enabled contains duplicates")
        return v

    @model_validator(mode="after")
    def _secondary_below_top(self) -> "Session":
        if self.secondary_target_usd >= self.top_target_usd:
            raise ValueError("secondary_target_usd must be less than top_target_usd")
        return self


class SessionConfig(BaseModel):
    credentials: Credentials
    session: Session


def load_config(path: str | Path, token_override: str | None = None) -> SessionConfig:
    """Parse a YAML file into a validated SessionConfig.

    Token resolution order (first non-empty wins):
      1. token_override argument   — supplied by main.py after an interactive prompt
      2. STAKE_ACCESS_TOKEN env var — for CI / headless runs
      3. credentials.stake_access_token in the YAML
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"config root must be a mapping, got {type(raw).__name__}")

    token = (
        token_override
        or os.environ.get("STAKE_ACCESS_TOKEN", "").strip()
        or ""
    )
    if token:
        raw.setdefault("credentials", {})["stake_access_token"] = token

    return SessionConfig.model_validate(raw)
