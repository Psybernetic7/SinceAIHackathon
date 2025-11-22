# explanations.py
from typing import List
from models import CompanyProfile, FundingInstrument

def make_explanation(company: CompanyProfile,
                     inst: FundingInstrument,
                     reasons: List[str]) -> str:
    needs = ", ".join(company.funding_need_types)
    stages = ", ".join(inst.target_stages)
    geos = ", ".join(inst.geography)

    parts = [
        f"{inst.name} by {inst.provider} is designed for {stages} companies in {geos}.",
        f"Your company is at {company.stage} stage with funding needs around {needs}, which matches this instrument's focus.",
    ]

    if inst.min_amount or inst.max_amount:
        parts.append(
            f"It typically supports project sizes between {inst.min_amount or 0} and {inst.max_amount or '∞'} EUR."
        )

    return " ".join(parts)
