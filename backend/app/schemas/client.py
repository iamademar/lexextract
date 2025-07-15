from pydantic import BaseModel, field_validator
from datetime import datetime

class ClientBase(BaseModel):
    name: str
    contact_name: str | None = None
    contact_email: str | None = None
    
    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    
    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Name cannot be empty')
        return v.strip() if v else v

class ClientRead(ClientBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True