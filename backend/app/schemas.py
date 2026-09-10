from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator, field_validator


class GeoLocation(BaseModel):
    provider_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=500)
    city: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    bounding_box: list[float] | None = Field(default=None, min_length=4, max_length=4)

    @field_validator('bounding_box')
    @classmethod
    def valid_bbox(cls, value):
        if value and not (-180 <= value[0] < value[2] <= 180 and -90 <= value[1] < value[3] <= 90):
            raise ValueError('Bounds must be west,south,east,north')
        return value


class SearchRequest(BaseModel):
    terms: list[str] = Field(min_length=1, max_length=15)
    location: GeoLocation
    scope: Literal['city', 'radius'] = 'radius'
    radius_km: float | None = Field(default=25, gt=0, le=100)
    mode: Literal['demo', 'live'] = 'demo'

    @field_validator('terms')
    @classmethod
    def clean_terms(cls, value):
        value = list(dict.fromkeys(s.strip() for s in value if s.strip()))
        if not value or any(len(s) > 100 for s in value):
            raise ValueError('Supply 1–15 nonblank terms, each at most 100 characters')
        return value

    @model_validator(mode='after')
    def scope_valid(self):
        if self.scope == 'radius' and self.radius_km is None:
            raise ValueError('Radius is required')
        if self.scope == 'city' and not self.location.bounding_box:
            raise ValueError('City scope requires provider-supplied geographic bounds; choose radius instead')
        return self


class RawObservation(BaseModel):
    source: str
    source_record_id: str
    source_url: str | None = None
    query_used: str
    name: str
    category_raw: str | None = None
    address_raw: str | None = None
    phone_raw: str | None = None
    website_raw: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    review_count: int | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)
    is_demo: bool = False


class ExportRequest(BaseModel):
    job_id: UUID
    format: Literal['csv', 'json', 'xlsx']
    scope: Literal['all', 'filtered', 'selected'] = 'all'
    entity_ids: list[UUID] = Field(default_factory=list, max_length=10000)
    filters: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def selected(self):
        if self.scope == 'selected' and not self.entity_ids:
            raise ValueError('Select at least one entity')
        return self
