// Busca por copy: pesquisa a frase principal do anúncio (texto acima do vídeo)
// como frase exata na Biblioteca (CO, todos os anúncios, ativos, ordenado por
// impressões) para ver quantos anúncios e quais outras páginas usam a mesma copy.
// Entrada: data/copy_queue.json [{id, page_id, page_name, product, copy}]
// Saída: data/raw/copy/<id>.json. Retomável.
//
// usage: node src/copy_search.js [--limit N]
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1]]);
  return acc;
}, []));

const OUT = path.join(L.DATA, 'raw', 'copy');
fs.mkdirSync(OUT, { recursive: true });

async function main() {
  const queue = JSON.parse(fs.readFileSync(path.join(L.DATA, 'copy_queue.json'), 'utf8'));
  const limit = args.limit ? Number(args.limit) : Infinity;
  const pending = queue.filter(q => !fs.existsSync(path.join(OUT, `${q.id}.json`))).slice(0, limit);
  console.log(`${pending.length} copies pending of ${queue.length}`);
  const browser = await L.newBrowser();
  const ctx = await L.newContext(browser);
  let n = 0;
  for (const q of pending) {
    n++;
    const url = L.keywordUrl(q.copy);
    let res;
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        res = await L.fetchLibrary(ctx, url, { type: 'copy', id: q.id });
      } catch (e) {
        res = { ok: false, error: String(e).slice(0, 200), ads: [] };
      }
      // The copy comes from a live ad, so zero results means the soft limit.
      if (res.ok && res.count > 0) break;
      if (attempt === 2) break;
      console.log(`  backoff (ok=${res.ok} count=${res.count}${res.error ? ' ' + res.error : ''})`);
      await L.sleep(L.jitter(60000, 90000));
    }
    const pages = new Set(res.ads.map(a => a.page_id));
    fs.writeFileSync(path.join(OUT, `${q.id}.json`), JSON.stringify({ ...q, url, fetched_at: L.nowIso(), ok: res.ok, count: res.count, ads: res.ads }));
    console.log(`[${n}/${pending.length}] ${q.page_name} | ${q.product} | count=${res.count} pages=${pages.size}`);
    await L.sleep(L.jitter(10000, 16000));
  }
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
