import json
from typing import List, Tuple
from models import CompanyProfile, FundingInstrument

def load_instruments(path: str) -> List[FundingInstrument]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [FundingInstrument(**item) for item in raw]


def score_instrument(
    company: CompanyProfile,
    instrument: FundingInstrument
) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    # 1) Stage match
    if company.stage in instrument.target_stages:
        score += 3
        reasons.append(f"Company stage '{company.stage}' is in target stages.")
    else:
        reasons.append(
            f"Company stage '{company.stage}' not explicitly in {instrument.target_stages}."
        )

    # 2) Funding need type overlap
    overlap = set(company.funding_need_types) & set(instrument.funding_need_types)
    if overlap:
        score += 3
        reasons.append("Funding need matches: " + ", ".join(sorted(overlap)))
    else:
        reasons.append(
            "No direct overlap between funding need types and instrument focus."
        )

    # 3) Geography
    if company.country == "Finland" and "FI" in instrument.geography:
        score += 2
        reasons.append("Company in Finland and instrument covers FI.")
    elif "EU" in instrument.geography:
        score += 1
        reasons.append("Instrument is EU-wide and may cover the company.")
    else:
        reasons.append("Geographic fit is uncertain.")

    # 4) Amount range (very rough)
    if company.funding_amount_max is not None and instrument.min_amount is not None:
        if company.funding_amount_max < instrument.min_amount:
            score -= 1
            reasons.append(
                "Requested maximum amount is below the instrument's minimum."
            )

    # 5) Industry keyword check (super naive)
    industry_lower = company.industry.lower()
    if "all" in [i.lower() for i in instrument.target_industries]:
        score += 1
        reasons.append("Instrument is open to all industries.")
    elif any(word in industry_lower for word in [i.lower() for i in instrument.target_industries]):
        score += 2
        reasons.append("Industry appears to match instrument focus.")
    else:
        reasons.append("Industry match not obvious from description.")

    return score, reasons


def rank_instruments(
    company: CompanyProfile,
    instruments: List[FundingInstrument]
):
    scored = []
    for inst in instruments:
        score, reasons = score_instrument(company, inst)
        scored.append({
            "instrument": inst,
            "score": score,
            "reasons": reasons
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored

if __name__ == "__main__":
    instruments = load_instruments("funding_instruments.json")

    company = CompanyProfile(
        name="Example AI Startup",
        business_id=None,
        industry="software, AI",
        revenue_class="<250k",
        employees=5,
        stage="seed",
        funding_need_types=["RDI", "internationalization"],
        funding_amount_min=50000,
        funding_amount_max=200000,
        country="Finland"
    )

    ranked = rank_instruments(company, instruments)

    print(f"Top recommendations for {company.name}:\n")
    for item in ranked:
        inst = item["instrument"]
        print(f"{inst.name} (score: {item['score']})")
        for r in item["reasons"]:
            print(f"  - {r}")
        print()
