from typing import List, Optional

from mss.models import Size
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


class SizeCreate(BaseModel):
    modification_id: Optional[int] = None
    tire_front: Optional[str] = None
    tire_rear: Optional[str] = None
    rim_front: Optional[str] = None
    rim_rear: Optional[str] = None
    offset_front: Optional[str] = None
    offset_rear: Optional[str] = None
    backspacing_front: Optional[str] = None
    backspacing_rear: Optional[str] = None
    weight_front: Optional[str] = None
    weight_rear: Optional[str] = None
    pressure_front: Optional[str] = None
    pressure_rear: Optional[str] = None
    load_index_front: Optional[str] = None
    load_index_rear: Optional[str] = None
    speed_index_front: Optional[str] = None
    speed_index_rear: Optional[str] = None
    original_equipment: bool = False
    run_flats_tire: bool = False
    recommended_for_winter: bool = False
    extra_load_tire: bool = False


class Size(SizeCreate):
    id: int

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
    trim_levels: Optional[str] = None  # This allows trim_levels to be None
    sizes: List[SizeCreate]


class Modification(ModificationCreate):
    id: int
    trim_id: int
    processed: bool

    class Config:
        orm_mode = True
