from dataclasses import dataclass
from typing import List, Optional, Literal, TypeAlias

Stage: TypeAlias = Literal["pre-seed", "seed", "growth", "scale-up"]

@dataclass
class CompanyProfile:
    name: str
    business_id: Optional[str]
    industry: str
    revenue_class: str
    employees: int
    stage: Stage
    funding_need_types: List[str]
    funding_amount_min: Optional[int]
    funding_amount_max: Optional[int]
    country: str = "Finland"

@dataclass
class FundingInstrument:
    id: str                     # internal ID
    name: str
    provider: str               # e.g. "Business Finland"
    url: str
    description: str

    target_stages: List[Stage]  # which stages it fits
    target_industries: List[str]  # keywords or NACE-like labels
    funding_need_types: List[str] # ["RDI", "internationalization", "investments"]

    min_amount: Optional[int]
    max_amount: Optional[int]

    geography: List[str]        # e.g. ["FI"], ["EU"], ["Nordic"]
    application_type: str       # "continuous" | "call-based"
    application_window: Optional[str]  # e.g. "2025-01-01 – 2025-03-31" or None
    notes: Optional[str] = None
