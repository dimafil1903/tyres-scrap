import databases
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, select, update, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, joinedload

from schemas.shemas import BrandCreate, ModelCreate, TrimCreate, ModificationCreate

DATABASE_URL = 'sqlite+aiosqlite:///./db.db'
database = databases.Database(DATABASE_URL)
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=True, connect_args={"timeout": 15})
SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class BrandModel(Base):
    __tablename__ = 'brands'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    url = Column(String, unique=True)
    processed = Column(Boolean, default=False)

    models = relationship("ModelModel", back_populates="brand")


class ModelModel(Base):
    __tablename__ = 'models'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    url = Column(String, unique=True)
    processed = Column(Boolean, default=False)
    brand_id = Column(Integer, ForeignKey('brands.id'))

    brand = relationship("BrandModel", back_populates="models")
    trims = relationship("TrimModel", back_populates="model")
    # wheel_sizes = relationship("WheelSizeModel", back_populates="model")


class TrimModel(Base):
    __tablename__ = 'trims'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    year_from = Column(Integer)
    year_to = Column(String)
    url = Column(String)
    regions = Column(String)
    model_id = Column(Integer, ForeignKey('models.id'))
    processed = Column(Boolean, default=False)

    model = relationship("ModelModel", back_populates="trims")
    modifications = relationship("ModificationModel", back_populates="trim")


# class WheelSizeModel(Base):
#     __tablename__ = 'wheel_sizes'
#
#     id = Column(Integer, primary_key=True, index=True)
#     size = Column(String, index=True)
#     model_id = Column(Integer, ForeignKey('models.id'))
#
#     model = relationship("ModelModel", back_populates="wheel_sizes")


class ModificationModel(Base):
    __tablename__ = 'modifications'

    id = Column(Integer, primary_key=True, index=True)
    trim_id = Column(Integer, ForeignKey('trims.id'))
    name = Column(String, index=True)
    year_from = Column(Integer)
    year_to = Column(String)
    regions = Column(String)
    url = Column(String, unique=True)
    fuel = Column(String)
    engine = Column(String)
    power = Column(String)
    center_bore_hub_bore = Column(String)
    bolt_pattern_pcd = Column(String)
    wheel_fasteners = Column(String)
    thread_size = Column(String)
    wheel_tightening = Column(String)
    trim_levels = Column(String, nullable=True)
    trim = relationship("TrimModel", back_populates="modifications")


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, unique=True, index=True, nullable=False)
    port = Column(String, nullable=False)
    used = Column(Boolean, default=False)
    failed = Column(Boolean, default=False)


async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


async def create_brand(db: AsyncSession, brand: BrandCreate):
    query = insert(BrandModel).values(name=brand.name, url=brand.url)
    await db.execute(query)
    await db.commit()


async def create_model(db: AsyncSession, model: ModelCreate, brand_id: int):
    query = insert(ModelModel).values(name=model.name, url=model.url, brand_id=brand_id).options(
        joinedload(ModelModel.brand))
    await db.execute(query)
    await db.commit()


async def create_trim(db: AsyncSession, trim: TrimCreate, model_id: int):
    regions_str = ', '.join(trim.regions)
    query = insert(TrimModel).values(
        name=trim.name,
        year_from=trim.year_from,
        year_to=trim.year_to,
        url=trim.url,
        regions=regions_str,
        model_id=model_id
    ).options(joinedload(TrimModel.model))
    await db.execute(query)
    await db.commit()


async def create_modification(db: AsyncSession, modification: ModificationCreate, trim_id: int):
    regions_str = ', '.join(modification.regions)
    query = insert(ModificationModel).values(
        trim_id=trim_id,
        name=modification.name,
        year_from=modification.year_from,
        year_to=modification.year_to,
        regions=regions_str,
        url=modification.url,
        fuel=modification.fuel,
        engine=modification.engine,
        power=modification.power,
        center_bore_hub_bore=modification.center_bore_hub_bore,
        bolt_pattern_pcd=modification.bolt_pattern_pcd,
        wheel_fasteners=modification.wheel_fasteners,
        thread_size=modification.thread_size,
        wheel_tightening=modification.wheel_tightening,
        trim_levels=modification.trim_levels
    ).options(joinedload(ModificationModel.trim))
    await db.execute(query)
    await db.commit()


async def update_brand_processed(db: AsyncSession, brand_id: int):
    query = update(BrandModel).where(BrandModel.id == brand_id).values(processed=True)
    await db.execute(query)
    await db.commit()


async def update_model_processed(db: AsyncSession, model_id: int):
    query = update(ModelModel).where(ModelModel.id == model_id).values(processed=True)
    await db.execute(query)
    await db.commit()


async def update_trim_processed(db: AsyncSession, trim_id: int):
    query = (update(TrimModel)
    .options(joinedload(TrimModel.model))
    .where(TrimModel.id == trim_id).values(processed=True))
    await db.execute(query)
    await db.commit()


async def update_modification_processed(db: AsyncSession, modification_id: int):
    query = update(ModificationModel).where(ModificationModel.id == modification_id).values(processed=True)
    await db.execute(query)
    await db.commit()


async def get_unprocessed_brands(db: AsyncSession):
    query = select(BrandModel).where(BrandModel.processed == False)
    result = await db.execute(query)
    return result.scalars().all()


async def get_unprocessed_models(db: AsyncSession):
    query = select(ModelModel).where(ModelModel.processed == False)
    result = await db.execute(query)
    return result.scalars().all()


async def get_unprocessed_trims(db: AsyncSession):
    query = select(TrimModel).where(TrimModel.processed == False)
    result = await db.execute(query)
    return result.scalars().all()


async def get_unprocessed_modifications(db: AsyncSession):
    query = (select(ModificationModel)
             .options(joinedload(ModificationModel.trim))
             .where(ModificationModel.processed == False))
    result = await db.execute(query)
    return result.scalars().all()


async def get_unused_proxy(db: AsyncSession):
    query = select(Proxy).where(Proxy.used == False, Proxy.failed == False)
    result = await db.execute(query)
    return result.scalars().first()


async def mark_proxy_as_used(db: AsyncSession, proxy):
    query = update(Proxy).where(Proxy.id == proxy.id).values(used=True)
    await db.execute(query)
    await db.commit()


async def mark_proxy_as_failed(db: AsyncSession, proxy):
    query = update(Proxy).where(Proxy.id == proxy.id).values(failed=True)
    await db.execute(query)
    await db.commit()


async def add_proxy(db: AsyncSession, ip, port):
    query = insert(Proxy).values(ip=ip, port=port)
    try:
        await db.execute(query)
        await db.commit()
    except IntegrityError:
        pass
