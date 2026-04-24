# Config parser for Kidde PG3x node server
from dataclasses import dataclass

@dataclass
class KiddeConfig:
    email: str = ""
    password: str = ""

def build_config(custom_params: dict) -> KiddeConfig:
    params = custom_params or {}
    return KiddeConfig(
        email=str(params.get("EMAIL", "")).strip(),
        password=str(params.get("PASSWORD", "")).strip(),
    )
