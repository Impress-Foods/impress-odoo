import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

_logger = logging.getLogger(__name__)


class DominoPrinter(BaseModel):
    id: int
    name: str
    active: bool


class DominoField(BaseModel):
    name: str
    type: str | None = None
    size: int | None = None


class DominoBufferSchema(BaseModel):
    fields: list[DominoField]


class DominoLabel(BaseModel):
    id: int
    name: str
    buffer_schema: DominoBufferSchema = Field(default=DominoBufferSchema(fields=[]))
    printer_ids: list[int]

    @field_validator("buffer_schema", mode="before")
    @classmethod
    def catch_empty_buffer_schema(cls, value: Any) -> dict | DominoBufferSchema:
        if isinstance(value, (dict, DominoBufferSchema)):
            return value
        return DominoBufferSchema(fields=[])
