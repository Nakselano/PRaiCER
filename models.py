from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel
from enum import Enum

class AnalysisStatus(str, Enum):
    NONE = "none",
    PROCESSING = "processing",
    COMPLETED = "completed",
    ERROR = "error"

class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float
    image_url: Optional[str] = None
    reviews: List["Review"] = Relationship(back_populates="product")
    offers: List["Offer"] = Relationship(back_populates="product")
    insights: Optional["Insight"] = Relationship(back_populates="product")

class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    content: str
    rating: float
    source: str = "unknown"
    product: Product = Relationship(back_populates="reviews")

class Insight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", unique=True)
    status: AnalysisStatus = Field(AnalysisStatus.NONE)
    summary: Optional[str] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    product: Product = Relationship(back_populates="insights")

class Offer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    store_name: Optional[str] = None
    price: float
    link: Optional[str] = None

    product: Optional[Product] = Relationship(back_populates="offers")