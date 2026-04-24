# Config parser for Kidde PG3x node server
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class KiddeConfig:
    email: str = ""
    password: str = ""
    cookie_file: str = ""

def build_config(custom_params: dict) -> KiddeConfig:
    params = custom_params or {}
    return KiddeConfig(
        email=str(params.get("EMAIL", "")).strip(),
        password=str(params.get("PASSWORD", "")).strip(),
        cookie_file=str(params.get("COOKIE_FILE", "")).strip(),
    )
