import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

COUNTRIES = ('US', 'GB', 'DE', 'IL')
OUTPUT = Path('data/signals.json')

def main():
    now = datetime.now(timezone.utc).isoformat()
    try:
        data = json.loads(OUTPUT.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        data = {'observations': [], 'runs': []}
    status = {}
    existing = {(x['observed_at'][:10], x['geo'], x['term']) for x in data['observations']}
    for geo in COUNTRIES:
        try:
            request = urllib.request.Request('https://trends.google.com/trending/rss?geo=' + geo, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                root = ET.fromstring(response.read())
            items = root.findall('./channel/item')
            status[geo] = {'ok': True, 'items': len(items)}
            for item in items:
                term = (item.findtext('title') or '').strip()
                if not term or (now[:10], geo, term) in existing:
                    continue
                data['observations'].append({'observed_at': now, 'geo': geo, 'term': term, 'source_url': item.findtext('link') or 'https://trends.google.com/trending/', 'published': item.findtext('pubDate')})
                existing.add((now[:10], geo, term))
        except Exception as exc:
            status[geo] = {'ok': False, 'error': str(exc)[:180]}
    data['last_run'] = now
    data['source'] = 'Google Trends Trending Now RSS (search interest, not sales)'
    data['runs'].append({'at': now, 'status': status})
    data['runs'] = data['runs'][-100:]
    data['observations'] = data['observations'][-15000:]
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not any(v['ok'] for v in status.values()):
        raise RuntimeError('All RSS feeds failed')

if __name__ == '__main__':
    main()
