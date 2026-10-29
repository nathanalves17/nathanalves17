"""Build data/site_queue.json from audited pages: the representative destination
URL of each page's main offers (up to --per-page, default 6)."""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
from offers import build_offers  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--per-page', type=int, default=6)
    args = ap.parse_args()
    search = collections.defaultdict(list)
    for a in C.load_search_ads():
        search[a['page_id']].append(a)
    queue, seen = [], set()
    for pid, rec in C.load_pages().items():
        offers, _, _ = build_offers(rec, search)
        for o in offers[:args.per_page]:
            if o['url'] in seen:
                continue
            seen.add(o['url'])
            queue.append({'url': o['url'], 'page_id': pid, 'offer_key': o['key'], 'n_ads': o['n_ads']})
    queue.sort(key=lambda q: -q['n_ads'])
    with open(os.path.join(C.DATA, 'site_queue.json'), 'w') as f:
        json.dump(queue, f, ensure_ascii=False, indent=0)
    print(f'{len(queue)} destination URLs queued')


if __name__ == '__main__':
    main()
