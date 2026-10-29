// Keyword discovery: runs each term of keywords_colombia.json against the Ad
// Library (CO, all ads, active, exact phrase, sorted by impressions) and stores
// the server-rendered results. Resumable: finished (term, variant) pairs found
// in data/search_log.jsonl are skipped.
//
// Requests are paced (10–16 s apart) in one browser session; when the Library
// answers with an empty result set (its soft rate limit) the script backs off
// and retries once, then records the search as "zero" for a later re-check.
//
// usage: node src/discover.js [--cats A_,B_] [--variants all,30d] [--limit N] [--recheck-zero 1]
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1]]);
  return acc;
}, []));

const LOG = path.join(L.DATA, 'search_log.jsonl');
const OUT = path.join(L.DATA, 'raw', 'search');
const VARIANTS = { all: null, '30d': L.daysAgo(30), '90d': L.daysAgo(90) };

function slug(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

async function main() {
  const kw = JSON.parse(fs.readFileSync(path.join(L.ROOT, 'keywords_colombia.json'), 'utf8'));
  const catFilter = args.cats ? args.cats.split(',') : null;
  const variants = (args.variants || 'all,30d').split(',');
  const limit = args.limit ? Number(args.limit) : Infinity;

  const doneStatus = args['recheck-zero'] ? ['ok'] : ['ok', 'zero'];
  const done = new Set(L.readJsonl(LOG).filter(r => doneStatus.includes(r.status)).map(r => `${r.term}|${r.variant}`));
  const jobs = [];
  for (const [cat, terms] of Object.entries(kw.categories)) {
    if (catFilter && !catFilter.some(c => cat.startsWith(c))) continue;
    for (const t of terms) {
      const term = typeof t === 'string' ? t : t.term;
      for (const v of variants) if (!done.has(`${term}|${v}`)) jobs.push({ cat, term, variant: v });
    }
  }
  console.log(`${jobs.length} searches pending`);

  const browser = await L.newBrowser();
  const ctx = await L.newContext(browser);
  let fails = 0, n = 0;
  for (const job of jobs) {
    if (n >= limit) break;
    n++;
    const url = L.keywordUrl(job.term, VARIANTS[job.variant]);
    let res, attempt = 0;
    while (true) {
      attempt++;
      try {
        res = await L.fetchLibrary(ctx, url, { type: 'keyword', term: job.term, variant: job.variant });
      } catch (e) {
        res = { ok: false, error: String(e).slice(0, 200), ads: [] };
      }
      const suspicious = !res.ok || res.captcha || res.count === 0;
      if (!suspicious || attempt >= 2) break;
      console.log(`  backoff ${job.term} [${job.variant}] (ok=${res.ok} count=${res.count})`);
      await L.sleep(L.jitter(60000, 90000));
    }
    const status = !res.ok || res.captcha ? 'failed' : res.count === 0 ? 'zero' : 'ok';
    fails = status === 'failed' ? fails + 1 : 0;
    const file = path.join(OUT, `${slug(job.term)}__${job.variant}.json`);
    if (status !== 'failed') {
      fs.writeFileSync(file, JSON.stringify({ ...job, url, fetched_at: L.nowIso(), count: res.count, ads: res.ads }, null, 0));
    }
    L.appendJsonl(LOG, { ...job, url, status, count: res.count ?? null, ads_returned: res.ads.length, fetched_at: L.nowIso(), error: res.error || null });
    const pages = new Set(res.ads.map(a => a.page_id)).size;
    console.log(`[${n}/${Math.min(jobs.length, limit)}] ${status} "${job.term}" [${job.variant}] count=${res.count} ads=${res.ads.length} pages=${pages}`);

    if (fails >= 3) {
      console.log('3 consecutive failures; cooling down 5 min');
      await L.sleep(300000);
      fails = 0;
    }
    await L.sleep(L.jitter(10000, 16000));
  }
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
