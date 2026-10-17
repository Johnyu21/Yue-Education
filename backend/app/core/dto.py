"""Strict HTTP DTOs. Datetimes must include an offset."""
from pydantic import BaseModel as PydanticBaseModel, ConfigDict
class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")
