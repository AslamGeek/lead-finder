import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import yaml
from rapidfuzz.fuzz import ratio
from .config import settings


def normalize(value):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', unicodedata.normalize('NFKC', value or '').casefold().replace('&', ' and '))).strip()


def normalize_phone(value):
    if not value:
        return None
    digits = re.sub(r'\D', '', value)
    # Never infer a country code from the search location.
    return ('+' if value.strip().startswith('+') else '') + digits if 7 <= len(digits) <= 15 else None


def normalize_url(value):
    if not value:
        return None
    try:
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', value) and not value.startswith(('https://','http://')):
            return None
        p = urlsplit(value if '://' in value else 'https://' + value)
        p.port  # validate malformed ports before returning a canonical URL
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
            return None
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/') or '/', p.query, ''))
    except ValueError:
        return None


def distance_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(a)))


class TaxonomyService:
    def __init__(self, directory=None):
        self.rules = {}
        for path in sorted(Path(directory or Path(__file__).parent / 'taxonomy').glob('*.yaml')):
            self.rules.update(yaml.safe_load(path.read_text(encoding='utf-8')).get('categories', {}))

    def expand(self, terms):
        canonical, expanded = [], []
        for term in terms:
            clean = normalize(term)
            match = next(((key, rule) for key, rule in self.rules.items() if clean in [normalize(s) for s in rule.get('synonyms', [])]), None)
            canonical.append(match[0] if match else clean)
            variants = [clean] + (match[1].get('related_queries', []) if match else [])
            for variant in variants[:settings.max_expansions_per_term]:
                variant = normalize(variant)
                if variant not in expanded and len(expanded) < settings.max_total_search_terms:
                    expanded.append(variant)
        return list(dict.fromkeys(canonical)), expanded

    def classify(self, content):
        text = normalize(content)
        results = []
        for key, rule in self.rules.items():
            signals = [{'term': term, 'weight': weight} for term, weight in rule.get('keywords', {}).items() if re.search(r'(?<!\w)' + re.escape(normalize(term)) + r'(?!\w)', text)]
            score = sum(s['weight'] for s in signals)
            if score >= rule.get('threshold', 8):
                results.append({'key': key, 'label': rule['label'], 'dimension': rule['dimension'], 'score': score, 'signals': signals})
        return results


def match_score(a, b):
    score, signals = 0, []
    def add(points, reason):
        nonlocal score
        score += points
        signals.append(reason)
    if a.get('phone') and a.get('phone') == b.get('phone'):
        add(50, 'same normalized phone')
    if a.get('website') and b.get('website') and urlsplit(a['website']).hostname == urlsplit(b['website']).hostname:
        add(45, 'same website domain')
    distance = distance_km(a.get('latitude'), a.get('longitude'), b.get('latitude'), b.get('longitude'))
    if distance is not None and distance < .1:
        add(25, 'distance below 100 meters')
    if a.get('name') and b.get('name') and ratio(normalize(a['name']), normalize(b['name'])) > 90:
        add(25, 'name similarity above 90')
    if a.get('address') and b.get('address') and ratio(normalize(a['address']), normalize(b['address'])) > 85:
        add(20, 'address similarity above 85')
    # A shared chain domain and phone must not merge geographically distinct branches.
    if distance is not None and distance > 1:
        return min(score, 69), signals + ['branch distance guard']
    return score, signals


COMPLETENESS_WEIGHTS = {'website': 10, 'phone': 15, 'email': 10, 'address': 10, 'coordinates': 10, 'category': 10, 'services': 10, 'multiple_sources': 10, 'recent_verification': 15}


def completeness(entity, weights=None):
    weights = weights or COMPLETENESS_WEIGHTS
    known = dict(entity)
    known['coordinates'] = entity.get('latitude') is not None and entity.get('longitude') is not None
    known['multiple_sources'] = entity.get('source_count', 0) > 1
    stamp=entity.get('last_verified_at')
    try:
        if isinstance(stamp,str): stamp=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if stamp and stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)
        known['recent_verification']=bool(stamp and 0 <= (datetime.now(timezone.utc)-stamp).days <= 90)
    except (ValueError,TypeError): known['recent_verification']=False
    return round(100 * sum(weight for key, weight in weights.items() if known.get(key)) / sum(weights.values()))


def confidence_band(score):
    return 'High' if score >= .85 else 'Medium' if score >= .6 else 'Low'
