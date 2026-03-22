const express = require("express");
const path = require("path");
const { spawn } = require("child_process");

const app = express();
const PORT = process.env.PORT || 3000;
const BOT_FILE = path.join(__dirname, "bot.py");
const PYTHON_BIN = process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

let botProcess = null;
let startedAt = null;
let logs = [];

function addLog(line) {
  const timestamp = new Date().toISOString();
  logs.push(`[${timestamp}] ${line}`);
  if (logs.length > 400) {
    logs = logs.slice(-400);
  }
}

function statusPayload() {
  return {
    running: !!botProcess,
    pid: botProcess ? botProcess.pid : null,
    startedAt,
    pythonBin: PYTHON_BIN,
    botFile: BOT_FILE,
  };
}

function startBot() {
  if (botProcess) {
    return { ok: false, message: "Bot is already running.", status: statusPayload() };
  }

  botProcess = spawn(PYTHON_BIN, [BOT_FILE], {
    cwd: __dirname,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
  });
  startedAt = new Date().toISOString();

  addLog(`Started bot process (PID ${botProcess.pid}).`);

  botProcess.stdout.on("data", (data) => {
    addLog(`[stdout] ${String(data).trimEnd()}`);
  });

  botProcess.stderr.on("data", (data) => {
    addLog(`[stderr] ${String(data).trimEnd()}`);
  });

  botProcess.on("close", (code, signal) => {
    addLog(`Bot process exited (code=${code}, signal=${signal || "none"}).`);
    botProcess = null;
    startedAt = null;
  });

  botProcess.on("error", (err) => {
    addLog(`Failed to start bot process: ${err.message}`);
    botProcess = null;
    startedAt = null;
  });

  return { ok: true, message: "Bot started.", status: statusPayload() };
}

function stopBot() {
  if (!botProcess) {
    return { ok: false, message: "Bot is not running.", status: statusPayload() };
  }

  const pid = botProcess.pid;
  const stopped = botProcess.kill("SIGTERM");

  if (!stopped) {
    return { ok: false, message: "Could not stop the bot process.", status: statusPayload() };
  }

  addLog(`Stop requested for PID ${pid}.`);
  return { ok: true, message: "Stop requested.", status: statusPayload() };
}

async function restartBot() {
  if (!botProcess) {
    return startBot();
  }

  await new Promise((resolve) => {
    const proc = botProcess;

    proc.once("close", () => {
      resolve();
    });

    const stopped = proc.kill("SIGTERM");
    if (!stopped) {
      resolve();
    }
  });

  return startBot();
}

app.get("/api/status", (_req, res) => {
  res.json(statusPayload());
});

app.get("/api/logs", (_req, res) => {
  res.json({ logs: logs.slice(-120) });
});

app.post("/api/start", (_req, res) => {
  const result = startBot();
  res.status(result.ok ? 200 : 409).json(result);
});

app.post("/api/stop", (_req, res) => {
  const result = stopBot();
  res.status(result.ok ? 200 : 409).json(result);
});

app.post("/api/restart", async (_req, res) => {
  const result = await restartBot();
  res.status(result.ok ? 200 : 500).json(result);
});

app.get("*", (_req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.listen(PORT, () => {
  console.log(`Control panel running on http://localhost:${PORT}`);
  addLog(`Control panel started on port ${PORT}.`);
});
