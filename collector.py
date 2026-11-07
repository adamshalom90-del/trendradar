import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

COUNTRIES = ('US', 'GB', 'DE', 'IL')
OUTPUT = Path('data/signals.json')
PRODUCTS = {
 'home_kitchen': ['air fryer','rice cooker','coffee maker','espresso machine','blender','juicer','food processor','vacuum cleaner','robot vacuum','steam mop','air purifier','dehumidifier','humidifier','water filter','water bottle','magnetic shelf','storage organizer','label maker','label printer','mini fridge','electric kettle','dish rack','silicone mold','ice maker','milk frother','מכונת קפה','סיר אורז','טיגון ללא שמן','בלנדר','מסחטה','שואב אבק','מטהר אוויר','מסנן מים','קומקום חשמלי','מדפסת מדבקות','מקציף חלב','מכונת קרח','מארגן מגירות','מכונת כביסה'],
 'pets': ['cat fountain','pet fountain','automatic feeder','pet feeder','cat litter','litter box','dog harness','dog bed','cat tree','pet camera','dog toy','cat toy','pet grooming','pet brush','dog leash','מזרקת מים לחתול','מאכיל אוטומטי','ארגז חול לחתול','רתמה לכלב','מיטת כלב','מצלמה לחיות מחמד','צעצוע לכלב','צעצוע לחתול'],
 'gadgets': ['portable monitor','wireless charger','power bank','smart plug','smart light','smart bulb','security camera','dash cam','bluetooth tracker','3d printer','thermal printer','mini projector','wireless earbuds','mechanical keyboard','gaming mouse','usb hub','charging station','portable fan','מסך נייד','מטען אלחוטי','סוללה ניידת','שקע חכם','נורה חכמה','מצלמת אבטחה','מצלמת רכב','מדפסת תלת מימד','מקרן נייד','אוזניות אלחוטיות','מקלדת מכנית','עכבר גיימינג']
}
BLOCK = ['election','president','prime minister','war','attack','killed','earthquake','stock','shares','earnings','football','soccer','nba','nfl','movie','actor','celebrity','netflix','concert','lottery','weather','news','trump','biden','iran','israel war','בחירות','מלחמה','פיגוע','רעידת אדמה','בורסה','מניות','כדורגל','כדורסל','חדשות','מזג אוויר']
def category(term):
    # Exact product name only. News headlines, people's names and games are not products.
    normalized = re.sub(r'\\s+', ' ', term.casefold().strip())
    for name, phrases in PRODUCTS.items():
        if normalized in phrases:
            return name
    return None

def main():
    now = datetime.now(timezone.utc).isoformat()
    try:
        data = json.loads(OUTPUT.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        data = {'observations': [], 'runs': []}
    data.setdefault('observations', [])
    data.setdefault('runs', [])
    # Remove old general-news observations. Keep only strict product matches.
    data['observations'] = [item for item in data['observations'] if category(item.get('term', ''))]
    for item in data['observations']:
        item['product_category'] = category(item['term'])
    existing = {(x.get('observed_at','')[:10], x.get('geo'), x.get('term')) for x in data['observations']}
    status = {}
    for geo in COUNTRIES:
        try:
            request = urllib.request.Request('https://trends.google.com/trending/rss?geo=' + geo, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                root = ET.fromstring(response.read())
            items = root.findall('./channel/item')
            accepted = 0
            for item in items:
                term = (item.findtext('title') or '').strip()
                cat = category(term)
                if not cat or (now[:10], geo, term) in existing:
                    continue
                data['observations'].append({'observed_at': now, 'geo': geo, 'term': term, 'product_category': cat, 'source_url': item.findtext('link') or 'https://trends.google.com/trending/', 'published': item.findtext('pubDate')})
                existing.add((now[:10], geo, term))
                accepted += 1
            status[geo] = {'ok': True, 'items_checked': len(items), 'product_candidates_added': accepted}
        except Exception as exc:
            status[geo] = {'ok': False, 'error': str(exc)[:180]}
    data['last_run'] = now
    data['source'] = 'Google Trends Trending Now RSS; strict product phrase filter; not sales data'
    data['runs'].append({'at': now, 'status': status})
    data['runs'] = data['runs'][-100:]
    data['observations'] = data['observations'][-15000:]
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not any(v['ok'] for v in status.values()):
        raise RuntimeError('All RSS feeds failed')

if __name__ == '__main__':
    main()
