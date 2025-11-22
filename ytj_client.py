import requests
from typing import Optional, Dict, Any, List
from models import CompanyProfile, Stage

BASE_URL = "https://avoindata.prh.fi/opendata-ytj-api/v3"


class YTJError(Exception):
    pass


def fetch_company_raw(business_id: str) -> Optional[Dict[str, Any]]:
    """
    Call PRH YTJ open data API and return the first matching company dict,
    or None if nothing found.
    """
    url = f"{BASE_URL}/companies"
    params = {"businessId": business_id}

    try:
        resp = requests.get(url, params=params, timeout=10)
    except requests.RequestException as exc:
        raise YTJError(f"YTJ API request failed: {exc}") from exc

    if resp.status_code == 429:
        raise YTJError("Rate limited by PRH YTJ API (HTTP 429). Try again later.")
    if resp.status_code >= 400:
        raise YTJError(f"YTJ API error {resp.status_code}: {resp.text}")

    data = resp.json()
    total = data.get("totalResults", 0)
    if not total:
        return None

    companies = data.get("companies") or []
    return companies[0] if companies else None

def build_company_from_ytj(
    business_id: str,
    *,
    stage: Stage,
    revenue_class: str,
    employees: int,
    funding_need_types: List[str],
    funding_amount_min: Optional[int],
    funding_amount_max: Optional[int],
) -> Optional[CompanyProfile]:
    raw = fetch_company_raw(business_id)
    if raw is None:
        return None

    # 1) Name – pick the current registered name (version == 1)
    names = raw.get("names") or []
    name = None
    for n in names:
        if n.get("version") == 1:
            name = n.get("name")
            break
    if not name and names:
        name = names[0].get("name")

    # 2) Industry – from mainBusinessLine descriptions, or TOL code
    main_bl = raw.get("mainBusinessLine") or {}
    tol_code = main_bl.get("type", "")
    descs = main_bl.get("descriptions") or []
    industry_desc = descs[0].get("description") if descs else ""

    # 3) Country – from address if available (otherwise default "FI")
    addresses = raw.get("addresses") or []
    country = "Finland"
    for addr in addresses:
        # type 1 = street, 2 = postal; we just pick first with a country
        c = addr.get("country")
        if c:
            # Country is a two-letter code, e.g. "FI"
            country = "Finland" if c == "FI" else c
            break

    return CompanyProfile(
        name=name or business_id,
        business_id=business_id,
        industry=industry_desc or tol_code or "Unknown",
        revenue_class=revenue_class,
        employees=employees,
        stage=stage,
        funding_need_types=funding_need_types,
        funding_amount_min=funding_amount_min,
        funding_amount_max=funding_amount_max,
        country=country,
    )
