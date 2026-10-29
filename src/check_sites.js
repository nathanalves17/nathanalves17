// Destination check: renders each landing page from data/site_queue.json and
// stores what is needed to judge the checkout model offline (visible text,
// COD-app markers in the HTML, currency/price metadata, WhatsApp links).
// Output: data/sites/raw/<sha1(url)>.json. Resumable. Does not submit forms.
//
// usage: node src/check_sites.js [--limit N] [--concurrency 4]
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const L = require('./lib');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1]]);
  return acc;
}, []));

const OUT = path.join(L.DATA, 'sites', 'raw');
fs.mkdirSync(OUT, { recursive: true });

const APP_MARKERS = [
  'releasit', 'easysell', 'easy-sell', 'cod-form', 'codform', 'cod_form', '_rsi_cod', 'ecomsell',
  'hulkapps.*cod', 'cod-order-form', 'rapidcod', 'zipcod', 'codmonster', 'cod monster', 'sellgo',
  'dropi\\.co', 'mastershop', 'cash on delivery', 'cash_on_delivery', 'contraentrega', 'contra entrega',
  'formulario-cod', 'cod-button', 'buy-cod', 'cod_button',
];

const hash = s => crypto.createHash('sha1').update(s).digest('hex').slice(0, 16);

async function check(ctx, item) {
  const page = await ctx.newPage();
  const rec = { url: item.url, checked_at: L.nowIso() };
  try {
    const resp = await page.goto(item.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    rec.status = resp ? resp.status() : null;
    await page.waitForTimeout(4000);
    await page.mouse.wheel(0, 2500);
    await page.waitForTimeout(2500);
    rec.final_url = page.url();
    rec.title = await page.title();
    const text = await page.evaluate(() => document.body ? document.body.innerText : '');
    rec.text = text.slice(0, 40000);
    const html = await page.content();
    const low = html.toLowerCase();
    rec.html_len = html.length;
    rec.app_markers = APP_MARKERS.filter(m => new RegExp(m).test(low));
    rec.shopify = /cdn\.shopify\.com|shopify\.theme|window\.shopify/i.test(html);
    rec.platform_hints = ['shopify', 'woocommerce', 'vtex', 'tiendanube', 'wix', 'jumpseller', 'dropi', 'lovable', 'hotmart']
      .filter(p => low.includes(p));
    rec.currency_hints = [...new Set((html.match(/("currency"\s*:\s*"[A-Z]{3}"|"active"\s*:\s*"[A-Z]{3}"|priceCurrency"?\s*[:=]\s*"[A-Z]{3}"|og:price:currency"\s+content="[A-Z]{3}")/g) || []).slice(0, 20))];
    rec.jsonld_offers = await page.$$eval('script[type="application/ld+json"]', els => {
      const out = [];
      const walk = o => {
        if (!o || typeof o !== 'object') return;
        if (Array.isArray(o)) return o.forEach(walk);
        if (o.price || o.lowPrice) out.push({ price: o.price || o.lowPrice, currency: o.priceCurrency || null, name: o.name || null });
        Object.values(o).forEach(walk);
      };
      els.forEach(e => { try { walk(JSON.parse(e.textContent)); } catch (err) { /* ignore broken JSON-LD */ } });
      return out.slice(0, 10);
    });
    rec.og = await page.$$eval('meta[property^="og:"]', els => Object.fromEntries(els.map(e => [e.getAttribute('property'), e.getAttribute('content')])));
    rec.whatsapp_links = [...new Set((html.match(/https?:\/\/(wa\.me|api\.whatsapp\.com|chat\.whatsapp\.com|web\.whatsapp\.com)[^"'\s<]*/gi) || []).slice(0, 5))];
    rec.cod_html_snippets = [...new Set((html.match(/.{0,80}(contra ?entrega|pago al recibir|paga al recibir|pagar al recibir|paga en casa|pago en casa).{0,80}/gi) || []).slice(0, 8))];
    rec.form_fields = await page.$$eval('input,select,textarea', els => els.map(e => (e.getAttribute('name') || e.getAttribute('placeholder') || e.getAttribute('aria-label') || '').slice(0, 40)).filter(Boolean).slice(0, 60));
  } catch (e) {
    rec.error = String(e).slice(0, 300);
  } finally {
    await page.close();
  }
  return rec;
}

async function main() {
  const queue = JSON.parse(fs.readFileSync(args.queue || path.join(L.DATA, 'site_queue.json'), 'utf8'));
  const limit = args.limit ? Number(args.limit) : Infinity;
  const conc = Number(args.concurrency || 4);
  const pending = queue.filter(q => !fs.existsSync(path.join(OUT, hash(q.url) + '.json'))).slice(0, limit);
  console.log(`${pending.length} sites pending of ${queue.length}`);
  const browser = await L.newBrowser();
  let i = 0, done = 0;
  async function worker() {
    const ctx = await L.newContext(browser);
    while (i < pending.length) {
      const item = pending[i++];
      const rec = await check(ctx, item);
      fs.writeFileSync(path.join(OUT, hash(item.url) + '.json'), JSON.stringify(rec));
      done++;
      console.log(`[${done}/${pending.length}] ${rec.status || rec.error && 'ERR'} ${item.url.slice(0, 100)} markers=${(rec.app_markers || []).join(',')}`);
    }
    await ctx.close();
  }
  await Promise.all(Array.from({ length: conc }, worker));
  await browser.close();
}

module.exports = { hash };
if (require.main === module) main().catch(e => { console.error(e); process.exit(1); });
