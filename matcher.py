import argparse
import json
from typing import List, Tuple

import requests
from models import CompanyProfile, FundingInstrument
from ytj_client import build_company_from_ytj, YTJError


def load_instruments(path: str) -> List[FundingInstrument]:
    # Allow loading from a remote JSON URL or local file.
    if path.startswith("http://") or path.startswith("https://"):
        resp = requests.get(path, timeout=10)
        if resp.status_code >= 400:
            raise SystemExit(f"Failed to fetch instruments from URL ({resp.status_code}): {resp.text}")
        raw = resp.json()
    else:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    return [FundingInstrument(**item) for item in raw]


def score_instrument(
    company: CompanyProfile,
    instrument: FundingInstrument
) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    # -------- 0) Geography: near hard-filter --------
    # Company is in Finland
    if company.country.lower() in ("finland", "fi"):
        geos_lower = [g.lower() for g in instrument.geography]

        if "fi" in geos_lower:
            score += 3
            reasons.append("Company is in Finland and the instrument explicitly covers FI.")
        elif "eu" in geos_lower or "europe" in geos_lower or "nordic" in geos_lower:
            score += 1
            reasons.append("Instrument is regional (EU / Nordic) and may cover Finnish companies.")
        else:
            score -= 8  # strong penalty -> will sink to bottom
            reasons.append(
                f"Instrument geography {instrument.geography} does not appear to cover Finland."
            )
    else:
        # very naive for non-Finnish companies
        reasons.append("Company is not in Finland; geographic fit not deeply evaluated.")

    # -------- 1) Stage fit (more decisive) --------
    if company.stage in instrument.target_stages:
        score += 4
        reasons.append(f"Company stage '{company.stage}' is in target stages {instrument.target_stages}.")
    else:
        # small nuance: if company is 'seed' and target includes 'pre-seed' or 'growth', maybe not terrible
        score -= 4
        reasons.append(
            f"Company stage '{company.stage}' is not in target stages {instrument.target_stages}."
        )

    # -------- 2) Funding need type overlap (strong signal) --------
    overlap = set(n.lower() for n in company.funding_need_types) & \
              set(n.lower() for n in instrument.funding_need_types)

    if overlap:
        score += 5
        reasons.append("Funding need matches instrument focus: " + ", ".join(sorted(overlap)))
    else:
        score -= 3
        reasons.append(
            "No overlap between company funding needs and instrument focus; fit is questionable."
        )

    # -------- 3) Amount range (strong penalties for obviously wrong) --------
    c_min = company.funding_amount_min
    c_max = company.funding_amount_max
    i_min = instrument.min_amount
    i_max = instrument.max_amount

    if c_min is not None and c_max is not None and (i_min is not None or i_max is not None):
        # Case: company max << instrument min -> instrument too big
        if i_min is not None and c_max < 0.5 * i_min:
            score -= 5
            reasons.append(
                f"Company's maximum request ({c_max} €) is far below instrument minimum ({i_min} €)."
            )
        # Case: company min >> instrument max -> instrument too small
        elif i_max is not None and c_min > i_max:
            score -= 5
            reasons.append(
                f"Company's minimum need ({c_min} €) is above instrument maximum ({i_max} €)."
            )
        else:
            # Rough positive signal if ranges overlap at all
            score += 2
            reasons.append(
                "Requested funding amount appears to be within or near the instrument's range."
            )
    else:
        reasons.append(
            "Funding amount fit not fully evaluated due to missing min/max values."
        )

    # -------- 4) Industry match (more bite) --------
    industry_lower = company.industry.lower()
    instrument_inds = [i.lower() for i in instrument.target_industries]

    if "all" in instrument_inds:
        score += 1
        reasons.append("Instrument is open to all industries.")
    else:
        # naive keyword / substring matching
        if any(ind in industry_lower for ind in instrument_inds):
            score += 3
            reasons.append(
                f"Company industry '{company.industry}' appears to match instrument focus {instrument.target_industries}."
            )
        else:
            score -= 2
            reasons.append(
                f"Company industry '{company.industry}' does not clearly match instrument focus {instrument.target_industries}."
            )

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


def main():
    parser = argparse.ArgumentParser(
        description="Rank funding instruments for a given company profile."
    )
    parser.add_argument("--business-id", help="Finnish business ID (Y-tunnus) to fetch from YTJ")
    parser.add_argument("--stage", default="seed", help="pre-seed|seed|growth|scale-up")
    parser.add_argument("--revenue-class", default="<250k", help="Revenue class label")
    parser.add_argument("--employees", type=int, default=5, help="Number of employees")
    parser.add_argument(
        "--needs",
        default="RDI,internationalization",
        help="Comma-separated funding need types (e.g. RDI,internationalization,investments)",
    )
    parser.add_argument("--min-amount", type=int, default=50000, help="Min amount needed (EUR)")
    parser.add_argument("--max-amount", type=int, default=200000, help="Max amount needed (EUR)")
    parser.add_argument("--country", default="Finland", help="Country name/code, defaults to Finland")
    parser.add_argument(
        "--instruments",
        default="funding_instruments.json",
        help="Path to funding instruments JSON",
    )
    args = parser.parse_args()

    instruments = load_instruments(args.instruments)
    needs = [n.strip() for n in args.needs.split(",") if n.strip()]

    company: CompanyProfile
    if args.business_id:
        try:
            company = build_company_from_ytj(
                args.business_id,
                stage=args.stage,  # type: ignore[arg-type]
                revenue_class=args.revenue_class,
                employees=args.employees,
                funding_need_types=needs,
                funding_amount_min=args.min_amount,
                funding_amount_max=args.max_amount,
            )
        except YTJError as exc:
            raise SystemExit(f"YTJ lookup failed: {exc}")

        if company is None:
            raise SystemExit(f"No company found in YTJ for business ID {args.business_id}.")
        if args.country and args.country != "Finland":
            company.country = args.country
    else:
        company = CompanyProfile(
            name="Example AI Startup",
            business_id=None,
            industry="software, AI",
            revenue_class=args.revenue_class,
            employees=args.employees,
            stage=args.stage,  # type: ignore[arg-type]
            funding_need_types=needs,
            funding_amount_min=args.min_amount,
            funding_amount_max=args.max_amount,
            country=args.country,
        )

    ranked = rank_instruments(company, instruments)

    print(f"Top recommendations for {company.name} (stage: {company.stage}):\n")
    for item in ranked:
        inst = item["instrument"]
        print(f"{inst.name} (provider: {inst.provider}) — score {item['score']}")
        for r in item["reasons"]:
            print(f"  - {r}")
        print()


if __name__ == "__main__":
    main()
