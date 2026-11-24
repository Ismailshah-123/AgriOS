"""Data-origin labels used on every stored measurement (CLAUDE.md hard rule 3)."""

from enum import StrEnum


class DataOrigin(StrEnum):
    MEASURED = "measured"
    FARMER_ENTERED = "farmer_entered"
    RETRIEVED = "retrieved"
    INFERRED = "inferred"
    SIMULATED = "simulated"
