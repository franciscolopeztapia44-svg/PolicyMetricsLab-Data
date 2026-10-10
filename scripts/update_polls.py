"""Validate curated survey observations and publish the clean dataset.
Discover news candidates automatically for later source verification.
Never turn article snippets into survey observations automatically.
"""
import csv, json, pathlib, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'brasil-2026/polls/source.csv'
OUT = ROOT / 'brasil-2026/polls/latest.csv'
DISC = ROOT / 'brasil-2026/polls/discovery.json'
FIELDS = ['fecha_fin','instituto','candidato','porcentaje','fuente_url','universo','muestra','metodologia','base','fecha_inicio','registro_tse','margen_error']
with SRC.open(encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f)
    if not set(FIELDS).issubset(reader.fieldnames or []): raise ValueError('Missing fields')
    rows=list(reader)
seen=set(); pairs={}
for r in rows:
    start,end=date.fromisoformat(r['fecha_inicio']),date.fromisoformat(r['fecha_fin'])
    assert start<=end and end>=date(2026,10,5)
    assert r['base']=='votos_validos' and r['candidato'] in ('Lula','Flavio Bolsonaro')
    assert 0<=float(r['porcentaje'])<=100 and int(r['muestra'])>0
    assert re.fullmatch(r'BR-\d+/2026',r['registro_tse'])
    assert urllib.parse.urlparse(r['fuente_url']).scheme=='https'
    assert r['instituto'].strip() and r['metodologia'].strip() and r['universo'].strip()
    key=(r['instituto'],r['fecha_fin'],r['registro_tse'],r['candidato'])
    if key in seen: raise ValueError(f'Duplicate {key}')
    seen.add(key)
    pairs.setdefault(key[:3],{})[r['candidato']]=float(r['porcentaje'])
for k,v in pairs.items():
    if set(v)!= {'Lula','Flavio Bolsonaro'} or abs(sum(v.values())-100)>2:
        raise ValueError(f'Incomplete/inconsistent pair {k}: {v}')
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
# News discovery is deliberately a review queue, not a source of numeric observations.
query=urllib.parse.quote('pesquisa segundo turno Lula Flávio Bolsonaro Datafolha Quaest Atlas PoderData')
url=f'https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419'
items=[]
try:
    req=urllib.request.Request(url,headers={'User-Agent':'PolicyMetricsLab/1.0'})
    with urllib.request.urlopen(req,timeout=20) as response:
        xml=ET.fromstring(response.read())
    for item in xml.findall('.//item')[:30]:
        items.append({'title':item.findtext('title',''), 'url':item.findtext('link',''), 'published':item.findtext('pubDate','')})
except Exception as exc:
    print('Discovery unavailable; keeping validated CSV:',exc)
DISC.write_text(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),'candidates_unverified':items},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Validated {len(rows)//2} surveys; {len(items)} discovery candidates (NOT automatically published).')
