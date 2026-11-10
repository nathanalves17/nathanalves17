// Fonte: Creative Center do TikTok (Top Ads), navegando como usuário. Saída: topads_<país>.json.
// Navega no Creative Center como um usuário (troca ordenação, período e objetivo pelos controles da
// página e rola para carregar mais) e guarda o que a própria página carrega.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [region, out] = process.argv.slice(2);
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'es-CO', viewport: { width: 1400, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36' });
  const p = await ctx.newPage();
  const all = {}; let tag = 'inicial';
  p.on('response', async r => {
    if (!/top_ads\/v2\/list/.test(r.url())) return;
    try { const d = JSON.parse(await r.text()); for (const m of d.data?.materials || []) { if (!all[m.id]) all[m.id] = { ...m, seen: [] }; if (!all[m.id].seen.includes(tag)) all[m.id].seen.push(tag); } } catch (e) {}
  });
  const scrollAll = async () => { for (let i = 0; i < 12; i++) { await p.mouse.wheel(0, 3000); await p.waitForTimeout(1500); const more = await p.getByText(/View more|See more|Load more/i).first(); if (await more.isVisible().catch(() => false)) { await more.click().catch(() => {}); await p.waitForTimeout(2000); } } };
  const pick = async (control, option) => {
    const c = p.getByText(control, { exact: true }).first();
    if (!(await c.isVisible().catch(() => false))) { console.log('controle não achado:', control); return false; }
    await c.click(); await p.waitForTimeout(800);
    const o = p.getByText(option, { exact: true }).last();
    if (!(await o.isVisible().catch(() => false))) { console.log('opção não achada:', option); await p.keyboard.press('Escape'); return false; }
    await o.click(); await p.waitForTimeout(3500); return true;
  };
  for (const period of ['Last 30 days', 'Last 180 days']) {
    await p.goto(`https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en?region=${region}&period=${period.includes('180') ? 180 : 30}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await p.waitForTimeout(6000);
    // fecha o aviso de cadastro que cobre a página
    for (let k = 0; k < 3; k++) { await p.keyboard.press('Escape'); await p.waitForTimeout(500); const x = p.locator('.byted-modal-close, [class*=modal] [class*=close], [aria-label=Close]').first(); if (await x.isVisible().catch(() => false)) { await x.click().catch(() => {}); await p.waitForTimeout(800); } }
    for (const sort of ['For You', 'CTR', 'Reach']) {
      tag = `${period}/${sort}`;
      if (sort !== 'For You') { const s = p.getByText(sort, { exact: true }).first(); if (await s.isVisible().catch(() => false)) { await s.click({ timeout: 5000 }).catch(e => console.log('clique', sort, e.message.slice(0, 60))); await p.waitForTimeout(3500); } }
      await scrollAll();
      console.log(tag, '-> acumulado', Object.keys(all).length);
    }
    tag = `${period}/Conversions`;
    const okObj = await pick('Objective', 'Conversions').catch(() => false);
    if (okObj) { await scrollAll(); console.log(tag, '-> acumulado', Object.keys(all).length); }
  }
  await p.screenshot({ path: `${out}/ui_final.png` });
  fs.writeFileSync(`${out}/topads_${region}.json`, JSON.stringify(Object.values(all)));
  console.log('total único', Object.keys(all).length);
  await b.close();
})();
