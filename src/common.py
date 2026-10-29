"""Shared loading and classification helpers for the analysis scripts."""
import glob
import json
import os
import re
import unicodedata
from urllib.parse import urlparse, urlunparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUTPUT = os.path.join(ROOT, 'output')

MESSAGING_CTAS = {
    'WHATSAPP_MESSAGE', 'SEND_WHATSAPP_MESSAGE', 'MESSAGE_PAGE', 'SEND_MESSAGE',
    'INSTAGRAM_MESSAGE', 'MESSENGER', 'CONTACT_US_MESSENGER',
}
MESSAGING_HOSTS = (
    'wa.me', 'api.whatsapp.com', 'whatsapp.com', 'chat.whatsapp.com', 'web.whatsapp.com',
    'm.me', 'messenger.com', 'ig.me',
)
SOCIAL_HOSTS = ('facebook.com', 'fb.me', 'fb.com', 'instagram.com', 'tiktok.com', 'youtube.com', 'linktr.ee')

# Phrases that state cash-on-delivery. Matched on accent-folded lowercase text.
COD_PATTERNS = [
    r'contra ?entrega', r'pag(?:o|a|as|ar|ue)s? (?:al|cuando|en el momento de) (?:recibir|recibas|reciba|llegue)',
    r'pag(?:o|a|as|ar) (?:en|desde) (?:casa|la puerta)', r'pag(?:o|a|as) en efectivo al (?:recibir|repartidor|mensajero|domiciliario|transportador)',
    r'recibe y paga', r'paga(?:s)? (?:cuando|al) (?:te )?llegue', r'pago cuando recibo', r'pagas? al momento de (?:la )?entrega',
    r'pago en la entrega', r'paga(?:s|r)? (?:hasta|solo) (?:que|cuando) (?:lo )?recib',
]
COD_RE = re.compile('|'.join(COD_PATTERNS))

COLOMBIA_RE = re.compile(r'\b(colombia|bogota|medellin|cali|barranquilla|cartagena|bucaramanga|antioquia|cundinamarca|valle del cauca|atlantico|santander)\b')


def fold(s):
    if not s:
        return ''
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()


def cod_phrases(text):
    """Return the distinct COD phrases found in text (accent-insensitive)."""
    return sorted({m.group(0) for m in COD_RE.finditer(fold(text))})


def cod_snippets(text, width=70, limit=3):
    t = text or ''
    ft = fold(t)
    out = []
    for m in COD_RE.finditer(ft):
        a, b = max(0, m.start() - width), min(len(t), m.end() + width)
        snip = re.sub(r'\s+', ' ', t[a:b]).strip()
        if snip not in out:
            out.append(snip)
        if len(out) >= limit:
            break
    return out


def host(url):
    try:
        h = urlparse(url).netloc.lower()
    except ValueError:
        return ''
    return h[4:] if h.startswith('www.') else h


def norm_url(url):
    """Product-level URL: scheme+host+path without query, fragment or trailing slash."""
    if not url:
        return None
    try:
        p = urlparse(url.strip())
    except ValueError:
        return None
    if not p.netloc:
        return None
    path = re.sub(r'/+$', '', p.path) or '/'
    # Shopify collection-scoped product URLs point at the same product.
    path = re.sub(r'^/collections/[^/]+/products/', '/products/', path)
    return urlunparse(('https', p.netloc.lower().replace('www.', '', 1), path, '', '', ''))


def ad_links(ad):
    links = [ad.get('link_url')] + [c.get('link_url') for c in ad.get('cards') or []]
    return [l for l in links if l]


def destination(ad):
    """website | messaging | social | none, judged from CTA type and the URL itself."""
    if (ad.get('cta_type') or '') in MESSAGING_CTAS:
        return 'messaging'
    links = ad_links(ad)
    if not links:
        return 'none'
    hs = [host(l) for l in links]
    if any(h.endswith(m) for h in hs for m in MESSAGING_HOSTS):
        return 'messaging'
    if all(any(h == s or h.endswith('.' + s) for s in SOCIAL_HOSTS) for h in hs):
        return 'social'
    return 'website'


def website_url(ad):
    for l in ad_links(ad):
        h = host(l)
        if not any(h.endswith(m) for m in MESSAGING_HOSTS) and not any(h == s or h.endswith('.' + s) for s in SOCIAL_HOSTS):
            return l
    return None


def ad_text(ad):
    parts = [ad.get('body'), ad.get('title'), ad.get('link_description'), ad.get('caption')]
    for c in ad.get('cards') or []:
        parts += [c.get('title'), c.get('body')]
    return '\n'.join(p for p in parts if p)


def load_search_ads():
    out = []
    for f in sorted(glob.glob(os.path.join(DATA, 'raw', 'search', '*.json'))):
        d = json.load(open(f))
        for a in d['ads']:
            a['_query'] = d['term']
            a['_variant'] = d['variant']
            out.append(a)
    return out


def load_pages():
    out = {}
    for f in glob.glob(os.path.join(DATA, 'raw', 'pages', '*.json')):
        d = json.load(open(f))
        out[d['page_id']] = d
    return out


def load_sites():
    out = {}
    for f in glob.glob(os.path.join(DATA, 'sites', 'raw', '*.json')):
        d = json.load(open(f))
        out[d['url']] = d
    return out


def lib_page_url(page_id):
    return ('https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=CO'
            '&is_targeted_country=false&media_type=all&search_type=page&sort_data%5Bdirection%5D=desc'
            f'&sort_data%5Bmode%5D=total_impressions&view_all_page_id={page_id}')


def lib_ad_url(ad_id):
    return f'https://www.facebook.com/ads/library/?id={ad_id}'
