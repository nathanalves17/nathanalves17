// WhatsApp public-name check (no login): opens wa.me/<number> for each phone
// and records the heading WhatsApp shows. A profile name means the number is
// on WhatsApp; the generic "Chat on WhatsApp with <number>" is inconclusive
// (no WhatsApp, or a profile that hides its name). Resumable.
//
// usage: NODE_PATH=$(npm root -g) node src/wa_names.js PHONES.txt OUT.jsonl
//   PHONES.txt: one phone per line, any format (+1 508 740 1520)
const fs = require('fs');
const { chromium } = require('playwright');

(async () => {
  const [inPath, out] = process.argv.slice(2);
  const done = new Set(fs.existsSync(out) ? fs.readFileSync(out, 'utf8').trim().split('\n').filter(Boolean).map(l => JSON.parse(l).digits) : []);
  const phones = [...new Set(fs.readFileSync(inPath, 'utf8').split('\n').map(l => l.replace(/\D/g, '')).filter(d => d.length >= 11))]
    .filter(d => !done.has(d));
  console.log(`${phones.length} numbers pending`);
  const b = await chromium.launch({ proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined });
  const p = await (await b.newContext({ locale: 'en-US' })).newPage();
  for (const d of phones) {
    let heading = null, error = null;
    try {
      await p.goto('https://wa.me/' + d, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForTimeout(3500);
      const t = await p.evaluate(() => document.body.innerText);
      const m = t.match(/Download\s*\n\s*(.+?)\s*\n\s*Open app/);
      heading = m ? m[1].trim() : null;
    } catch (e) { error = String(e).slice(0, 80); }
    const generic = !heading || /^Chat on WhatsApp with/i.test(heading);
    const status = error ? 'erro' : generic ? 'inconclusivo' : 'tem WhatsApp';
    fs.appendFileSync(out, JSON.stringify({ digits: d, status, nome_whatsapp: generic ? '' : heading, error }) + '\n');
    console.log(d, status, generic ? '' : heading);
    await p.waitForTimeout(4000 + Math.random() * 4000);
  }
  await b.close();
})();
