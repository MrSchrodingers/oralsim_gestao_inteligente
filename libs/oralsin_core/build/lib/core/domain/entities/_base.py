from dataclasses import asdict, fields, is_dataclass
from typing import Any, TypeVar

T = TypeVar("T")

class EntityMixin:
    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """
        Cria uma instância da entidade a partir de um dict.
        """
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """
        Converte a entidade em dict, recursivamente se for dataclass.
        """
        return asdict(self)

    @classmethod
    def from_model(cls: type[T], model: Any) -> T:
        """
        Cria uma entidade a partir de um modelo Django.
        Usa os campos da dataclass para extrair atributos do model.
        """
        if not is_dataclass(cls):
            raise TypeError(f"{cls.__name__} deve ser um dataclass")
        data: dict[str, Any] = {}
        for f in fields(cls):
            data[f.name] = getattr(model, f.name)
        return cls(**data)
