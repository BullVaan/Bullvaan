import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import SignalCard from "../components/SignalCard";

function Dashboard() {
  const navigate = useNavigate();

  useEffect(() => {
    const auth = localStorage.getItem("auth");
    if (!auth) navigate("/");
  }, []);

  const dummySignals = [
    { name: "Moving Average", signal: "BUY" },
    { name: "RSI", signal: "SELL" },
    { name: "MACD", signal: "BUY" },
    { name: "Bollinger", signal: "NEUTRAL" },
    { name: "EMA", signal: "BUY" },
    { name: "Supertrend", signal: "SELL" },
    { name: "VWAP", signal: "BUY" },
    { name: "Stochastic", signal: "NEUTRAL" },
    { name: "ADX", signal: "BUY" },
    { name: "Volume", signal: "SELL" }
  ];

  return (
    <div>

      {/* TOP BAR */}
      <div
        style={{
          background: "#020617",
          padding: 15,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid #334155"
        }}
      >
        <h2 style={{ margin: 0 }}>Bullvan Dashboard</h2>

        <button
          onClick={()=>{
            localStorage.removeItem("auth");
            navigate("/");
          }}
          style={{
            padding: "8px 14px",
            background: "#dc2626",
            border: "none",
            color: "white",
            cursor: "pointer",
            borderRadius: 6
          }}
        >
          Logout
        </button>
      </div>

      {/* CARDS GRID */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 15,
          justifyContent: "center",
          padding: 30
        }}
      >
        {dummySignals.map((item, index) => (
          <SignalCard key={index} name={item.name} signal={item.signal} />
        ))}
      </div>

    </div>
  );
}

export default Dashboard;
