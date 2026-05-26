from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredResponseGenerator(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        output_model: type[T],
    ) -> T: ...
