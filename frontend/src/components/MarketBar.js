import { useEffect, useState } from "react";

function MarketBar() {
  const [data, setData] = useState([]);

  const fetchMarket = async () => {
    try {
      const res = await fetch(
        "https://query1.finance.yahoo.com/v7/finance/quote?symbols=%5ENSEI,%5EBSESN,%5ENSEBANK"
      );
      const json = await res.json();

      const result = json.quoteResponse.result;

      setData(result);
    } catch (err) {
      console.log("Fetch error:", err);
    }
  };

  useEffect(() => {
    fetchMarket();
    const interval = setInterval(fetchMarket, 500000); 
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      style={{
        background: "#020617",
        padding: 15,
        borderBottom: "1px solid #334155",
        display: "flex",
        justifyContent: "center",
        gap: 40
      }}
    >
      {data.map((item) => (
        <div key={item.symbol} style={{ textAlign: "center" }}>
          <div style={{ fontSize: 13, color: "#9ca3af" }}>
            {item.shortName}
          </div>

          <div style={{ fontSize: 18, fontWeight: "bold" }}>
            {item.regularMarketPrice}
          </div>

          <div
            style={{
              fontSize: 13,
              color:
                item.regularMarketChange >= 0 ? "#16a34a" : "#dc2626"
            }}
          >
            {item.regularMarketChange.toFixed(2)} (
            {item.regularMarketChangePercent.toFixed(2)}%)
          </div>
        </div>
      ))}
    </div>
  );
}

export default MarketBar;
