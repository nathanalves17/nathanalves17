"""Group an audited page's ads into offers (one offer = one product destination)."""
import collections
import re
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import common as C

TRACKING = re.compile(r'^(utm_|fbclid|gclid|ttclid|campaign|adset|ad_id|ad_name|placement|site_source|h_ad_id|_pos|_sid|_ss|variant$)', re.I)


def clean_url(url):
    """Drop tracking parameters but keep anything that may select the product."""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k) and '{{' not in v]
    return urlunparse((p.scheme or 'https', p.netloc, p.path, '', urlencode(q), ''))


def offer_key(url):
    n = C.norm_url(url)
    if not n:
        return None
    # Shopify duplicates products as handle-1, handle-2 ...
    return re.sub(r'(/products/[^/]+?)-\d{1,2}$', r'\1', n)


def page_ads(page_rec, search_ads_by_page):
    """All distinct ads seen for a page, tagged with the slices they appeared in."""
    seen = {}
    for slice_name in ('all', '30d', '90d'):
        sl = page_rec['slices'].get(slice_name)
        if not sl:
            continue
        for rank, a in enumerate(sl['ads']):
            cur = seen.setdefault(a['ad_archive_id'], dict(a, _slices={}, _queries=set()))
            cur['_slices'][slice_name] = rank
    for a in search_ads_by_page.get(page_rec['page_id'], []):
        cur = seen.setdefault(a['ad_archive_id'], dict(a, _slices={}, _queries=set()))
        cur['_queries'].add(a['_query'])
    return list(seen.values())


def build_offers(page_rec, search_ads_by_page, today=None):
    today = today or date.today()
    ads = page_ads(page_rec, search_ads_by_page)
    dest_counts = collections.Counter(C.destination(a) for a in ads)
    groups = collections.defaultdict(list)
    for a in ads:
        if C.destination(a) != 'website':
            continue
        u = C.website_url(a)
        k = offer_key(u)
        if k:
            groups[k].append(a)

    offers = []
    for key, gads in groups.items():
        starts = sorted(a['start_date'] for a in gads if a.get('start_date'))
        oldest = starts[0] if starts else None
        newest = starts[-1] if starts else None
        media = set()
        for a in gads:
            media.update(a.get('media_keys') or [])
        bodies = {re.sub(r'\W+', ' ', C.fold(a.get('body') or ''))[:160] for a in gads if a.get('body')}
        # The Library groups identical ads ("N anuncios usan este contenido"):
        # collation_count sits on the group's first member and a few other
        # members may be listed too, so count each group once.
        groups_ = collections.defaultdict(list)
        for a in gads:
            groups_[a.get('collation_id') or a['ad_archive_id']].append(a)
        group_sizes = [max(len(m), max((x.get('collation_count') or 1) for x in m)) for m in groups_.values()]
        represented = sum(group_sizes)
        by_rank = sorted(gads, key=lambda a: (a['_slices'].get('all', 999), a['_slices'].get('30d', 999)))
        urls = collections.Counter(clean_url(C.website_url(a)) for a in gads)
        age = (today - date.fromisoformat(oldest)).days if oldest else 0
        recent = sum(1 for s in starts if (today - date.fromisoformat(s)).days < 30)
        older = sum(1 for s in starts if (today - date.fromisoformat(s)).days >= 30)
        ad_cod = sorted({p for a in gads for p in C.cod_phrases(C.ad_text(a))})
        offers.append({
            'key': key,
            'page_id': page_rec['page_id'],
            'url': urls.most_common(1)[0][0],
            'urls': [u for u, _ in urls.most_common()],
            'ads': gads,
            'n_ads': len(gads),
            'represented_ads': represented,
            'ad_groups': len(group_sizes),
            'max_duplicates': max(group_sizes),
            'distinct_creatives': len(media) or len(gads),
            'distinct_copies': len(bodies),
            'oldest_start': oldest,
            'newest_start': newest,
            'age_days': age,
            'recent_ads': recent,
            'older_ads': older,
            'in_30d_slice': sum(1 for a in gads if '30d' in a['_slices']),
            'in_90d_slice': sum(1 for a in gads if '90d' in a['_slices']),
            'top_ad': by_rank[0]['ad_archive_id'],
            'oldest_ad': min(gads, key=lambda a: a.get('start_date') or '9999')['ad_archive_id'],
            'ad_cod_phrases': ad_cod,
            'formats': sorted({a.get('display_format') for a in gads if a.get('display_format')}),
        })
    offers.sort(key=lambda o: (-o['represented_ads'], -o['age_days']))
    return offers, dest_counts, ads
