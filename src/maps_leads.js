// Google Maps lead collector (public listing data only; no login, no forms).
// Opens https://www.google.com/maps/search/TERM+in+PLACE?hl=en for each
// (term, place) pair, scrolls the result feed until it stops growing and
// saves every card's text, place link and whether the card shows a Website
// button.
//
// usage: NODE_PATH=$(npm root -g) node src/maps_leads.js OUT.jsonl "term|place" ["term|place" ...]
const fs = require('fs');
const { chromium } = require('playwright');

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function readFeed(page) {
  return page.evaluate(() => {
    const feed = document.querySelector('div[role=feed]');
    if (!feed) return null;
    const items = [];
    for (const child of feed.children) {
      const a = child.querySelector('a[href*="/maps/place/"]');
      if (!a) continue;
      const website = !!child.querySelector('a[data-value="Website"], a[aria-label*="Website" i]');
      items.push({ name: a.getAttribute('aria-label') || '', href: a.href, text: child.innerText, website });
    }
    return items;
  });
}

async function scrollFeed(page) {
  let last = -1, still = 0;
  for (let i = 0; i < 40; i++) {
    const n = await page.evaluate(() => {
      const feed = document.querySelector('div[role=feed]');
      if (!feed) return -1;
      feed.lastElementChild && feed.lastElementChild.scrollIntoView();
      feed.dispatchEvent(new WheelEvent('wheel', { deltaY: 800, bubbles: true }));
      return feed.querySelectorAll('a[href*="/maps/place/"]').length;
    });
    const end = await page.evaluate(() => /You've reached the end of the list/i.test(document.body.innerText));
    if (n === last) still++; else still = 0;
    last = n;
    if (end || still >= 3 || n < 0) break;
    await sleep(2000);
  }
}

async function main() {
  const [out, ...jobs] = process.argv.slice(2);
  const browser = await chromium.launch({ proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined });
  const ctx = await browser.newContext({ locale: 'en-US', viewport: { width: 1400, height: 1000 } });
  const page = await ctx.newPage();
  for (const job of jobs) {
    const [term, place] = job.split('|');
    const url = `https://www.google.com/maps/search/${encodeURIComponent(`${term} in ${place}`).replace(/%20/g, '+')}?hl=en`;
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForSelector('div[role=feed]', { timeout: 20000 }).catch(() => {});
      await scrollFeed(page);
      const items = (await readFeed(page)) || [];
      for (const it of items) fs.appendFileSync(out, JSON.stringify({ term, place, ...it }) + '\n');
      console.log(`${String(items.length).padStart(4)} cards  ${term} | ${place}`);
    } catch (e) {
      console.log(`FAIL ${term} | ${place}: ${String(e).slice(0, 120)}`);
    }
    await sleep(3000 + Math.random() * 3000);
  }
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
