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

// respond.io posts replies to <Webhook URL for Outgoing message>/message
const OUTGOING_PATH = /^\/respond\/outgoing(\/message)?\/?$/;

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
            statusCodes: lastRun.statusCodes || null,
            redirectUrls: lastRun.redirectUrls || null,
            unknowns: lastRun.unknowns || null,
            failedUrls: lastRun.failedUrls || null,
          },
        });
      }

      return jsonResponse(res, 200, { running: false, lastRun: null });
    }

    // ── GET /warmer/summary ──
    if (req.method === "GET" && url.pathname === "/warmer/summary") {
      const lastRun = readJSON(SUMMARY_FILE);
      if (!lastRun) {
        return jsonResponse(res, 200, { lastRun: null });
      }
      return jsonResponse(res, 200, {
        started: lastRun.started,
        finished: lastRun.finished,
        total: lastRun.total,
        successful: lastRun.successful,
        failed: lastRun.failed,
        kinsta: lastRun.kinsta || null,
        cdn: lastRun.cdn || null,
        edge: lastRun.edge || null,
        statusCodes: lastRun.statusCodes || null,
        redirectUrls: lastRun.redirectUrls || null,
        unknowns: lastRun.unknowns || null,
        failedUrls: lastRun.failedUrls || null,
      });
    }

    // ── GET /respond/outgoing (health check, e.g. when opened in a browser) ──
    if (req.method === "GET" && OUTGOING_PATH.test(url.pathname)) {
      return jsonResponse(res, 200, { status: "ok", accepts: "POST from respond.io" });
    }

    // ── POST /respond/outgoing (replies written in respond.io → Telegram) ──
    if (req.method === "POST" && OUTGOING_PATH.test(url.pathname)) {
      const expected = process.env.RESPOND_CUSTOM_CHANNEL_TOKEN;
      const auth = String(req.headers.authorization || "");
      if (!expected || auth !== "Bearer " + expected) {
        return jsonResponse(res, 401, { error: "Unauthorized" });
      }
      let raw = "";
      req.on("data", (c) => { raw += c; if (raw.length > 1e6) req.destroy(); });
      req.on("end", async () => {
        try {
          const body = JSON.parse(raw || "{}");
          const mId = await require("./business-bot").sendFromRespond(body.contactId, body.message);
          jsonResponse(res, 200, { mId });
        } catch (err) {
          console.error("[respond] outgoing failed:", err.message);
          jsonResponse(res, 400, { error: err.message });
        }
      });
      return;
    }

    // ── 404 ──
    jsonResponse(res, 404, { error: "Not found" });
  });
}

module.exports = { createServer };
