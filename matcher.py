import argparse
import json
from datetime import datetime
from typing import List, Tuple

import requests
from models import CompanyProfile, FundingInstrument, Stage
from ytj_client import build_company_from_ytj, YTJError
from explanations import make_explanation

STAGES: List[Stage] = ["pre-seed", "seed", "growth", "scale-up"]
FUNDING_NEED_TYPES = {"RDI", "internationalization", "investments", "working capital"}


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


def validate_stage(stage: str) -> Stage:
    if stage not in STAGES:
        raise ValueError(f"Stage '{stage}' is not one of {STAGES}")
    return stage  # type: ignore[return-value]


def validate_need_types(needs: List[str]) -> List[str]:
    invalid = [n for n in needs if n.lower() not in {t.lower() for t in FUNDING_NEED_TYPES}]
    if invalid:
        raise ValueError(f"Unknown funding_need_types: {invalid}. Allowed: {sorted(FUNDING_NEED_TYPES)}")
    return needs


def score_instrument(
    company: CompanyProfile,
    instrument: FundingInstrument
) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    # -------- 0) Geography: hard-ish filter --------
    company_country = company.country.lower()
    geos_lower = [g.lower() for g in instrument.geography]
    if company_country in ("finland", "fi"):
        if "fi" in geos_lower:
            score += 4
            reasons.append("Company is in Finland and the instrument explicitly covers FI.")
        elif any(g in geos_lower for g in ["eu", "europe", "nordic"]):
            score += 1
            reasons.append("Instrument is regional (EU / Nordic) and may cover Finnish companies.")
        else:
            score -= 8
            reasons.append(f"Instrument geography {instrument.geography} does not appear to cover Finland.")
    else:
        if company_country in geos_lower:
            score += 2
            reasons.append(f"Instrument explicitly covers company country {company.country}.")
        elif any(g in geos_lower for g in ["eu", "europe"]):
            score += 1
            reasons.append("Instrument is EU-wide and may include the company country.")
        else:
            score -= 5
            reasons.append(f"Geographic fit uncertain for country {company.country}.")

    # -------- 1) Stage fit with adjacency --------
    stage_order = {s: i for i, s in enumerate(STAGES)}
    if company.stage in instrument.target_stages:
        score += 5
        reasons.append(f"Company stage '{company.stage}' is in target stages {instrument.target_stages}.")
    else:
        comp_idx = stage_order.get(company.stage)
        inst_idxs = [stage_order.get(s) for s in instrument.target_stages if stage_order.get(s) is not None]
        if comp_idx is not None and any(abs(comp_idx - idx) == 1 for idx in inst_idxs):
            score += 2
            reasons.append(f"Company stage '{company.stage}' is adjacent to target stages {instrument.target_stages}.")
        else:
            score -= 4
            reasons.append(f"Company stage '{company.stage}' is not aligned with target stages {instrument.target_stages}.")

    # -------- 2) Funding need overlap (coverage-based) --------
    company_needs = {n.lower() for n in company.funding_need_types}
    instrument_needs = {n.lower() for n in instrument.funding_need_types}
    overlap = company_needs & instrument_needs
    if overlap:
        coverage = len(overlap) / max(len(company_needs), 1)
        if coverage == 1:
            score += 6
            reasons.append("Funding needs fully covered by instrument focus.")
        else:
            score += 4
            reasons.append("Funding need partially covered: " + ", ".join(sorted(overlap)))
    else:
        score -= 4
        reasons.append("No overlap between funding needs and instrument focus.")

    # -------- 3) Amount range fit (with partial data) --------
    c_min = company.funding_amount_min
    c_max = company.funding_amount_max
    i_min = instrument.min_amount
    i_max = instrument.max_amount

    if c_min is not None or c_max is not None:
        if i_min is not None and c_max is not None and c_max < i_min:
            score -= 5
            reasons.append(f"Requested max ({c_max} €) is below instrument minimum ({i_min} €).")
        elif i_max is not None and c_min is not None and c_min > i_max:
            score -= 5
            reasons.append(f"Requested min ({c_min} €) is above instrument maximum ({i_max} €).")
        else:
            score += 2
            reasons.append("Requested amount overlaps the instrument's range.")
    else:
        reasons.append("Funding amount not provided; fit could be improved with ranges.")

    # -------- 4) Industry match (token-level check) --------
    industry_tokens = {tok.strip() for tok in company.industry.lower().replace(",", " ").split() if tok}
    instrument_inds = [i.lower() for i in instrument.target_industries]

    if "all" in instrument_inds:
        score += 1
        reasons.append("Instrument is open to all industries.")
    else:
        hit = False
        for ind in instrument_inds:
            for tok in industry_tokens:
                if tok in ind or ind in tok:
                    hit = True
                    break
            if hit:
                break
        if hit:
            score += 3
            reasons.append(f"Company industry '{company.industry}' matches instrument focus {instrument.target_industries}.")
        else:
            score -= 2
            reasons.append(f"Industry '{company.industry}' not clearly matched to {instrument.target_industries}.")

    # -------- 5) Application window urgency / availability --------
    if instrument.application_type == "call-based" and instrument.application_window:
        try:
            start_str, end_str = [p.strip() for p in instrument.application_window.split("–")]
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            days_left = (end_date - datetime.utcnow().date()).days
            if 0 <= days_left <= 30:
                score += 2
                reasons.append(f"Call deadline approaching in {days_left} days.")
            elif days_left < 0:
                score -= 2
                reasons.append("Call deadline appears to have passed.")
            else:
                reasons.append(f"Call open; {days_left} days until deadline.")
        except Exception:
            reasons.append("Could not parse application window for urgency scoring.")
    elif instrument.application_type == "continuous":
        score += 1
        reasons.append("Continuous application accepted.")

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

    try:
        stage_validated = validate_stage(args.stage)
        needs_validated = validate_need_types(needs)
    except ValueError as exc:
        raise SystemExit(str(exc))

    company: CompanyProfile
    if args.business_id:
        try:
            company = build_company_from_ytj(
                args.business_id,
                stage=stage_validated,
                revenue_class=args.revenue_class,
                employees=args.employees,
                funding_need_types=needs_validated,
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
            stage=stage_validated,
            funding_need_types=needs_validated,
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
