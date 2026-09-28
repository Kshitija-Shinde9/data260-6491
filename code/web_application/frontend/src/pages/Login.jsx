import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "../api/recallsApi.js";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const user = await login(email, password);
      onLogin(user);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <div className="view-head">
        <h2>Login</h2>
      </div>

      <div className="card">
        {error && <div className="notice notice-error" style={{ marginBottom: 18 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <label htmlFor="loginEmail">Email</label>
          <input
            id="loginEmail"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />

          <label htmlFor="loginPassword">Password</label>
          <input
            id="loginPassword"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button type="submit" className="btn btn-primary btn-block">Login</button>
        </form>

        <p className="field-hint" style={{ marginTop: 18, marginBottom: 0 }}>
          Demo account for grading: <code>admin@s6491.com</code> / <code>Recall@6491</code>
        </p>
      </div>
    </>
  );
}
