import SignalCard from "./components/SignalCard";

function App() {
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
    <div style={{ padding: 30 }}>
      
      {/* HEADER BOX */}
      <div
        style={{
          background: "#111827",
          padding: 15,
          borderRadius: 12,
          textAlign: "center",
          width: "fit-content",
          margin: "0 auto",
          border: "1px solid #334155"
        }}
      >
        <h2 style={{ margin: 0 }}>Bullvan Signal Dashboard</h2>
      </div>

      {/* CARD GRID */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 15,
          justifyContent: "center",
          marginTop: 30
        }}
      >
        {dummySignals.map((item, index) => (
          <SignalCard key={index} name={item.name} signal={item.signal} />
        ))}
      </div>

    </div>
  );
}

export default App;
