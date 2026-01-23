
from pydantic import BaseModel
from typing import Literal, Any, Dict
from datetime import datetime

class CacheStatus(BaseModel):
    slug: str
    status: Literal['hit', 'miss', 'processing', 'failed']
    message: str | None = None
    data: Dict[str, Any] | None = None
    estimated_time: int | None = None
