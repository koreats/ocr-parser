from pydantic import BaseModel, Field
from typing import Optional

class InvoiceFields(BaseModel):
    supplier: Optional[str] = Field(None)
    bizno: Optional[str] = Field(None)
    date: Optional[str] = Field(None)
    total: Optional[float] = Field(None)
    vat: Optional[float] = Field(None)
    buyer: Optional[str] = Field(None)