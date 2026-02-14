import { useEffect, useState } from "react";

function MarketStatus() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setTime(new Date());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Indian time
  const options = {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  };

  const indiaTime = time.toLocaleTimeString("en-IN", options);

  // Market hours (IST)
  const hours = time.toLocaleString("en-US", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    hour12: false
  });

  const minutes = time.toLocaleString("en-US", {
    timeZone: "Asia/Kolkata",
    minute: "2-digit"
  });

  const currentMinutes = parseInt(hours) * 60 + parseInt(minutes);

  const open = 9 * 60 + 15;   // 9:15
  const close = 15 * 60 + 30; // 3:30

  const isOpen = currentMinutes >= open && currentMinutes <= close;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      
      <span style={{
        color: isOpen ? "#22c55e" : "#ef4444",
        fontWeight: "bold"
      }}>
        {isOpen ? "● Market Open" : "● Market Closed"}
      </span>

      <span style={{ color:"#cbd5e1" }}>
        {indiaTime} IST
      </span>

    </div>
  );
}

export default MarketStatus;
