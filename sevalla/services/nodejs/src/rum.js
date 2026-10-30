'use strict';

/**
 * Real user monitoring (RUM) for pbservices.ge
 *
 * Goal: find out why leads drop after cache purges. For every page view we
 * record the visitor's country, the Cloudflare location (PoP) that served it,
 * whether the page came from the edge cache (HIT) or not (MISS), load times
 * and what happened with the contact form and the Telegram / WhatsApp links.
 * No IP address, cookie or form content is stored.
 *
 * Routes (wired in warmer-server.js):
 *   GET  /rum.js                       the browser script, add it once to the site:
 *                                      <script src="https://<app-domain>/rum.js" async></script>
 *   POST /rum                          beacons sent by the script
 *   GET  /rum/summary?token=..&days=7  daily report (token = RUM_TOKEN or WARMER_TOKEN)
 *
 * Environment:
 *   DATA_DIR             folder for data files (default: app folder). Point it to a
 *                        Sevalla persistent disk to keep the data across deploys.
 *   RUM_TOKEN            token for the report (default: WARMER_TOKEN)
 *   RUM_ALLOWED_ORIGINS  default https://pbservices.ge,https://www.pbservices.ge
 *   RUM_KEEP_DAYS        default 45
 *   RUM_MAINTENANCE_HOURS  admin maintenance window in Tbilisi hours, default 4-7
 *                        (04:00-07:00). The report shows it apart in by_hour.
 */

const fs = require('fs');
const path = require('path');

const RUM_DIR = path.join(process.env.DATA_DIR || path.join(__dirname, '..'), 'rum');
const KEEP_DAYS = parseInt(process.env.RUM_KEEP_DAYS, 10) || 45;
const MAX_FILE_BYTES = 50 * 1024 * 1024;
const ALLOWED_ORIGINS = (process.env.RUM_ALLOWED_ORIGINS || 'https://pbservices.ge,https://www.pbservices.ge')
  .split(',').map((s) => s.trim()).filter(Boolean);

// ── Browser script ──
// Runs after the page has loaded, never blocks rendering, skips logged-in users.
const CLIENT_JS = `(function () {
  try {
    if (window.__pbsRum || !window.performance || !performance.getEntriesByType) return;
    window.__pbsRum = 1;
    var script = document.currentScript;
    var base = script && script.src ? new URL(script.src).origin : '';
    var nav = performance.getEntriesByType('navigation')[0];
    if (!base || !nav) return;

    var r = function (n) { return n > 0 ? Math.round(n) : 0; };
    var d = {
      v: 1,
      pv: Math.random().toString(36).slice(2, 10) + Date.now().toString(36),
      seq: 0,
      path: location.pathname.slice(0, 150),
      qs: location.search ? 1 : 0,
      // Which ad / tracking parameters the URL has (names only). Google Ads adds
      // gclid (or gbraid / wbraid) to every click, and those URLs skip the edge cache.
      qk: (function () {
        if (!location.search) return 'none';
        var keys = location.search.slice(1).split('&').map(function (p) { return p.split('=')[0].toLowerCase(); });
        var groups = { gclid: ['gclid'], gbraid: ['gbraid', 'wbraid'], gad: ['gad_source', 'gad_campaignid'], utm: ['utm_'], fbclid: ['fbclid'], msclkid: ['msclkid'] };
        var found = [];
        for (var g in groups) {
          if (keys.some(function (k) { return groups[g].some(function (x) { return x === 'utm_' ? k.indexOf('utm_') === 0 : k === x; }); })) found.push(g);
        }
        return found.length ? found.join(',') : 'other';
      })(),
      ref: document.referrer ? (function () { try { return new URL(document.referrer).hostname; } catch (e) { return ''; } })() : '',
      nt: nav.type,
      proto: nav.nextHopProtocol || '',
      ttfb: r(nav.responseStart),
      wait: r(nav.responseStart - nav.requestStart),
      size: nav.transferSize || 0,
      mob: window.matchMedia && matchMedia('(max-width: 768px)').matches ? 1 : 0,
      net: navigator.connection && navigator.connection.effectiveType || '',
      form: 0, frender: 0, fstart: 0, fsubmit: 0, fvfail: 0, fok: 0, ferr: 0,
      tg: 0, wa: 0, tel: 0, mail: 0
    };

    var loggedIn = function () { return document.body && document.body.classList.contains('logged-in'); };

    // Which known cookies the visitor has (names only, never values), to find
    // the cookie that makes some visits skip the cache. Read as early as possible.
    var CK = { pll: /^pll_language$/, wpml: /wpml/i, wsf: /^ws_form_/, ch: /^_channel_/, ym: /^_ym_/, ga: /^_ga/, gcl: /^_gcl_/,
      cmt: /^comment_author/, pass: /^wp-postpass/, wps: /^wp-settings/, test: /^wordpress_test_cookie$/ };
    var names = document.cookie ? document.cookie.split(';').map(function (c) { return c.split('=')[0].trim(); }) : [];
    var flags = [];
    for (var k in CK) { if (names.some(function (n) { return CK[k].test(n); })) flags.push(k); }
    d.ck = flags.join(',');
    d.nck = names.length;

    // Paint timings
    try {
      new PerformanceObserver(function (l) {
        l.getEntries().forEach(function (e) { if (e.name === 'first-contentful-paint') d.fcp = r(e.startTime); });
      }).observe({ type: 'paint', buffered: true });
      new PerformanceObserver(function (l) {
        var e = l.getEntries(); if (e.length) d.lcp = r(e[e.length - 1].startTime);
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {}

    // Contact form. WS Form triggers its events on document as "wsf-<name>"
    // (the docs list them as "wsft-<name>"), so both prefixes are listened to.
    var hookForm = function () {
      d.form = document.querySelector('.wsf-form') ? 1 : 0;
      if (d.form && document.querySelector('.wsf-form input, .wsf-form textarea')) d.frender = d.frender || -1;
      var $ = window.jQuery;
      if (!$ || hookForm.done) return;
      hookForm.done = 1;
      var ev = function (name) { return 'wsf-' + name + ' wsft-' + name; };
      $(document).on(ev('rendered'), function () { d.frender = r(performance.now()); });
      $(document).on(ev('submit-before'), function () { d.fsubmit++; });
      $(document).on(ev('submit-validate-fail'), function () { d.fvfail++; });
      $(document).on(ev('submit-success'), function () { d.fok++; send(); });
      $(document).on(ev('submit-error'), function () { d.ferr++; send(); });
    };
    document.addEventListener('focusin', function (e) {
      if (!d.fstart && e.target.closest && e.target.closest('.wsf-form')) d.fstart = r(performance.now());
    }, true);

    // Contact link clicks
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[href]');
      if (!a) return;
      var h = a.getAttribute('href') || '';
      if (/t\\.me\\/|telegram\\.me\\//i.test(h)) d.tg++;
      else if (/wa\\.me\\/|whatsapp\\.com/i.test(h)) d.wa++;
      else if (/^tel:/i.test(h)) d.tel++;
      else if (/^mailto:/i.test(h)) d.mail++;
      else return;
      send();
    }, true);

    var send = function () {
      if (loggedIn()) return;
      d.seq++;
      d.dcl = r(nav.domContentLoadedEventEnd);
      d.load = r(nav.loadEventEnd);
      var body = JSON.stringify(d);
      try {
        if (navigator.sendBeacon && navigator.sendBeacon(base + '/rum', new Blob([body], { type: 'text/plain' }))) return;
      } catch (e) {}
      try { fetch(base + '/rum', { method: 'POST', body: body, keepalive: true, mode: 'no-cors' }); } catch (e) {}
    };

    var afterLoad = function () {
      hookForm();
      setTimeout(hookForm, 3000);
      // Cloudflare location and country
      fetch('/cdn-cgi/trace', { credentials: 'omit' }).then(function (res) { return res.text(); }).then(function (t) {
        var m = t.match(/^colo=(\\w+)/m); if (m) d.colo = m[1];
        m = t.match(/^loc=(\\w+)/m); if (m) d.loc = m[1];
      }).catch(function () {});
      // Edge cache status of this page view: the edge copy's age tells whether
      // it existed before this visit (HIT) or was just created by it (MISS).
      // HEAD requests skip the Kinsta edge, so a GET is used and stopped as
      // soon as the headers arrive (the page body is not downloaded again).
      if (d.qs) { d.edge = 'qs'; }
      else if (d.nt === 'back_forward') { d.edge = 'bfcache'; }
      else if (window.AbortController) {
        setTimeout(function () {
          var ctrl = new AbortController();
          fetch(location.pathname, { credentials: 'omit', signal: ctrl.signal }).then(function (res) {
            var type = (res.headers.get('ki-cache-type') || '').toLowerCase();
            var age = parseInt(res.headers.get('age') || '0', 10);
            var elapsed = (Date.now() - performance.timeOrigin) / 1000;
            d.edge = type === 'edge' ? (age > elapsed + 5 ? 'hit' : 'miss') : (type || 'none');
            d.origin = (res.headers.get('x-kinsta-cache') || '').toLowerCase();
            d.age = age;
            ctrl.abort();
          }).catch(function () { if (!d.edge) d.edge = 'err'; });
        }, 1500);
      }
      // First report a few seconds after load, then again when the visitor leaves.
      setTimeout(send, 8000);
    };

    if (document.readyState === 'complete') afterLoad();
    else window.addEventListener('load', afterLoad);
    document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden') send(); });
    window.addEventListener('pagehide', send);
  } catch (e) {}
})();
`;

// ── Storage ──

const FIELDS = {
  v: 'n', pv: 's', seq: 'n', path: 's', qs: 'n', ref: 's', nt: 's', proto: 's', ttfb: 'n', wait: 'n',
  size: 'n', mob: 'n', net: 's', fcp: 'n', lcp: 'n', dcl: 'n', load: 'n', colo: 's', loc: 's',
  edge: 's', origin: 's', age: 'n', form: 'n', frender: 'n', fstart: 'n', fsubmit: 'n', fvfail: 'n',
  fok: 'n', ferr: 'n', tg: 'n', wa: 'n', tel: 'n', mail: 'n', ck: 's', nck: 'n', qk: 's',
};

function clean(input) {
  if (!input || typeof input !== 'object' || typeof input.pv !== 'string') return null;
  const out = {};
  for (const [k, type] of Object.entries(FIELDS)) {
    const v = input[k];
    if (v === undefined || v === null) continue;
    if (type === 'n' && typeof v === 'number' && Number.isFinite(v)) out[k] = Math.max(-1, Math.min(Math.round(v), 1e9));
    if (type === 's' && typeof v === 'string') out[k] = v.replace(/[^\w\-./:%, ]/g, '').slice(0, 150);
  }
  return out.pv ? out : null;
}

function dayKey(ts) {
  return new Date(ts).toISOString().slice(0, 10);
}

function store(record) {
  fs.mkdirSync(RUM_DIR, { recursive: true });
  const file = path.join(RUM_DIR, dayKey(Date.now()) + '.jsonl');
  try {
    if (fs.statSync(file).size > MAX_FILE_BYTES) return;
  } catch (_) { /* new file */ }
  fs.appendFileSync(file, JSON.stringify(Object.assign({ t: Date.now() }, record)) + '\n');
}

function cleanupOldFiles() {
  try {
    const limit = dayKey(Date.now() - KEEP_DAYS * 86400000);
    for (const f of fs.readdirSync(RUM_DIR)) {
      if (f.endsWith('.jsonl') && f.slice(0, 10) < limit) fs.unlinkSync(path.join(RUM_DIR, f));
    }
  } catch (_) { /* nothing to clean */ }
}
setInterval(cleanupOldFiles, 6 * 3600 * 1000).unref();

// ── Report ──

function median(list) {
  const a = list.filter((n) => typeof n === 'number' && n > 0).sort((x, y) => x - y);
  if (!a.length) return null;
  return a[Math.floor((a.length - 1) / 2)];
}

function group(views) {
  const sum = (k) => views.reduce((s, v) => s + (v[k] > 0 ? 1 : 0), 0);
  return {
    views: views.length,
    ttfb_ms: median(views.map((v) => v.ttfb)),
    lcp_ms: median(views.map((v) => v.lcp)),
    load_ms: median(views.map((v) => v.load)),
    with_form: sum('form'),
    form_started: sum('fstart'),
    form_submitted: sum('fsubmit'),
    form_success: sum('fok'),
    form_error: sum('ferr'),
    form_validation_fail: sum('fvfail'),
    telegram_clicks: sum('tg'),
    whatsapp_clicks: sum('wa'),
  };
}

function by(views, key, top) {
  const map = new Map();
  for (const v of views) {
    const k = v[key] || 'unknown';
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(v);
  }
  return [...map.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, top)
    .map(([k, list]) => Object.assign({ [key]: k, edge_miss_pct: pct(list) }, group(list)));
}

function pct(list) {
  const known = list.filter((v) => v.edge === 'hit' || v.edge === 'miss');
  if (!known.length) return null;
  return Math.round((known.filter((v) => v.edge === 'miss').length / known.length) * 100);
}

/**
 * For each tracked cookie: how often visits WITH it skip the cache (edge "none")
 * compared to visits WITHOUT it. The cookie that causes the bypass stands out.
 */
function cookieReport(views) {
  const tracked = views.filter((v) => typeof v.ck === 'string' && ['hit', 'miss', 'none'].includes(v.edge));
  const skip = (list) => (list.length ? Math.round((list.filter((v) => v.edge === 'none').length / list.length) * 100) : null);
  const rows = [{ cookie: 'all visits', views: tracked.length, skip_cache_pct: skip(tracked), ttfb_ms: median(tracked.map((v) => v.ttfb)) }];
  const names = new Set();
  tracked.forEach((v) => v.ck.split(',').filter(Boolean).forEach((n) => names.add(n)));
  for (const name of names) {
    const has = (v) => v.ck.split(',').includes(name);
    const withIt = tracked.filter(has);
    const without = tracked.filter((v) => !has(v));
    rows.push({
      cookie: name,
      views_with: withIt.length,
      skip_cache_pct_with: skip(withIt),
      skip_cache_pct_without: skip(without),
      ttfb_ms_with: median(withIt.map((v) => v.ttfb)),
      ttfb_ms_without: median(without.map((v) => v.ttfb)),
    });
  }
  return [rows[0]].concat(rows.slice(1).sort((a, b) => (b.skip_cache_pct_with || 0) - (a.skip_cache_pct_with || 0)));
}

function readDay(day) {
  const file = path.join(RUM_DIR, day + '.jsonl');
  const latest = new Map();
  let text = '';
  try { text = fs.readFileSync(file, 'utf8'); } catch (_) { return []; }
  for (const line of text.split('\n')) {
    if (!line) continue;
    try {
      const r = JSON.parse(line);
      const prev = latest.get(r.pv);
      if (!prev || (r.seq || 0) >= (prev.seq || 0)) latest.set(r.pv, Object.assign({}, prev, r));
    } catch (_) { /* skip bad line */ }
  }
  return [...latest.values()];
}

// Tbilisi is UTC+4 all year (no daylight saving time).
const TBILISI_OFFSET_H = 4;
// Admin maintenance window in Tbilisi hours [start, end), e.g. "4-7" = 04:00-07:00.
const MAINT = (process.env.RUM_MAINTENANCE_HOURS || '4-7').split('-').map(Number);

function tbilisiHour(ts) {
  return (new Date(ts).getUTCHours() + TBILISI_OFFSET_H) % 24;
}

function inMaintenance(h) {
  const [a, b] = MAINT;
  if (!Number.isInteger(a) || !Number.isInteger(b)) return false;
  return a <= b ? h >= a && h < b : h >= a || h < b;
}

/**
 * Views per Tbilisi hour, plus the maintenance window vs the rest of the day,
 * so admin purges in the morning can be told apart from normal behaviour.
 * Each row also has the form funnel and click counts, to check whether leads
 * per hour follow cold-edge hours or simply the visitors' local time.
 */
function hourReport(views) {
  const timed = views.filter((v) => typeof v.t === 'number');
  const skip = (list) => {
    const known = list.filter((v) => ['hit', 'miss', 'none'].includes(v.edge));
    return known.length ? Math.round((known.filter((v) => v.edge === 'none').length / known.length) * 100) : null;
  };
  // Same fields as the other sections (views, timings, form and click counts),
  // so leads per hour can be compared with cold-edge hours.
  const row = (list) => Object.assign({ edge_miss_pct: pct(list), skip_cache_pct: skip(list) }, group(list));
  const hours = [];
  for (let h = 0; h < 24; h++) {
    const list = timed.filter((v) => tbilisiHour(v.t) === h);
    if (list.length) hours.push(Object.assign({ hour_tbilisi: String(h).padStart(2, '0') + ':00', maintenance: inMaintenance(h) }, row(list)));
  }
  return {
    maintenance_window_tbilisi: MAINT.join('-'),
    maintenance: row(timed.filter((v) => inMaintenance(tbilisiHour(v.t)))),
    rest_of_day: row(timed.filter((v) => !inMaintenance(tbilisiHour(v.t)))),
    hours,
  };
}

function summary(days) {
  const out = { generated: new Date().toISOString(), days: [] };
  const all = [];
  for (let i = days - 1; i >= 0; i--) {
    const day = dayKey(Date.now() - i * 86400000);
    const views = readDay(day);
    if (!views.length) continue;
    all.push(...views);
    out.days.push(Object.assign({ date: day, edge_miss_pct: pct(views) }, group(views), {
      by_edge: by(views, 'edge', 6),
    }));
  }
  out.total = Object.assign({ edge_miss_pct: pct(all) }, group(all));
  out.by_edge = by(all, 'edge', 6);
  out.by_country = by(all, 'loc', 15);
  out.by_cloudflare_location = by(all, 'colo', 15);
  out.by_page = by(all, 'path', 15);
  out.by_cookie = cookieReport(all);
  out.by_query = by(all, 'qk', 10);
  out.by_hour = hourReport(all);
  return out;
}

// ── HTTP handler ──

function cors(req, res) {
  const origin = req.headers.origin;
  if (origin && ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
  }
}

/**
 * Handles the RUM routes. Returns true when the request was handled.
 */
function handle(req, res, url) {
  if (req.method === 'GET' && url.pathname === '/rum.js') {
    res.writeHead(200, {
      'Content-Type': 'application/javascript; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(CLIENT_JS);
    return true;
  }

  if (url.pathname === '/rum' && req.method === 'OPTIONS') {
    cors(req, res);
    res.setHeader('Access-Control-Allow-Methods', 'POST');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.writeHead(204);
    res.end();
    return true;
  }

  if (url.pathname === '/rum' && req.method === 'POST') {
    cors(req, res);
    let raw = '';
    req.on('data', (c) => {
      raw += c;
      if (raw.length > 8192) req.destroy();
    });
    req.on('end', () => {
      try {
        const record = clean(JSON.parse(raw));
        if (record) store(record);
      } catch (_) { /* ignore bad beacons */ }
      res.writeHead(204);
      res.end();
    });
    return true;
  }

  if (req.method === 'GET' && url.pathname === '/rum/summary') {
    const token = process.env.RUM_TOKEN || require('../config/warmer-config').WARMER_TOKEN;
    if (!token || url.searchParams.get('token') !== token) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Invalid or missing token' }));
      return true;
    }
    const days = Math.max(1, Math.min(parseInt(url.searchParams.get('days'), 10) || 7, KEEP_DAYS));
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(summary(days), null, 2));
    return true;
  }

  return false;
}

module.exports = { handle, summary, clean, CLIENT_JS, RUM_DIR };
