import json
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExportFormat(str, Enum):
    Markdown = "md"
    HTML = "html"


class DOC_STATUS(str, Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


# Playbook definition type, either a dict or a list of tuples both mapping to an OrderedDict


class Playbook(BaseModel):
    id: str
    name: str
    version: int = 1
    definition: dict[str, dict[str, Any]] | list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("definition", mode="before")
    @classmethod
    def ensure_ordered_dict(cls, v):
        # The playbook definition can be given as a list of objects, but we always
        # convert to a dict (since python 3.7+ maintains insertion order)
        if isinstance(v, list):
            return {item["attribute"]: {k: v_ for k, v_ in item.items() if k != "attribute"} for item in v}
        elif isinstance(v, dict):
            return v
        else:
            raise ValueError(f"Invalid type for Playbook definition: {type(v)}")

    @classmethod
    def from_json_file(cls, file_path: Path | str):
        fpath = Path(file_path)
        with fpath.open("r", encoding="utf-8") as f:
            data = json.load(
                f,
            )

        return cls(**data)


class DBDocumentInfo(BaseModel):
    id: str | UUID
    sha1: str
    name: str
    client_id: str
    collection: str
    created_at: str
    status: str
    reason: str | None = None
    run_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @field_validator("status")
    def validate_status(cls, v):
        if v not in DOC_STATUS.__members__.values():
            raise ValueError(f"Invalid document status: {v}")
        return v
