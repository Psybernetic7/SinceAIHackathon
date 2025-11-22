# Smart Funding Advisor (Business Turku)

FastAPI + React prototype that ranks public funding instruments for Finnish companies. The backend scores matches using metadata in `funding_instruments.json`, optional LLM rewriting, and company data pulled from the PRH YTJ open data API. The frontend lets you search YTJ by name, provide funding details, and view ranked recommendations with explanations.

## Features
- YTJ company lookup and autofill (Business ID → basic profile)
- Scoring engine for funding stage, needs, geography, industry, and amount fit
- Optional LLM-generated explanations (OpenAI API) in addition to rule-based reasoning
- Ready-to-use dataset of Finnish/EU funding instruments
- React/Vite UI to search, configure needs, and browse ranked matches

## Prerequisites
- Python 3.10+ and `pip`
- Node.js 18+ and `npm`
- OpenAI access if using LLM explanations

## Backend setup (FastAPI)
1. Install deps: `pip install -r requirements.txt`
2. Environment variables (optional but recommended):
   - `OPENAI_API_KEY` – enables LLM explanations and summaries
   - `OPENAI_API_BASE` – override OpenAI base URL (default `https://api.openai.com/v1`)
   - `LLM_MODEL` – OpenAI model name (default `gpt-4o-mini`)
   - `INSTRUMENTS_SOURCE` – path or URL to the instrument JSON (default `funding_instruments.json`)
3. Run the API: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
4. Swagger UI is available at `http://localhost:8000/docs`.

## Frontend setup (React/Vite)
1. `cd frontend/my-app`
2. Install deps: `npm install`
3. `.env.local` with `VITE_API_BASE=http://localhost:8000` if the API is not on the default.
4. Start dev server: `npm run dev` (Vite defaults to port 5173).

## API reference (high level)
- `GET /health` – service status and loaded instrument count.
- `POST /recommendations` – manual company payload → ranked instruments.
- `POST /recommendations/by-business-id` – YTJ Business ID + request params → ranked instruments.
  - Optional query `use_llm=true` to enrich explanations when `OPENAI_API_KEY` is set.

Example request:
```bash
curl -X POST "http://localhost:8000/recommendations/by-business-id?use_llm=false" \
  -H "Content-Type: application/json" \
  -d '{
        "business_id": "1234567-8",
        "stage": "seed",
        "revenue_class": "<250k",
        "employees": 5,
        "funding_need_types": ["RDI", "internationalization"],
        "funding_amount_min": 50000,
        "funding_amount_max": 200000
      }'
```

## Data and scoring
- Instruments are loaded from `funding_instruments.json` (or `INSTRUMENTS_SOURCE` URL). Each record defines stage, industry, need types, geography, amount range, and application window metadata.
- Scoring rules live in `matcher.py` and consider geography, stage adjacency, need overlap, amount fit, industry tokens, and urgency (call deadlines).
- `explanations.py` builds human-readable rationales; `llm.py` can rewrite them via OpenAI for more polished text.

## Running the matcher CLI
You can also rank instruments from the CLI without the API:
```bash
python matcher.py --business-id 1234567-8 --stage seed --needs RDI,internationalization
```


