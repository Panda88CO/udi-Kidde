# Config parser for Kidde PG3x node server
from dataclasses import dataclass

@dataclass
class KiddeConfig:
    email: str = ""
    password: str = ""
    temp_unit: str = "F"


def _normalize_temp_unit(raw_value) -> str:
    value = str(raw_value or "").strip().upper()
    if value in {"F", "FAHRENHEIT"}:
        return "F"
    if value in {"C", "CELSIUS"}:
        return "C"
    return "F"

def build_config(custom_params: dict) -> KiddeConfig:
    params = custom_params or {}
    return KiddeConfig(
        email=str(params.get("EMAIL", "")).strip(),
        password=str(params.get("PASSWORD", "")).strip(),
        temp_unit=_normalize_temp_unit(params.get("TEMP_UNIT", "F")),
    )
