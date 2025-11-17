"""
Database Schemas for Luxury Real Estate & Construction Platform

Each Pydantic model below maps to a MongoDB collection using the lowercased
class name as the collection name.

Examples:
- Property -> "property"
- Lead -> "lead"
- Service -> "service"

These schemas are used by the backend for validation and by the CMS UI.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal, Dict


class SEO(BaseModel):
    title: Optional[str] = Field(None, description="SEO title override")
    description: Optional[str] = Field(None, description="SEO meta description")
    keywords: Optional[List[str]] = Field(default=None, description="SEO keywords")
    schema_type: Optional[str] = Field(
        default="RealEstateAgent",
        description="Schema.org type for rich results",
    )


class Property(BaseModel):
    title: str
    slug: str = Field(..., description="URL-friendly identifier")
    type: Literal["residential", "commercial", "land", "mixed"] = "residential"
    status: Literal["pre-sale", "available", "sold"] = "available"
    price: float = Field(..., ge=0)
    currency: Literal["MXN", "USD"] = "USD"
    location: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "Mexico"
    bedrooms: Optional[int] = Field(default=None, ge=0)
    bathrooms: Optional[float] = Field(default=None, ge=0)
    area_m2: Optional[float] = Field(default=None, ge=0)
    parking: Optional[int] = Field(default=None, ge=0)
    amenities: List[str] = []
    description: Optional[str] = None

    hero_image: Optional[HttpUrl] = None
    gallery: List[HttpUrl] = []
    video_url: Optional[HttpUrl] = None
    tour_360_url: Optional[HttpUrl] = None
    floorplan_url: Optional[HttpUrl] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    featured: bool = False
    seo: Optional[SEO] = None


class Lead(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = Field(default="website")
    property_id: Optional[str] = Field(default=None, description="Related property _id")
    tags: List[str] = []
    utm: Optional[Dict[str, str]] = None
    score: Optional[int] = Field(default=None, description="Simple heuristic score")


class Service(BaseModel):
    name: str
    slug: str
    summary: Optional[str] = None
    description: Optional[str] = None
    gallery: List[HttpUrl] = []
    categories: List[str] = []
    seo: Optional[SEO] = None
