"""Separates Brazilian-owned leads from the rest using public signals only.

Signals, strongest first:
  forte   - business name has brazil/brasil or a Portuguese word (limpeza, faxina...),
            or the WhatsApp profile name has one
  nome_br - WhatsApp profile name or business name carries a typically Brazilian
            first name (Elianice, Regiane, Rosangela, Grazy...) or a Portuguese-only
            surname spelling (Souza, Gonçalves, Nascimento, Freitas...)
  lusofono- only a surname shared by Portuguese/Cape Verdean and Hispanic families
            (Silva, Santos, Costa, Lima): probable, not certain
Leads with no signal are left out.

usage: python3 src/br_classify.py WA_NAMES.jsonl OUT.csv DETAILED.csv [DETAILED2.csv ...]
"""
import csv
import json
import re
import sys
import unicodedata


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


STRONG = re.compile(r"\b(brazil\w*|brasil\w*|limpeza|faxina|faxineira|diarista|casa limpa|brilho|cheirinho|"
                    r"servicos|capricho|caprichosa|deus|jesus|abencoad\w*|benca|fe em deus)\b")
BR_FIRST = re.compile(r"\b(elianice|regiane|rosana|rosangela|rosimeire|rosemeire|roseli|rosilene|luciana|luciene|"
                      r"lucimara|lucimar|lucilene|marli|marlene|simone|silvana|solange|sueli|suely|tatiane|thais|"
                      r"viviane|adriana|adriane|aline|alessandra|andreia|aparecida|bruna|cintia|cristiane|daiane|"
                      r"edileuza|eliane|elisangela|elizangela|fabiana|fabiola|flavia|gisele|giselle|graziela|grazi|"
                      r"grazy|gleice|gleyce|ivone|ivonete|jaqueline|janaina|joice|josiane|jucilene|juliana|jussara|"
                      r"katia|keila|kely|kelly|larissa|leticia|lidiane|luana|luzia|maiara|mayara|marilene|marinalva|"
                      r"michele|neide|poliana|priscila|renata|samara|sheila|sirlene|valdirene|zilda|betania|rayane|"
                      r"raiane|jessica|gaby|gabi|leidiane|daniele|denise|eunice|geane|jane|joelma|kenia|lucia|"
                      r"marcia|marta|meire|nilza|rose|rosa|tais|vania|vanusa|wanessa|wellington|weslley|"
                      r"wesley|edson|edvaldo|claudinei|valdir|jair|joao|marcos|thiago|tiago|rodrigo|leandro|"
                      r"cris|kaka|nana|fafa|lu|dani|duda|bia)\b")
PT_SURNAME = re.compile(r"\b(souza|sousa|goncalves|conceicao|nascimento|araujo|oliveira|pereira|ferreira|rodrigues|"
                        r"carvalho|ribeiro|freitas|moreira|teixeira|cardoso|barbosa|azevedo|magalhaes|medeiros|"
                        r"monteiro|siqueira|vieira|coelho|cunha|machado|pinheiro|rezende|resende|cavalcante|assis|"
                        r"alves|dias|lopes|gomes|mendes|fernandes|martins|nunes|rocha|barros|moura|lourenco|"
                        r"amora|batista|santana|aguiar|braga|camargo|paiva|prado|queiroz|reis|sales|xavier)\b")
SHARED_SURNAME = re.compile(r"\b(silva|santos|costa|lima|campos|castro|pinto|cruz|andrade)\b")


def classify(name, wa_name):
    n, w = norm(name), norm(wa_name)
    ev = []
    if STRONG.search(n):
        ev.append(f"nome da empresa: '{STRONG.search(n).group(0)}'")
    if w and STRONG.search(w):
        ev.append(f"WhatsApp: '{STRONG.search(w).group(0)}'")
    if ev:
        return "forte", ev
    for label, text in (("WhatsApp", w), ("nome da empresa", n)):
        for pat in (BR_FIRST, PT_SURNAME):
            m = pat.search(text) if text else None
            if m:
                ev.append(f"{label}: '{m.group(0)}'")
    if ev:
        return "nome_br", ev
    for label, text in (("WhatsApp", w), ("nome da empresa", n)):
        m = SHARED_SURNAME.search(text) if text else None
        if m:
            ev.append(f"{label}: '{m.group(0)}'")
    if ev:
        return "lusofono", ev
    return "", []


def main():
    wa_path, out, *detailed = sys.argv[1:]
    wa = {}
    for line in open(wa_path, encoding="utf8"):
        r = json.loads(line)
        wa[r["digits"]] = r
    seen, rows = set(), []
    for path in detailed:
        for r in csv.DictReader(open(path, encoding="utf8")):
            digits = re.sub(r"\D", "", r["telefone"])
            if digits in seen:
                continue
            seen.add(digits)
            w = wa.get(digits, {})
            level, ev = classify(r["nome"], w.get("nome_whatsapp", ""))
            if not level:
                continue
            rows.append({
                "nome": r["nome"].split("|")[0].strip(),
                "telefone": r["telefone"],
                "tem_site": r["tem_site"],
                "whatsapp": {"tem WhatsApp": "sim"}.get(w.get("status"), "não confirmado"),
                "nome_whatsapp": w.get("nome_whatsapp", ""),
                "nivel_br": level,
                "evidencia": "; ".join(ev),
                "cidade_busca": r["cidade_busca"],
                "link_maps": r["link_maps"],
            })
    order = {"forte": 0, "nome_br": 1, "lusofono": 2}
    rows.sort(key=lambda r: (order[r["nivel_br"]], r["whatsapp"] != "sim"))
    with open(out, "w", newline="", encoding="utf8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    from collections import Counter
    print(len(seen), "leads lidos;", len(rows), "com sinal brasileiro:", dict(Counter(r["nivel_br"] for r in rows)))


if __name__ == "__main__":
    main()
