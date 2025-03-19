from enum import Enum

from pydantic import BaseModel, field_validator


class DOC_STATUS(str, Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentInfo(BaseModel):
    client_id: str
    collection: str
    name: str
    doc_id: str
    status: str
    reason: str | None = None

    @field_validator("status")
    def validate_status(cls, v):
        if v not in DOC_STATUS.__members__.values():
            raise ValueError(f"Invalid document status: {v}")
        return v
