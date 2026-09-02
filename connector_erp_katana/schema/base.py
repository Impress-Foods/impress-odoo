from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class BaseKatanaModel(BaseModel):
    model_config = ConfigDict(serialize_by_alias=True)

    record_id: int = Field(alias="id")
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)
    archived_at: datetime | None = None
