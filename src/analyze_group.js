// Análise de ofertas indicadas (ex.: exportação de grupo do WhatsApp).
// Para cada oferta de data/group_offers.json [{id, product, product_url, library_url, country}]:
//   1. abre o link da Biblioteca indicado (busca pelo domínio da loja);
//   2. escolhe as páginas que mais anunciam o domínio e audita cada uma no
//      mesmo país (todos os ativos, iniciados há 30+ dias e 90+ dias);
//   3. pesquisa a copy principal dos anúncios do produto como frase exata.
// Saída: data/raw/group/<id>.json (retomável por etapa).
//
// usage: node src/analyze_group.js [--only id1,id2]
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1]]);
  return acc;
}, []));

const OUT = path.join(L.DATA, 'raw', 'group');
fs.mkdirSync(OUT, { recursive: true });

function host(u) {
  try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; }
}

function firstLine(body) {
  const line = (body || '').split('\n').map(l => l.trim()).find(l => (l.match(/[\p{L}\p{N}]/gu) || []).length >= 12) || '';
  if (line.includes('{{')) return '';
  // Exact-phrase search works best on a clean run of words.
  const clean = line.replace(/[^\p{L}\p{N}\s¿?¡!.,]/gu, ' ').replace(/\s+/g, ' ').trim();
  return clean.split(' ').slice(0, 10).join(' ').replace(/[.,]+$/, '');
}

async function load(ctx, url, source, expectNonZero) {
  let res;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      res = await L.fetchLibrary(ctx, url, source);
    } catch (e) {
      res = { ok: false, error: String(e).slice(0, 200), ads: [] };
    }
    if (res.ok && !res.captcha && (res.count > 0 || !expectNonZero)) break;
    if (attempt === 2) break;
    console.log(`  backoff (ok=${res.ok} count=${res.count}${res.error ? ' ' + res.error : ''})`);
    await L.sleep(L.jitter(60000, 90000));
  }
  await L.sleep(L.jitter(10000, 16000));
  return res;
}

async function main() {
  const offers = JSON.parse(fs.readFileSync(path.join(L.DATA, 'group_offers.json'), 'utf8'));
  const only = args.only ? args.only.split(',') : null;
  const browser = await L.newBrowser();
  const ctx = await L.newContext(browser);
  for (const o of offers) {
    if (only && !only.includes(o.id)) continue;
    const file = path.join(OUT, `${o.id}.json`);
    const rec = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : { ...o, pages: {} };
    const save = () => fs.writeFileSync(file, JSON.stringify(rec));
    const domain = host(o.product_url);

    if (!rec.domain_search || !rec.domain_search.ads.length) {
      const r = await load(ctx, o.library_url, { type: 'group_domain', id: o.id }, true);
      rec.domain_search = { url: o.library_url, ok: r.ok, count: r.count, ads: r.ads, fetched_at: L.nowIso() };
      save();
      console.log(`${o.id}: busca do domínio count=${r.count} ads=${r.ads.length}`);
    }

    const byPage = {};
    for (const a of rec.domain_search.ads) {
      const links = [a.link_url, ...(a.cards || []).map(c => c.link_url)].filter(Boolean);
      const hit = links.some(l => host(l) === domain) || (a.caption || '').toLowerCase().includes(domain);
      const p = byPage[a.page_id] = byPage[a.page_id] || { page_id: a.page_id, page_name: a.page_name, ads: 0, domain_ads: 0 };
      p.ads++;
      if (hit) p.domain_ads++;
    }
    const mainPages = Object.values(byPage).sort((a, b) => b.domain_ads - a.domain_ads || b.ads - a.ads)
      .filter((p, i) => i === 0 || p.domain_ads >= 3).slice(0, 3);
    rec.main_pages = mainPages;

    for (const p of mainPages) {
      if (rec.pages[p.page_id] && rec.pages[p.page_id].slices.all.ads.length) continue;
      const d30 = L.daysAgo(30), d90 = L.daysAgo(90);
      const sAll = await load(ctx, L.pageUrl(p.page_id, null, o.country), { type: 'page', slice: 'all' }, true);
      const s30 = await load(ctx, L.pageUrl(p.page_id, d30, o.country), { type: 'page', slice: '30d' },
        sAll.ads.some(a => a.start_date && a.start_date <= d30));
      const pr = { page_id: p.page_id, page_name: p.page_name, url: L.pageUrl(p.page_id, null, o.country), audited_at: L.nowIso(), slices: {
        all: { ok: sAll.ok, count: sAll.count, ads: sAll.ads },
        '30d': { ok: s30.ok, count: s30.count, max_start: d30, ads: s30.ads },
      } };
      if (s30.ok && s30.count >= 10) {
        const s90 = await load(ctx, L.pageUrl(p.page_id, d90, o.country), { type: 'page', slice: '90d' },
          s30.ads.some(a => a.start_date && a.start_date <= d90));
        pr.slices['90d'] = { ok: s90.ok, count: s90.count, max_start: d90, ads: s90.ads };
      }
      rec.pages[p.page_id] = pr;
      save();
      console.log(`${o.id}: página ${p.page_name} total=${sAll.count} 30d+=${s30.count} 90d+=${pr.slices['90d'] ? pr.slices['90d'].count : '-'}`);
    }

    if (!rec.copy_search || !rec.copy_search.ads.length) {
      const pool = [...rec.domain_search.ads, ...Object.values(rec.pages).flatMap(p => Object.values(p.slices).flatMap(s => s.ads))];
      const counts = {};
      for (const a of pool) {
        const links = [a.link_url, ...(a.cards || []).map(c => c.link_url)].filter(Boolean);
        if (!links.some(l => host(l) === domain)) continue;
        const fl = firstLine(a.body);
        if (fl.split(' ').length >= 4) counts[fl] = (counts[fl] || 0) + Math.max(1, a.collation_count || 1);
      }
      const copy = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
      if (copy) {
        const url = L.keywordUrl(copy[0], null, o.country);
        const r = await load(ctx, url, { type: 'group_copy', id: o.id }, true);
        rec.copy_search = { copy: copy[0], url, ok: r.ok, count: r.count, ads: r.ads, fetched_at: L.nowIso() };
        save();
        console.log(`${o.id}: copy "${copy[0]}" count=${r.count} pages=${new Set(r.ads.map(a => a.page_id)).size}`);
      }
    }
  }
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
