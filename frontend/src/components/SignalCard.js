function SignalCard({ name, signal }) {
  const getColor = () => {
    if (signal === "BUY") return "#16a34a";
    if (signal === "SELL") return "#dc2626";
    return "#eab308";
  };

  return (
    <div
      style={{
        background: "#111827",
        border: `2px solid ${getColor()}`,
        borderRadius: 10,
        padding: 15,
        textAlign: "center",
        width: 140
      }}
    >
      <div
        style={{
          fontSize: 14,
          marginBottom: 10,
          color: "#9ca3af"
        }}
      >
        {name}
      </div>

      <div
        style={{
          fontSize: 20,
          fontWeight: "bold",
          color: getColor()
        }}
      >
        {signal}
      </div>
    </div>
  );
}

export default SignalCard;
