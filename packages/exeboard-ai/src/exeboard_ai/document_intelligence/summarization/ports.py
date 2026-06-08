from typing import ClassVar, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T", bound=BaseModel)


class StructuredGenerationRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    operation_name: str
    prompt_name: str
    prompt_version: str
    output_schema_name: str
    output_schema_version: str
    prompt: str
    context: BaseModel | None = None
    replay_key: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "operation_name",
        "prompt_name",
        "prompt_version",
        "output_schema_name",
        "output_schema_version",
        "prompt",
    )
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("replay_key")
    @classmethod
    def _replay_key_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and (not value or not value.strip()):
            raise ValueError("replay_key must not be empty")
        return value

    @field_validator("metadata")
    @classmethod
    def _metadata_must_not_contain_empty_keys_or_values(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        if any(not key or not key.strip() for key in value):
            raise ValueError("metadata keys must not be empty")
        if any(not metadata_value or not metadata_value.strip() for metadata_value in value.values()):
            raise ValueError("metadata values must not be empty")
        return value


class StructuredResponseGenerator(Protocol):
    def generate(
        self,
        *,
        request: StructuredGenerationRequest,
        output_model: type[T],
    ) -> T: ...
