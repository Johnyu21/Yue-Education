from uuid import UUID
from pydantic import Field
from app.core.dto import BaseModel
class LeadImportIn(BaseModel):
    object_key: str = Field(min_length=1,max_length=500)
    sheet_name: str | None = None
    mapping: dict[str,str]
    request_key: UUID
    fingerprint: str | None = None
    confirmed: bool = False
