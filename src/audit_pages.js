// Page audit: for each page id in data/audit_queue.json, loads the advertiser's
// own Library view (briefing URL template) in up to three slices:
//   all  -> total active results in CO + top 30 ads by impressions
//   30d  -> active ads that started 30+ days ago (count + top 30)
//   90d  -> active ads that started 90+ days ago, only when 30d count >= 10
// Output: data/raw/pages/<page_id>.json. Resumable.
//
// usage: node src/audit_pages.js [--limit N] [--queue data/audit_queue.json]
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1]]);
  return acc;
}, []));

const OUT = path.join(L.DATA, 'raw', 'pages');
const LOG = path.join(L.DATA, 'audit_log.jsonl');

async function load(state, url, source, expectNonZero) {
  let res;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      res = await L.fetchLibrary(state.ctx, url, source);
    } catch (e) {
      res = { ok: false, error: String(e).slice(0, 200), ads: [] };
    }
    // A count of 0 where earlier data proves ads exist is the Library's soft limit.
    if (res.ok && !res.captcha && (res.count > 0 || !expectNonZero)) break;
    if (attempt === 2) break;
    console.log(`  backoff (ok=${res.ok} count=${res.count})`);
    await L.sleep(L.jitter(60000, 90000));
  }
  await L.sleep(L.jitter(10000, 16000));
  return res;
}

async function main() {
  const queueFile = args.queue || path.join(L.DATA, 'audit_queue.json');
  const queue = JSON.parse(fs.readFileSync(queueFile, 'utf8'));
  const limit = args.limit ? Number(args.limit) : Infinity;
  const pending = queue.filter(p => !fs.existsSync(path.join(OUT, `${p.page_id}.json`)));
  console.log(`${pending.length} pages pending of ${queue.length}`);

  const browser = await L.newBrowser();
  const state = { browser, ctx: await L.newContext(browser) };
  let n = 0, fails = 0;
  for (const p of pending) {
    if (n++ >= limit) break;
    const d30 = L.daysAgo(30), d90 = L.daysAgo(90);
    const rec = { page_id: p.page_id, page_name: p.page_name, audited_at: L.nowIso(), url: L.pageUrl(p.page_id), slices: {} };

    const sAll = await load(state, L.pageUrl(p.page_id), { type: 'page', slice: 'all' }, true);
    const s30 = await load(state, L.pageUrl(p.page_id, d30), { type: 'page', slice: '30d' },
      sAll.ads.some(a => a.start_date && a.start_date <= d30) || (p.min_start && p.min_start <= d30));
    rec.slices['30d'] = { url: L.pageUrl(p.page_id, d30), max_start: d30, ok: s30.ok, count: s30.count, ads: s30.ads };
    rec.slices.all = { url: rec.url, ok: sAll.ok, count: sAll.count, ads: sAll.ads };
    if (s30.ok && s30.count >= 10) {
      const s90 = await load(state, L.pageUrl(p.page_id, d90), { type: 'page', slice: '90d' },
        s30.ads.some(a => a.start_date && a.start_date <= d90));
      rec.slices['90d'] = { url: L.pageUrl(p.page_id, d90), max_start: d90, ok: s90.ok, count: s90.count, ads: s90.ads };
    }
    rec.validated = Boolean(sAll.ok && sAll.count > 0);
    const ok = sAll.ok && s30.ok;
    fs.writeFileSync(path.join(OUT, `${p.page_id}.json`), JSON.stringify(rec));
    L.appendJsonl(LOG, { page_id: p.page_id, page_name: p.page_name, ok, total: sAll.count, c30: s30.count, c90: rec.slices['90d'] ? rec.slices['90d'].count : null, at: rec.audited_at });
    console.log(`[${n}/${Math.min(pending.length, limit)}] ${p.page_name} (${p.page_id}) total=${sAll.count} 30d+=${s30.count} 90d+=${rec.slices['90d'] ? rec.slices['90d'].count : '-'}`);
    fails = ok ? 0 : fails + 1;
    if (fails >= 3) {
      console.log('3 consecutive failures; cooling down 5 min');
      await L.sleep(300000);
      fails = 0;
    }
  }
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
