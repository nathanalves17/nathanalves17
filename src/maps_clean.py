"""Cleans Google Maps cards collected by src/maps_leads.js into a lead list.

Rules (from the "Prompt Scrapper Maps" brief): drop cards without phone,
repeated phones, "Permanently closed", repeated Sponsored cards, categories
outside the niche and places outside the state's box; optionally keep only
businesses without a Website button. Never invents data: name and phone come
straight from the card.

Writes OUT.csv (nome, telefone, tem_site) and OUT_detalhado.csv (adds
categoria, cidade_busca, termo, sinal_brasileiro, link_maps).

usage: python3 src/maps_clean.py RAW.jsonl OUT.csv [--only-no-site] [--limit N]
"""
import csv
import json
import re
import sys
import unicodedata

NICHE_OK = re.compile(r"(house cleaning|cleaning service|commercial cleaning|janitorial|maid service|"
                      r"office cleaning|cleaners|cleaning company|move.?out cleaning|housekeeping)", re.I)
NICHE_BAD = re.compile(r"(dry clean|laundr|car wash|detailing|carpet|upholstery|pressure wash|power wash|"
                       r"window clean|gutter|chimney|duct|septic|pool|junk|restoration|supply|supplies|"
                       r"store|pest|landscap|plumb|staffing|employment)", re.I)
# Massachusetts bounding box (approximate)
LAT, LON = (41.23, 42.89), (-73.51, -69.92)

BR_WORDS = re.compile(r"\b(brazil|brasil|brazilian|brasileir|limpeza|faxina|casa|minha|sonho|"
                      r"silva|souza|sousa|santos|oliveira|costa|pereira|ferreira|rodrigues|almeida|"
                      r"lima|gomes|ribeiro|carvalho|alves|araujo|barbosa|rocha|dias|moreira|nascimento|"
                      r"freitas|cardoso|teixeira|mendes|vieira|batista|machado|campos|cunha|"
                      r"rosangela|luciana|simone|adriana|cristiane|cristina|fernanda|juliana|patricia|"
                      r"daniela|aline|camila|tatiana|vanessa|leticia|priscila|eliane|sandra|marcia|"
                      r"rosana|gisele|kelly|joyce|joice|thais|bianca|larissa|debora|claudia|lucia)\b", re.I)

PHONE = re.compile(r"(?:\+1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})")


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse(card):
    lines = [l.strip() for l in card["text"].split("\n") if l.strip()]
    category = ""
    for l in lines:
        if l.lower() == card["name"].lower():
            continue
        if "·" in l and not re.search(r"\b(Open|Closed|Opens|Closes)\b", l):
            category = l.split("·")[0].strip()
            break
        if NICHE_OK.search(l) and len(l) < 60:
            category = l
            break
    phone = None
    for l in lines:
        if l.lower().startswith(card["name"].lower()):
            continue
        m = PHONE.search(l)
        if m and re.search(r"\+1|\(\d{3}\)|\d{3}-\d{3}-\d{4}", l):
            phone = m.groups()
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", card["href"])
    lat, lon = (float(m.group(1)), float(m.group(2))) if m else (None, None)
    return {
        "category": category,
        "phone": phone,
        "lat": lat,
        "lon": lon,
        "sponsored": "Sponsored" in card["text"],
        "closed": "Permanently closed" in card["text"] or "Temporarily closed" in card["text"],
    }


def main():
    raw, out = sys.argv[1], sys.argv[2]
    only_no_site = "--only-no-site" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None

    seen_phone, seen_name, rows, drops = set(), set(), [], {}

    def drop(reason):
        drops[reason] = drops.get(reason, 0) + 1

    for line in open(raw, encoding="utf8"):
        card = json.loads(line)
        p = parse(card)
        key_name = norm(card["name"]).lower().strip()
        if p["closed"]:
            drop("fechada"); continue
        if not p["phone"]:
            drop("sem telefone"); continue
        phone = "+1 {} {} {}".format(*p["phone"])
        if phone in seen_phone or key_name in seen_name:
            drop("repetida"); continue
        cat = p["category"]
        if NICHE_BAD.search(cat) or not NICHE_OK.search(cat):
            drop("fora do nicho"); continue
        if p["lat"] is None or not (LAT[0] <= p["lat"] <= LAT[1] and LON[0] <= p["lon"] <= LON[1]):
            drop("fora do estado"); continue
        seen_phone.add(phone)
        seen_name.add(key_name)
        if only_no_site and card["website"]:
            drop("tem site"); continue
        br = BR_WORDS.search(norm(card["name"]))
        signal = ("sim" if br and re.search(r"brazil|brasil|limpeza|faxina", br.group(0), re.I)
                  else "talvez" if br or re.search(r"brazil", card["term"], re.I) else "")
        rows.append({
            "nome": card["name"],
            "telefone": phone,
            "tem_site": "sim" if card["website"] else "não",
            "categoria": cat,
            "cidade_busca": card["place"],
            "termo": card["term"],
            "sinal_brasileiro": signal,
            "link_maps": card["href"].split("?")[0],
        })

    # Brazilian-signal leads first, then the rest, keeping collection order inside each group.
    rows.sort(key=lambda r: {"sim": 0, "talvez": 1, "": 2}[r["sinal_brasileiro"]])
    total = len(rows)
    if limit:
        rows = rows[:limit]

    with open(out, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["nome", "telefone", "tem_site"], extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    with open(out.replace(".csv", "_detalhado.csv"), "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["nome"])
        w.writeheader(); w.writerows(rows)

    print(f"válidas: {total}  salvas: {len(rows)}  descartes: {drops}")


if __name__ == "__main__":
    main()
