# main.py
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from models import CompanyProfile, FundingInstrument, Stage
from matcher import load_instruments, rank_instruments, validate_stage, validate_need_types
from ytj_client import build_company_from_ytj, YTJError
from explanations import make_explanation


app = FastAPI(title="Smart Funding Advisor MVP")

# ---------- Load instruments once at startup ----------

INSTRUMENT_SOURCE = os.getenv("INSTRUMENTS_SOURCE", "funding_instruments.json")
INSTRUMENTS: List[FundingInstrument] = load_instruments(INSTRUMENT_SOURCE)


# ---------- Pydantic models for API ----------

class CompanyInput(BaseModel):
    name: str
    business_id: Optional[str] = None
    industry: str
    revenue_class: str
    employees: int
    stage: Stage
    funding_need_types: List[str]
    funding_amount_min: Optional[int] = None
    funding_amount_max: Optional[int] = None
    country: str = "Finland"


class CompanyByBusinessIdInput(BaseModel):
    business_id: str
    stage: Stage
    revenue_class: str
    employees: int
    funding_need_types: List[str]
    funding_amount_min: Optional[int] = None
    funding_amount_max: Optional[int] = None


class Recommendation(BaseModel):
    instrument: dict
    score: int
    reasons: List[str]
    explanation: str


# ---------- Simple root endpoint (optional) ----------

@app.get("/")
def root():
    return {"message": "Smart Funding Advisor API. See /docs for Swagger UI."}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "instrument_source": INSTRUMENT_SOURCE,
        "instrument_count": len(INSTRUMENTS),
    }


# ---------- Main recommendations endpoint (manual company input) ----------

@app.post("/recommendations", response_model=List[Recommendation])
def get_recommendations(company: CompanyInput):
    """
    Take a company profile as JSON, return ranked funding instruments + reasons.
    """
    try:
        validate_stage(company.stage)
        validate_need_types(company.funding_need_types)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Convert request model -> internal dataclass
    company_profile = CompanyProfile(
        name=company.name,
        business_id=company.business_id,
        industry=company.industry,
        revenue_class=company.revenue_class,
        employees=company.employees,
        stage=company.stage,
        funding_need_types=company.funding_need_types,
        funding_amount_min=company.funding_amount_min,
        funding_amount_max=company.funding_amount_max,
        country=company.country,
    )

    # Use your matcher
    scored = rank_instruments(company_profile, INSTRUMENTS)

    # Convert dataclass instruments to plain dicts
    recommendations: List[Recommendation] = []
    for item in scored:
        inst: FundingInstrument = item["instrument"]

        # build explanation per item
        explanation = make_explanation(company_profile, inst, item["reasons"])

        inst_dict = {
            "id": inst.id,
            "name": inst.name,
            "provider": inst.provider,
            "url": inst.url,
            "description": inst.description,
            "target_stages": inst.target_stages,
            "target_industries": inst.target_industries,
            "funding_need_types": inst.funding_need_types,
            "min_amount": inst.min_amount,
            "max_amount": inst.max_amount,
            "geography": inst.geography,
            "application_type": inst.application_type,
            "application_window": inst.application_window,
            "notes": inst.notes,
        }
        recommendations.append(
            Recommendation(
                instrument=inst_dict,
                score=item["score"],
                reasons=item["reasons"],
                explanation=explanation,
            )
        )

    return recommendations


# ---------- YTJ-based endpoint (Business ID) ----------

@app.post("/recommendations/by-business-id", response_model=List[Recommendation])
def get_recommendations_by_business_id(payload: CompanyByBusinessIdInput):
    """
    Use YTJ (PRH open data) to fetch company info from Business ID,
    then run the matching logic.
    """
    try:
        validate_stage(payload.stage)
        validate_need_types(payload.funding_need_types)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        company = build_company_from_ytj(
            payload.business_id,
            stage=payload.stage,
            revenue_class=payload.revenue_class,
            employees=payload.employees,
            funding_need_types=payload.funding_need_types,
            funding_amount_min=payload.funding_amount_min,
            funding_amount_max=payload.funding_amount_max,
        )
    except YTJError as e:
        # upstream API problem
        raise HTTPException(status_code=502, detail=str(e))

    if company is None:
        # YTJ returned 0 results
        raise HTTPException(
            status_code=404,
            detail=f"No company found in YTJ for Business ID {payload.business_id}",
        )

    scored = rank_instruments(company, INSTRUMENTS)

    recommendations: List[Recommendation] = []
    for item in scored:
        inst: FundingInstrument = item["instrument"]

        # explanation here uses the company built from YTJ
        explanation = make_explanation(company, inst, item["reasons"])

        inst_dict = {
            "id": inst.id,
            "name": inst.name,
            "provider": inst.provider,
            "url": inst.url,
            "description": inst.description,
            "target_stages": inst.target_stages,
            "target_industries": inst.target_industries,
            "funding_need_types": inst.funding_need_types,
            "min_amount": inst.min_amount,
            "max_amount": inst.max_amount,
            "geography": inst.geography,
            "application_type": inst.application_type,
            "application_window": inst.application_window,
            "notes": inst.notes,
        }
        recommendations.append(
            Recommendation(
                instrument=inst_dict,
                score=item["score"],
                reasons=item["reasons"],
                explanation=explanation,
            )
        )

    return recommendations
