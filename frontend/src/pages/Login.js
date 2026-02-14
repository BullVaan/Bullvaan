import { useState } from "react";
import { useNavigate } from "react-router-dom";

function Login() {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const navigate = useNavigate();

  const handleLogin = () => {
    if (user === process.env.REACT_APP_USER && pass === process.env.REACT_APP_PASS) {
      localStorage.setItem("auth", "true");
      navigate("/dashboard");
    } else {
      alert("Invalid credentials");
    }
  };

  return (
    <div style={{ display:"flex", height:"100vh", justifyContent:"center", alignItems:"center" }}>
      <div style={{ background:"#111827", padding:30, borderRadius:12, width:300 }}>
        
        <h2 style={{ textAlign:"center" }}>Login</h2>

        <input
          placeholder="Username"
          value={user}
          onChange={(e)=>setUser(e.target.value)}
          style={{ width:"100%", padding:10, marginTop:10 }}
        />

        <input
          placeholder="Password"
          type="password"
          value={pass}
          onChange={(e)=>setPass(e.target.value)}
          style={{ width:"100%", padding:10, marginTop:10 }}
        />

        <button
          onClick={handleLogin}
          style={{
            width:"100%",
            padding:10,
            marginTop:15,
            background:"#2563eb",
            border:"none",
            color:"white",
            cursor:"pointer"
          }}
        >
          Login
        </button>

      </div>
    </div>
  );
}

export default Login;
