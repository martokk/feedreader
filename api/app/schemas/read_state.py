from typing import Optional

from pydantic import BaseModel


class ReadStateUpdate(BaseModel):
    read: Optional[bool] = None
    starred: Optional[bool] = None
