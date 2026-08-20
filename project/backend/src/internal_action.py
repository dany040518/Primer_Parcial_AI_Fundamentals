"""Tipo compartido para una acción interna del agente (antes de traducir al contrato)."""

from __future__ import annotations

from typing import Any, NamedTuple


class InternalAction(NamedTuple):
    kind: str
    target: str
    extra: Any
    cost: int
