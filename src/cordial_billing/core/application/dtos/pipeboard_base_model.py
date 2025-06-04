import re
from typing import Any

from pydantic import BaseModel


def to_snake(s: str) -> str:
    """Converte camelCase ou PascalCase para snake_case."""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', s).lower()

class PDBaseModel(BaseModel):
    """
    BaseModel padrão para Pipedrive:
    - Converte aliases de camelCase para snake_case.
    - Permite campos extras, armazenando-os em `custom_fields`.
    """
    custom_fields: dict[str, Any] = {}

    model_config = {
        "alias_generator": to_snake,
        "populate_by_name": True,
        "extra": "allow",
    }
