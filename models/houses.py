from pydoc import describe
from pydantic import BaseModel
from typing import Optional
from datetime import date as dt
from typing import List
        
class Houses(BaseModel):
    id: str
    title: str
    houseType: str
    main_image: Optional[List[str]] = None
    images: Optional[List[str]] = None

class HouseUpdate(BaseModel):
    title: str
    houseType: str
    main_image: Optional[List[str]] = []
    images: Optional[List[str]] = []