// Shared helpers for reading the Meta Ad Library (logged-out) with Playwright.
// The Library server-renders the first page of results (up to 30 ad groups) as
// JSON inside <script type="application/json">; logged-out GraphQL pagination
// answers "Rate limit exceeded", so every URL yields at most that first page.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DATA = path.join(ROOT, 'data');
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36';
const LIB = 'https://www.facebook.com/ads/library/';

const sleep = ms => new Promise(r => setTimeout(r, ms));
const jitter = (min, max) => min + Math.floor(Math.random() * (max - min));
const nowIso = () => new Date().toISOString();

function daysAgo(n, from = new Date()) {
  const d = new Date(from.getTime() - n * 86400000);
  return d.toISOString().slice(0, 10);
}

function baseParams() {
  return [
    ['active_status', 'active'], ['ad_type', 'all'], ['country', 'CO'],
    ['is_targeted_country', 'false'], ['media_type', 'all'],
  ];
}

function encode(params) {
  return params.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
}

function sortParams() {
  return [['sort_data[direction]', 'desc'], ['sort_data[mode]', 'total_impressions']];
}

function dateParams(maxDate) {
  return maxDate ? [['start_date[min]', ''], ['start_date[max]', maxDate]] : [];
}

// Page URL in the exact shape of the briefing template.
function pageUrl(pageId, maxDate) {
  return LIB + '?' + encode([...baseParams(), ['search_type', 'page'], ...sortParams(), ...dateParams(maxDate), ['view_all_page_id', String(pageId)]]);
}

function keywordUrl(q, maxDate) {
  return LIB + '?' + encode([...baseParams(), ['q', `"${q}"`], ['search_type', 'keyword_exact_phrase'], ...sortParams(), ...dateParams(maxDate)]);
}

function adUrl(id) {
  return `${LIB}?id=${id}`;
}

function findKey(o, k, out = []) {
  if (o && typeof o === 'object') {
    if (Object.prototype.hasOwnProperty.call(o, k)) out.push(o[k]);
    for (const v of Object.values(o)) findKey(v, k, out);
  }
  return out;
}

function trunc(s, n) {
  if (!s) return s || null;
  return s.length > n ? s.slice(0, n) + '…' : s;
}

// Stable identifiers for the media of a creative, so re-uploads of the same
// video or image across ads count as one creative.
function mediaKeys(snap) {
  const keys = new Set();
  const addVideo = v => {
    const u = v.video_hd_url || v.video_sd_url || '';
    const m = u.match(/[?&]efg=([^&]+)/);
    if (m) {
      try {
        const j = JSON.parse(Buffer.from(decodeURIComponent(m[1]), 'base64').toString('utf8'));
        if (j.xpv_asset_id) { keys.add('v:' + j.xpv_asset_id); return; }
      } catch (e) { /* fall through to the preview image */ }
    }
    const p = (v.video_preview_image_url || '').split('?')[0].split('/').pop();
    if (p) keys.add('vp:' + p.split('_').slice(0, 2).join('_'));
  };
  const addImage = i => {
    const p = (i.original_image_url || i.resized_image_url || '').split('?')[0].split('/').pop();
    if (p) keys.add('i:' + p.split('_').slice(0, 2).join('_'));
  };
  (snap.videos || []).forEach(addVideo);
  (snap.images || []).forEach(addImage);
  (snap.cards || []).forEach(c => {
    if (c.video_hd_url || c.video_sd_url || c.video_preview_image_url) addVideo(c);
    if (c.original_image_url || c.resized_image_url) addImage(c);
  });
  return [...keys];
}

function normalizeAd(a, source) {
  const s = a.snapshot || {};
  const cards = (s.cards || []).map(c => ({
    link_url: c.link_url || null,
    title: trunc(c.title, 200),
    body: trunc(c.body, 400),
    cta_type: c.cta_type || null,
  }));
  return {
    ad_archive_id: a.ad_archive_id,
    page_id: a.page_id || s.page_id,
    page_name: s.page_name || a.page_name || null,
    page_profile_uri: s.page_profile_uri || null,
    page_like_count: s.page_like_count ?? null,
    page_categories: s.page_categories || [],
    is_active: a.is_active,
    start_date: a.start_date ? new Date(a.start_date * 1000).toISOString().slice(0, 10) : null,
    end_date: a.end_date ? new Date(a.end_date * 1000).toISOString().slice(0, 10) : null,
    collation_id: a.collation_id || null,
    collation_count: a.collation_count ?? null,
    publisher_platform: a.publisher_platform || [],
    display_format: s.display_format || null,
    cta_type: s.cta_type || null,
    cta_text: s.cta_text || null,
    link_url: s.link_url || null,
    caption: s.caption || null,
    title: trunc(s.title, 300),
    body: trunc(s.body && s.body.text, 1500),
    link_description: trunc(s.link_description, 300),
    cards,
    media_keys: mediaKeys(s),
    source,
  };
}

async function newBrowser() {
  return chromium.launch({ proxy: { server: process.env.HTTPS_PROXY } });
}

async function newContext(browser) {
  return browser.newContext({ locale: 'es-CO', userAgent: UA, viewport: { width: 1366, height: 900 } });
}

function withTimeout(promise, ms, label) {
  let timer;
  const t = new Promise((_, rej) => { timer = setTimeout(() => rej(new Error(`timeout ${ms}ms: ${label}`)), ms); });
  return Promise.race([promise, t]).finally(() => clearTimeout(timer));
}

// Loads one Library URL and returns {count, ads, captcha, ok}. "ok" is false
// when no server-rendered result block is present at all. The whole load is
// capped at 90 s: page.evaluate has no timeout of its own and a stuck renderer
// would otherwise block the run indefinitely.
async function fetchLibrary(ctx, url, source) {
  const page = await ctx.newPage();
  try {
    return await withTimeout(readLibraryPage(page, url, source), 90000, url);
  } finally {
    await withTimeout(page.close({ runBeforeUnload: false }), 15000, 'page.close').catch(() => {});
  }
}

async function readLibraryPage(page, url, source) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2500);
  let jsons = await page.$$eval('script[type="application/json"]', els => els.map(e => e.textContent));
  if (!jsons.some(j => j.includes('search_results_connection'))) {
    await page.waitForTimeout(5000);
    jsons = await page.$$eval('script[type="application/json"]', els => els.map(e => e.textContent));
  }
  for (const j of jsons) {
    if (!j.includes('search_results_connection')) continue;
    const o = JSON.parse(j);
    const conn = findKey(o, 'search_results_connection')[0];
    const captcha = findKey(o, 'xfb_ad_library_is_captcha_required')[0] === true;
    const raw = conn.edges.flatMap(e => e.node.collated_results || []);
    return { ok: true, count: conn.count, captcha, ads: raw.map(a => normalizeAd(a, source)) };
  }
  const text = await page.evaluate(() => document.body ? document.body.innerText : '');
  return { ok: false, count: null, captcha: /captcha|seguridad/i.test(text), ads: [], text: text.slice(0, 300) };
}

function appendJsonl(file, obj) {
  fs.appendFileSync(file, JSON.stringify(obj) + '\n');
}

function readJsonl(file) {
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l));
}

module.exports = {
  ROOT, DATA, UA, sleep, jitter, nowIso, daysAgo, pageUrl, keywordUrl, adUrl,
  newBrowser, newContext, fetchLibrary, appendJsonl, readJsonl, findKey,
};
