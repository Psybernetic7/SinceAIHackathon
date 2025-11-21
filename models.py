from dataclasses import dataclass
from typing import List, Optional, Literal

Stage = Literal["pre-seed", "seed", "growth", "scale-up"]

@dataclass
class CompanyProfile:
    name: str
    business_id: Optional[str]  # Y-tunnus, can be None
    industry: str               # free text or NACE code
    revenue_class: str          # e.g. "<250k", "250k-1M", "1-5M", ">5M"
    employees: int
    stage: Stage                # "pre-seed" | "seed" | "growth" | "scale-up"
    funding_need_types: List[str]   # ["RDI", "internationalization", "investments"]
    funding_amount_min: Optional[int]  # in euros
    funding_amount_max: Optional[int]  # in euros
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
