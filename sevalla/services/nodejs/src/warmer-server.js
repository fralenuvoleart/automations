const http = require("http");
const fs = require("fs");
const path = require("path");
const { runWarmer } = require("./cache-warmer");
const { WARMER_TOKEN: TOKEN } = require("../config/warmer-config");

const PROGRESS_FILE = path.join(__dirname, "..", "cache-warmer-progress.json");
const SUMMARY_FILE = path.join(__dirname, "..", "cache-warmer-last-run.json");

function jsonResponse(res, status, data) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

function readJSON(filepath) {
  try {
    if (fs.existsSync(filepath)) {
      return JSON.parse(fs.readFileSync(filepath, "utf8"));
    }
  } catch (_) { /* ignore */ }
  return null;
}

function createServer() {
  return http.createServer((req, res) => {
    const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

    // ── GET /warmer/trigger?token=... ──
    if (req.method === "GET" && url.pathname === "/warmer/trigger") {
      if (!TOKEN) {
        return jsonResponse(res, 500, { error: "WARMER_TOKEN not configured on server" });
      }
      const provided = url.searchParams.get("token");
      if (!provided || provided !== TOKEN) {
        return jsonResponse(res, 401, { error: "Invalid or missing token" });
      }

      // Fire-and-forget — don't await, respond immediately
      runWarmer().catch((err) =>
        console.error("[warmer-server] Warmer failed:", err.message)
      );

      return jsonResponse(res, 202, { status: "started" });
    }

    // ── GET /warmer/status ──
    if (req.method === "GET" && url.pathname === "/warmer/status") {
      const progress = readJSON(PROGRESS_FILE);
      const lastRun = readJSON(SUMMARY_FILE);

      if (progress && progress.running) {
        return jsonResponse(res, 200, {
          running: true,
          started: progress.started,
          current: progress.current,
          total: progress.total,
          lastUrl: progress.lastUrl || null,
          updated: progress.updated,
        });
      }

      if (lastRun) {
        return jsonResponse(res, 200, {
          running: false,
          lastRun: {
            started: lastRun.started,
            finished: lastRun.finished,
            total: lastRun.total,
            successful: lastRun.successful,
            failed: lastRun.failed,
            kinsta: lastRun.kinsta || null,
            cdn: lastRun.cdn || null,
            edge: lastRun.edge || null,
          },
        });
      }

      return jsonResponse(res, 200, { running: false, lastRun: null });
    }

    // ── 404 ──
    jsonResponse(res, 404, { error: "Not found" });
  });
}

module.exports = { createServer };