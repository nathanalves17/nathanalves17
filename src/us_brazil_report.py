"""Counts which US cities and states Brazilian advertisers mention.

Reads data/eua/scan_ads.jsonl (from src/us_brazil_scan.js) and counts unique
advertiser pages per city/state mentioned in ad text or page name. Writes
data/eua/cidades_anunciantes.csv and prints the ranking.

usage: python3 src/us_brazil_report.py
"""
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADS = ROOT / "data" / "eua" / "scan_ads.jsonl"
OUT = ROOT / "data" / "eua" / "cidades_anunciantes.csv"

# city label -> (state, regex alternatives on normalized lowercase text)
CITIES = {
    "Orlando": ("FL", r"orlando"),
    "Kissimmee": ("FL", r"kissimm?ee"),
    "Windermere/Horizon West": ("FL", r"windermere|horizon west|winter garden"),
    "Pompano Beach": ("FL", r"pompano"),
    "Deerfield Beach": ("FL", r"deerfield"),
    "Boca Raton": ("FL", r"boca raton|\bboca\b"),
    "Coconut Creek": ("FL", r"coconut creek"),
    "Fort Lauderdale": ("FL", r"fort lauderdale|ft\.? lauderdale|lauderdale"),
    "Miami": ("FL", r"\bmiami\b"),
    "Tampa": ("FL", r"\btampa\b"),
    "Jacksonville": ("FL", r"jacksonville"),
    "Naples/Fort Myers": ("FL", r"\bnaples\b|fort myers"),
    "Port St. Lucie": ("FL", r"port st\.? lucie|port saint lucie"),
    "Palm Beach": ("FL", r"palm beach"),
    "Boston": ("MA", r"\bboston\b"),
    "Framingham": ("MA", r"framingham"),
    "Marlborough": ("MA", r"marlboro"),
    "Milford (MA)": ("MA", r"\bmilford\b"),
    "Hudson (MA)": ("MA", r"\bhudson\b"),
    "Everett": ("MA", r"\beverett\b"),
    "Somerville": ("MA", r"somerville"),
    "Revere/Malden": ("MA", r"\brevere\b|\bmalden\b"),
    "Worcester": ("MA", r"worcester"),
    "Lowell": ("MA", r"\blowell\b"),
    "Cape Cod/Hyannis": ("MA", r"cape cod|hyannis|barnstable"),
    "Martha's Vineyard": ("MA", r"vineyard"),
    "Newark": ("NJ", r"\bnewark\b|ironbound"),
    "Long Branch": ("NJ", r"long branch"),
    "Danbury": ("CT", r"danbury"),
    "Bridgeport": ("CT", r"bridgeport"),
    "New York": ("NY", r"new york|nova york|\bnyc\b|queens|astoria"),
    "Philadelphia": ("PA", r"philadelphia|filadelfia"),
    "Atlanta": ("GA", r"atlanta"),
    "Marietta": ("GA", r"marietta"),
    "Charlotte": ("NC", r"charlotte"),
    "Houston": ("TX", r"houston"),
    "Dallas": ("TX", r"\bdallas\b"),
    "Austin": ("TX", r"\baustin\b"),
    "Los Angeles": ("CA", r"los angeles"),
    "San Diego": ("CA", r"san diego"),
    "Las Vegas": ("NV", r"las vegas"),
    "Salt Lake/Utah": ("UT", r"salt lake|\butah\b"),
}

STATES = {
    "FL": r"florida|\bfl\b",
    "MA": r"massachusetts|\bma\b(?=[\s,.!])",
    "NJ": r"new jersey|nova jersey|\bnj\b",
    "CT": r"connecticut|\bct\b(?=[\s,.!])",
    "NY": r"new york|nova york|\bny\b",
    "GA": r"georgia|georgia",
    "TX": r"texas|\btx\b",
    "CA": r"california|\bca\b(?=[\s,.!])",
    "NC": r"north carolina|carolina do norte",
    "PA": r"pennsylvania|pensilvania",
    "UT": r"\butah\b",
}


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def ad_text(ad):
    parts = [ad.get("page_name"), ad.get("title"), ad.get("body"), ad.get("link_description"), ad.get("caption")]
    for c in ad.get("cards") or []:
        parts += [c.get("title"), c.get("body")]
    return norm(" ".join(p for p in parts if p))


def main():
    pages = {}
    city_pages = defaultdict(set)
    state_pages = defaultdict(set)
    for line in ADS.read_text(encoding="utf8").splitlines():
        ad = json.loads(line)
        pid = str(ad.get("page_id"))
        text = ad_text(ad)
        pages.setdefault(pid, {"name": ad.get("page_name"), "terms": set()})["terms"].add(ad["term"])
        for city, (_, pat) in CITIES.items():
            if re.search(pat, text):
                city_pages[city].add(pid)
        for st, pat in STATES.items():
            if re.search(pat, text):
                state_pages[st].add(pid)
        for city, (st, pat) in CITIES.items():
            if re.search(pat, text):
                state_pages[st].add(pid)

    rows = sorted(((c, CITIES[c][0], len(p), "; ".join(sorted(pages[x]["name"] or x for x in p)[:8]))
                   for c, p in city_pages.items()), key=lambda r: -r[2])
    with OUT.open("w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["cidade", "estado", "anunciantes", "exemplos"])
        w.writerows(rows)

    print(f"{len(pages)} anunciantes únicos")
    print("\nCidades (anunciantes únicos que citam a cidade):")
    for c, st, n, ex in rows:
        print(f"  {n:4d}  {c} ({st})  — {ex[:110]}")
    print("\nEstados (cidade ou estado citado):")
    for st, p in sorted(state_pages.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(p):4d}  {st}")


if __name__ == "__main__":
    main()
