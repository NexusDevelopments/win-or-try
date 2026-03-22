const { useEffect, useMemo, useRef, useState } = React;

function formatTime(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function App() {
  const [status, setStatus] = useState({ running: false, pid: null, startedAt: null });
  const [logs, setLogs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("panel ready rn.");
  const logEndRef = useRef(null);

  const stateClass = status.running ? "status-running" : "status-stopped";
  const stateText = status.running ? "Running" : "Stopped";

  const botUptime = useMemo(() => {
    if (!status.startedAt) {
      return "-";
    }

    const started = new Date(status.startedAt).getTime();
    const now = Date.now();
    const diffMs = now - started;
    if (diffMs < 0) {
      return "-";
    }

    const mins = Math.floor(diffMs / 60000);
    const secs = Math.floor((diffMs % 60000) / 1000);
    return `${mins}m ${secs}s`;
  }, [status.startedAt, logs.length]);

  async function refreshStatus() {
    const response = await fetch("/api/status");
    const data = await response.json();
    setStatus(data);
  }

  async function refreshLogs() {
    const response = await fetch("/api/logs");
    const data = await response.json();
    setLogs(data.logs || []);
  }

  async function runAction(endpoint, successText) {
    try {
      setBusy(true);
      const response = await fetch(endpoint, { method: "POST" });
      const data = await response.json();

      setNotice(data.message || successText);
      if (!response.ok) {
        return;
      }

      await refreshStatus();
      await refreshLogs();
    } catch (error) {
      setNotice(`request failed fr: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refreshStatus();
    refreshLogs();

    const timer = setInterval(() => {
      refreshStatus();
      refreshLogs();
    }, 2500);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [logs.length]);

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1 className="title">Casino Bot Control</h1>
          <p className="subtitle">browser panel so u can control the bot process easy.</p>
        </div>
        <div className={`status-pill ${stateClass}`}>{stateText}</div>
      </header>

      <section className="grid">
        <article className="card">
          <h2>Process</h2>
          <div className="row">
            <button disabled={busy || status.running} onClick={() => runAction("/api/start", "Start requested")}>Start</button>
            <button disabled={busy || !status.running} onClick={() => runAction("/api/stop", "Stop requested")}>Stop</button>
            <button disabled={busy} onClick={() => runAction("/api/restart", "Restart requested")}>Restart</button>
          </div>

          <ul className="meta-list" style={{ marginTop: "16px" }}>
            <li><strong>PID</strong> {status.pid || "-"}</li>
            <li><strong>Started</strong> {formatTime(status.startedAt)}</li>
            <li><strong>Uptime</strong> {botUptime}</li>
            <li><strong>Python</strong> {status.pythonBin || "python"}</li>
            <li><strong>Token Var</strong> {status.tokenEnvKey || "missing"}</li>
          </ul>
        </article>

        <article className="card">
          <h2>Runtime Notes</h2>
          <p>
            bot runs from this pc and pulls token from railway vars.
            it checks <strong>DISCORD_TOKEN</strong>, then <strong>BOT_TOKEN</strong>, then <strong>TOKEN</strong>.
          </p>
          <p>
            if it dont start, check logs for python path, missing packages,
            or token setup.
          </p>
          <div className="banner">{notice}</div>
        </article>
      </section>

      <section className="card" style={{ marginTop: "16px" }}>
        <h2>Logs</h2>
        <div className="log-box">
          {(logs.length ? logs : ["No logs yet."]).join("\n")}
          <div ref={logEndRef} />
        </div>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
