// Brazilian businesses advertising in the US: runs Portuguese exact-phrase
// searches in the Ad Library (country=US, active ads) and counts which US
// cities and states the advertisers mention in ad text and page names.
//
// Output: data/eua/scan_ads.jsonl (one row per ad) and data/eua/scan_log.jsonl.
// usage: NODE_PATH=$(npm root -g) node src/us_brazil_scan.js [--terms "a,b"] [--limit N]
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1]]);
  return acc;
}, []));

const DEFAULT_TERMS = [
  'orçamento grátis', 'orçamento gratuito', 'empresa brasileira', 'atendemos toda',
  'falamos português', 'limpeza de casas', 'limpeza residencial', 'limpeza de estofados',
  'pintura residencial', 'telhado', 'construção e reforma', 'serviços de construção',
  'brasileiros em', 'comunidade brasileira', 'para brasileiros nos', 'aqui nos EUA',
  'agende sua avaliação', 'chame no whatsapp', 'faça seu orçamento', 'mão de obra',
];

const OUT_DIR = path.join(L.DATA, 'eua');
const ADS = path.join(OUT_DIR, 'scan_ads.jsonl');
const LOG = path.join(OUT_DIR, 'scan_log.jsonl');

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const terms = args.terms ? args.terms.split(',') : DEFAULT_TERMS;
  const done = new Set(L.readJsonl(LOG).filter(r => r.status === 'ok').map(r => r.term));
  const jobs = terms.filter(t => !done.has(t)).slice(0, args.limit ? Number(args.limit) : Infinity);
  console.log(`${jobs.length} searches pending`);

  const browser = await L.newBrowser();
  const ctx = await L.newContext(browser);
  for (const term of jobs) {
    const url = L.keywordUrl(term, null, 'US');
    let res;
    try {
      res = await L.fetchLibrary(ctx, url, { type: 'keyword', term, country: 'US' });
    } catch (e) {
      res = { ok: false, error: String(e).slice(0, 200), ads: [] };
    }
    const status = res.ok ? (res.ads.length ? 'ok' : 'zero') : 'failed';
    for (const ad of res.ads) L.appendJsonl(ADS, { term, ...ad });
    L.appendJsonl(LOG, { term, status, count: res.count ?? null, rows: res.ads.length, at: L.nowIso() });
    console.log(`${status.padEnd(6)} ${String(res.count ?? '-').padStart(6)} total, ${res.ads.length} rows  "${term}"`);
    await L.sleep(L.jitter(10000, 16000));
  }
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
