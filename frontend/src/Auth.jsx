import { useState } from "react";
import { api, setSession } from "./api";

export default function Auth({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api[mode](username, password);
      setSession(res.token, res.username);
      onAuth(res.username);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <section className="pitch">
        <div className="brand"><strong>Marginalia</strong></div>
        <h1>Answers you can check against the page.</h1>
        <p>Upload your documents, ask in plain language, and see the exact passage behind every claim.</p>
        <div className="demo" aria-label="Example answer">
          <p className="q">What notice is needed to end the contract?</p>
          <p className="a">Either party can terminate with 60 days' written notice<button className="cite" tabIndex={-1}>1</button>.</p>
          <p className="src"><b>1</b> Services Agreement.pdf, page 4</p>
          <blockquote><mark>Either party may terminate this Agreement upon sixty (60) days' prior written notice to the other party.</mark></blockquote>
          <span className="tag">Example</span>
        </div>
      </section>

      <form onSubmit={submit} className="auth-card">
        <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
        <label>Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label>Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            minLength={mode === "register" ? 8 : undefined} required />
        </label>
        {mode === "register" && <p className="muted small">Use at least 8 characters.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? "One moment…" : mode === "login" ? "Sign in" : "Create account"}</button>
        <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}
        </button>
      </form>
    </main>
  );
}
