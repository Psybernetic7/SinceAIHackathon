import { useEffect, useState } from "react";

import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const url = `https://avoindata.prh.fi/opendata-ytj-api/v3/companies?name=${encodeURIComponent(
        query
      )}&page=1`;

      const response = await fetch(url);
      const data = await response.json();
      //Filter companies based on search
      const filtered = data.companies.filter((company) =>
        company.names.some((n) => n.name.toLowerCase().includes(query.toLowerCase()))
      );
      setResults(filtered);
    } catch (error) {
      console.log(error);
      setResults([]);
    }
    setLoading(false);
  };
  
  useEffect(()=>{
    if(query.length === 0){
      setResults([])
      return
    }
  }, [query])

  return (
    <>
      <div
        style={{
          maxWidth: "400px",
          margin: "auto",
          backgroundColor: "skyblue",
          padding: "20px",
          borderRadius: "8px",
        }}
      >
        <form onSubmit={handleSearch}>
          <input
            onChange={(e) => setQuery(e.target.value)}
            type="text"
            value={query}
            required
            style={{ width: "100%", padding: "8px", marginBottom: "10px" }}
            placeholder="enter the company name"
          />
          <button
            style={{
              backgroundColor: "green",
              color: "white",
              padding: "8px 16px",
            }}
          >
            Search
          </button>
        </form>
        {loading && <p>Loading...</p>}
        <ul>
          {results.map((company, index) => (
            <li key={index} style={{ marginBottom: "15px" }}>
              <strong>Business ID:</strong> {company.businessId?.value} <br />
              <strong>Name(s):</strong>{" "}
              {company.names?.map((n) => n.name).join(", ")} <br />
              {company.tradeRegisterStatus && (
                <>
                  <strong>Status:</strong> {company.tradeRegisterStatus}
                </>
              )}
            </li>
          ))}
        </ul>
        {results.length === 0 && !loading && <p>No exact match found.</p>}
      </div>
    </>
  );
}

export default App;
