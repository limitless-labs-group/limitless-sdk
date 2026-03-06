"""Market-pages and navigation type definitions."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

from .markets import Market


FilterPrimitive = Union[str, int, float, bool]
FilterValue = Union[FilterPrimitive, List[FilterPrimitive]]


class NavigationNode(BaseModel):
    """Navigation node returned by /navigation endpoint."""

    id: str
    name: str
    slug: str
    path: str
    icon: Optional[str] = None
    children: List["NavigationNode"] = Field(default_factory=list)


NavigationNode.model_rebuild()


class FilterGroupOption(BaseModel):
    """Filter group option for market pages."""

    label: str
    value: str
    metadata: Optional[Dict[str, Any]] = None


class FilterGroup(BaseModel):
    """Filter group for market pages."""

    name: Optional[str] = None
    slug: Optional[str] = None
    allow_multiple: Optional[bool] = Field(None, alias="allowMultiple")
    presentation: Optional[str] = None
    options: Optional[List[FilterGroupOption]] = None
    source: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True)


class BreadcrumbItem(BaseModel):
    """Breadcrumb item returned by /market-pages/by-path endpoint."""

    name: str
    slug: str
    path: str


class MarketPage(BaseModel):
    """Market page data resolved by path."""

    id: str
    name: str
    slug: str
    full_path: str = Field(alias="fullPath")
    description: Optional[str] = None
    base_filter: Dict[str, Any] = Field(alias="baseFilter")
    filter_groups: List[FilterGroup] = Field(default_factory=list, alias="filterGroups")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    breadcrumb: List[BreadcrumbItem] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class PropertyOption(BaseModel):
    """Property option returned by property-keys endpoints."""

    id: str
    property_key_id: str = Field(alias="propertyKeyId")
    value: str
    label: str
    sort_order: int = Field(alias="sortOrder")
    parent_option_id: Optional[str] = Field(None, alias="parentOptionId")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class PropertyKey(BaseModel):
    """Property key returned by property-keys endpoints."""

    id: str
    name: str
    slug: str
    type: Literal["select", "multi-select"]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_system: bool = Field(alias="isSystem")
    options: Optional[List[PropertyOption]] = None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class OffsetPagination(BaseModel):
    """Offset pagination metadata."""

    page: int
    limit: int
    total: int
    total_pages: int = Field(alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)


class CursorPagination(BaseModel):
    """Cursor pagination metadata."""

    next_cursor: Optional[str] = Field(alias="nextCursor")

    model_config = ConfigDict(populate_by_name=True)


MarketPageSortField = Literal["createdAt", "updatedAt", "deadline", "id"]
MarketPageSort = Literal[
    "createdAt",
    "updatedAt",
    "deadline",
    "id",
    "-createdAt",
    "-updatedAt",
    "-deadline",
    "-id",
]


class MarketPageMarketsParams(BaseModel):
    """Query params for /market-pages/:id/markets endpoint."""

    page: Optional[int] = None
    limit: Optional[int] = None
    sort: Optional[MarketPageSort] = None
    cursor: Optional[str] = None
    filters: Optional[Dict[str, FilterValue]] = None


class MarketPageMarketsOffsetResponse(BaseModel):
    """Offset response for /market-pages/:id/markets endpoint."""

    data: List[Market]
    pagination: OffsetPagination


class MarketPageMarketsCursorResponse(BaseModel):
    """Cursor response for /market-pages/:id/markets endpoint."""

    data: List[Market]
    cursor: CursorPagination


MarketPageMarketsResponse = Union[MarketPageMarketsOffsetResponse, MarketPageMarketsCursorResponse]
