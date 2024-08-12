from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class BrandCreate(BaseModel):
    name: str
    url: HttpUrl


class Brand(BrandCreate):
    id: int
    processed: bool

    class Config:
        orm_mode = True


class ModelCreate(BaseModel):
    name: str
    url: HttpUrl


class Model(ModelCreate):
    id: int
    brand_id: int
    processed: bool

    class Config:
        orm_mode = True


class TrimCreate(BaseModel):
    name: str
    year_from: int
    year_to: str
    url: HttpUrl
    regions: List[str]


class Trim(TrimCreate):
    id: int
    model_id: int
    processed: bool

    class Config:
        orm_mode = True


class ModificationCreate(BaseModel):
    name: str
    year_from: int
    year_to: str
    url: HttpUrl
    fuel: str
    engine: str
    power: str
    center_bore_hub_bore: str
    bolt_pattern_pcd: str
    wheel_fasteners: str
    thread_size: str
    wheel_tightening: str
    regions: List[str]
    trim_levels: Optional[str]  # This allows trim_levels to be None



class Modification(ModificationCreate):
    id: int
    trim_id: int
    processed: bool
    class Config:
        orm_mode = True