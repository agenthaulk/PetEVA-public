"""Lifecycle providers for the lightweight PetEVA runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PetState:
    enabled: bool
    unit_id: str = "eva-01"
    reason: str = ""


class PetStateProvider(Protocol):
    def read_state(self) -> PetState:
        """Return the current desired pet state."""


class LocalSwitchFileProvider:
    """Read the initial lifecycle signal from a local file.

    Supported switch formats:
    - JSON: {"enabled": true, "unit": "eva-01"}
    - text: enabled / disabled / true / false / 1 / 0
    """

    def __init__(self, switch_file: Path, default_unit_id: str = "eva-01"):
        self.switch_file = switch_file
        self.default_unit_id = default_unit_id

    def read_state(self) -> PetState:
        if not self.switch_file.exists():
            return PetState(
                False,
                unit_id=self.default_unit_id,
                reason=f"switch file missing: {self.switch_file}",
            )

        raw_value = self.switch_file.read_text(encoding="utf-8").strip()
        if not raw_value:
            return PetState(False, unit_id=self.default_unit_id, reason="switch file is empty")

        if raw_value.startswith("{"):
            return self._read_json(raw_value)

        normalized = raw_value.lower()
        if normalized in {"enabled", "true", "1", "on", "yes"}:
            return PetState(True, unit_id=self.default_unit_id, reason="local switch enabled")
        if normalized in {"disabled", "false", "0", "off", "no"}:
            return PetState(False, unit_id=self.default_unit_id, reason="local switch disabled")

        return PetState(
            False,
            unit_id=self.default_unit_id,
            reason=f"unknown switch value: {raw_value}",
        )

    def _read_json(self, raw_value: str) -> PetState:
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError as error:
            return PetState(
                False,
                unit_id=self.default_unit_id,
                reason=f"switch JSON is invalid: {error}",
            )

        enabled = bool(payload.get("enabled", False))
        unit_id = str(payload.get("unit", self.default_unit_id))
        reason = "local switch enabled" if enabled else "local switch disabled"
        return PetState(enabled, unit_id=unit_id, reason=reason)


class CodexDesktopStateProvider:
    """Future provider for Codex Desktop state.

    This intentionally does not inspect Codex Desktop internals yet. The first
    runtime version uses LocalSwitchFileProvider so we do not guess where Codex
    stores pet state.
    """

    def read_state(self) -> PetState:
        return PetState(False, reason="Codex Desktop state provider is not implemented")


def write_local_switch(switch_file: Path, enabled: bool, unit_id: str = "eva-01") -> None:
    switch_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"enabled": enabled, "unit": unit_id}
    switch_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
