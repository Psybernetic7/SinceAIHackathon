import { FormEvent, useEffect, useMemo, useState } from "react";
import "./App.css";

type Stage = "pre-seed" | "seed" | "growth" | "scale-up";

type CompanyResult = {
  businessId?: { value?: string };
  names?: { name: string }[];
  tradeRegisterStatus?: string;
};

type Recommendation = {
  instrument: {
    id: string;
    name: string;
    provider: string;
    url: string;
    application_window?: string | null;
  };
  score: number;
  reasons: string[];
  explanation: string;
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CompanyResult[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingRecos, setLoadingRecos] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("seed");
  const [revenue, setRevenue] = useState("<250k");
  const [employees, setEmployees] = useState(5);
  const [needTypes, setNeedTypes] = useState<string>("RDI,internationalization");
  const [minAmount, setMinAmount] = useState<number | "">("");
  const [maxAmount, setMaxAmount] = useState<number | "">("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [useLLM, setUseLLM] = useState(true);

  const parsedNeeds = useMemo(
    () =>
      needTypes
        .split(",")
        .map((n) => n.trim())
        .filter(Boolean),
    [needTypes]
  );

  const handleSearch = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoadingSearch(true);
    setError(null);

    try {
        const url = `https://avoindata.prh.fi/opendata-ytj-api/v3/companies?name=${encodeURIComponent(
          query
        )}&page=1`;

        const response = await fetch(url);
        const data = await response.json();
        const filtered = (data.companies || []).filter((company: CompanyResult) =>
          (company.names || []).some((n) => n.name.toLowerCase().includes(query.toLowerCase()))
        );
        setResults(filtered);
    } catch (err) {
      console.error(err);
      setError("Search failed. Try again.");
      setResults([]);
    }
    setLoadingSearch(false);
  };

  const fetchRecommendations = async () => {
    if (!selectedId) return;
    setLoadingRecos(true);
    setError(null);
    setRecommendations([]);
    try {
      const payload = {
        business_id: selectedId,
        stage,
        revenue_class: revenue,
        employees,
        funding_need_types: parsedNeeds,
        funding_amount_min: minAmount === "" ? null : minAmount,
        funding_amount_max: maxAmount === "" ? null : maxAmount,
      };
      const resp = await fetch(`${API_BASE}/recommendations/by-business-id?use_llm=${useLLM}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${resp.status})`);
      }
      const data = await resp.json();
      setRecommendations(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Could not fetch recommendations.");
    }
    setLoadingRecos(false);
  };

  useEffect(() => {
    if (query.length === 0) {
      setResults([]);
      return;
    }
  }, [query]);

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Smart Funding Advisor</p>
          <h1>Find public funding matches in minutes</h1>
          <p className="subhead">
            Lookup a Finnish company from YTJ, add your funding needs, and get ranked recommendations with justifications.
          </p>
        </div>
      </header>

      <main className="layout">
        <section className="panel">
          <div className="panel-header">
            <h2>Company lookup (YTJ)</h2>
            <p className="helper">Search by name, then pick the correct Business ID.</p>
          </div>
          <form onSubmit={handleSearch} className="form-grid">
            <input
              onChange={(e) => setQuery(e.target.value)}
              type="text"
              value={query}
              required
              placeholder="Enter company name"
              className="input"
            />
            <button className="btn primary" disabled={loadingSearch}>
              {loadingSearch ? "Searching..." : "Search"}
            </button>
          </form>
          {error && <p className="error">{error}</p>}
          {results.length === 0 && !loadingSearch && query && <p className="muted">No exact match found.</p>}
          <div className="results">
            {results.map((company, index) => (
              <div
                key={index}
                className={`result-card ${selectedId === company.businessId?.value ? "active" : ""}`}
              >
                <div>
                  <div className="result-title">{company.names?.map((n) => n.name).join(", ") || "Unknown"}</div>
                  <div className="muted small">Business ID: {company.businessId?.value || "N/A"}</div>
                  {company.tradeRegisterStatus && (
                    <div className="muted small">Status: {company.tradeRegisterStatus}</div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedId(company.businessId?.value || null)}
                  className="btn ghost"
                >
                  {selectedId === company.businessId?.value ? "Selected" : "Select"}
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Funding request details</h2>
            <p className="helper">Tell us your stage and need so we can rank better.</p>
          </div>
          <div className="form-grid">
            <label className="field">
              <span>Stage</span>
              <select value={stage} onChange={(e) => setStage(e.target.value as Stage)} className="input">
                <option value="pre-seed">pre-seed</option>
                <option value="seed">seed</option>
                <option value="growth">growth</option>
                <option value="scale-up">scale-up</option>
              </select>
            </label>
            <label className="field">
              <span>Revenue class</span>
              <input value={revenue} onChange={(e) => setRevenue(e.target.value)} className="input" />
            </label>
            <label className="field">
              <span>Employees</span>
              <input
                type="number"
                value={employees}
                onChange={(e) => setEmployees(Number(e.target.value))}
                className="input"
              />
            </label>
            <label className="field">
              <span>Funding needs (comma separated)</span>
              <input value={needTypes} onChange={(e) => setNeedTypes(e.target.value)} className="input" />
            </label>
            <div className="two-col">
              <label className="field">
                <span>Min amount (€)</span>
                <input
                  type="number"
                  value={minAmount}
                  onChange={(e) => setMinAmount(e.target.value === "" ? "" : Number(e.target.value))}
                  className="input"
                />
              </label>
              <label className="field">
                <span>Max amount (€)</span>
                <input
                  type="number"
                  value={maxAmount}
                  onChange={(e) => setMaxAmount(e.target.value === "" ? "" : Number(e.target.value))}
                  className="input"
                />
              </label>
            </div>
            <label className="field toggle">
              <span>Use LLM explanations</span>
              <input
                type="checkbox"
                checked={useLLM}
                onChange={(e) => setUseLLM(e.target.checked)}
              />
            </label>
            <button
              disabled={!selectedId || loadingRecos}
              onClick={fetchRecommendations}
              className="btn accent"
              type="button"
            >
              {loadingRecos ? "Loading recommendations..." : "Get recommendations"}
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Recommendations</h2>
            <p className="helper">Ranked options with explanations you can show to the client.</p>
          </div>
          {recommendations.length === 0 && !loadingRecos && <p className="muted">No recommendations yet.</p>}
          <div className="recos">
            {recommendations.map((rec) => (
              <div key={rec.instrument.id} className="reco-card">
                <div className="reco-head">
                  <div>
                    <div className="reco-title">{rec.instrument.name}</div>
                    <div className="muted small">{rec.instrument.provider}</div>
                    {rec.instrument.application_window && (
                      <div className="badge">Window: {rec.instrument.application_window}</div>
                    )}
                  </div>
                  <div className="score">Score: {rec.score}</div>
                </div>
                <p className="explanation">{rec.explanation}</p>
                <ul className="reason-list">
                  {rec.reasons.map((r, idx) => (
                    <li key={idx}>{r}</li>
                  ))}
                </ul>
                <a className="link" href={rec.instrument.url} target="_blank" rel="noreferrer">
                  View instrument
                </a>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
