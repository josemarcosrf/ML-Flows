import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, field_validator


class ExportFormat(str, Enum):
    Markdown = "md"
    HTML = "html"


class DOC_STATUS(str, Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class Playbook(BaseModel):
    id: str
    name: str
    version: int = 1
    definition: dict[str, dict[str, str | list[str]]]

    @classmethod
    def from_json_file(cls, file_path: Path | str):
        fpath = Path(file_path)
        with fpath.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


class DocumentInfo(BaseModel):
    id: str
    name: str
    client_id: str
    collection: str
    created_at: str
    status: str
    reason: str | None = None

    @field_validator("status")
    def validate_status(cls, v):
        if v not in DOC_STATUS.__members__.values():
            raise ValueError(f"Invalid document status: {v}")
        return v
