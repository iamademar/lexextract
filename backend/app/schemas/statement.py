from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List

class StatementBase(BaseModel):
    client_id: int
    progress: int = 0
    status: str = 'pending'
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        allowed_statuses = ['pending', 'processing', 'completed', 'failed']
        if v not in allowed_statuses:
            raise ValueError(f'Status must be one of: {", ".join(allowed_statuses)}')
        return v
    
    @field_validator('progress')
    @classmethod
    def validate_progress(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Progress must be between 0 and 100')
        return v

class StatementCreate(StatementBase):
    pass

class StatementRead(StatementBase):
    id: int
    uploaded_at: datetime
    file_path: str
    ocr_text: Optional[str] = None
    
    class Config:
        from_attributes = True

class StatementProgress(BaseModel):
    progress: int
    status: str
    
    class Config:
        from_attributes = True

class TransactionRead(BaseModel):
    id: int
    date: datetime
    payee: str
    amount: float
    type: str
    balance: Optional[float] = None
    currency: str = "GBP"
    
    class Config:
        from_attributes = True