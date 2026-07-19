"""Small, stable failure shapes shared by the CLI and gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Fab7Error(Exception):
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.context}


@dataclass
class Result:
    errors: list[Fab7Error] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def fail(self, code: str, message: str, **context: Any) -> None:
        self.errors.append(Fab7Error(code, message, context))

    def to_dict(self, **extra: Any) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [error.to_dict() for error in self.errors],
            **extra,
        }
