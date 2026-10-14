#!/usr/bin/env python3
"""Public project discovery and a human-reviewed opportunity research queue."""
import argparse
import csv
import html
import json
import re
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, quote
from urllib.request import Request, urlopen

DEX = 'https://api.dexscreener.com'
GECKO = 'https://api.geckoterminal.com/api/v2'
NETWORKS = {'eth': 'ethereum', 'polygon_pos': 'polygon', 'avax': 'avalanche'}


def key(chain, address):
    return chain + ':' + (address.lower() if address.startswith('0x') else address)


def safe_url(value):
    try:
        u = urlsplit(value or '')
        return value if u.scheme in ('https', 'http') and u.hostname and not u.username else ''
    except ValueError:
        return ''


def contacts(links):
    """Accept profile/channel URLs, never interpret a viral post as team ownership."""
    result = set()
    for link in links:
        url = safe_url(link.get('url', ''))
        if not url:
            continue
        u = urlsplit(url)
        host = u.hostname.lower().removeprefix('www.')
        parts = u.path.strip('/').split('/')
        if len(parts) != 1 or not parts[0]:
            continue
        handle = parts[0]
        if host in ('x.com', 'twitter.com'):
            if re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle) and handle.lower() not in ('i', 'home', 'search', 'intent', 'explore', 'share', 'settings'):
                result.add('https://x.com/' + handle)
        elif host == 't.me' and re.fullmatch(r'[A-Za-z0-9_]{5,}', handle) and handle.lower() not in ('share', 'joinchat'):
            result.add('https://t.me/' + handle)
        elif host == 'instagram.com' and re.fullmatch(r'[A-Za-z0-9_.]{1,30}', handle) and handle.lower() not in ('p', 'reel', 'reels', 'explore', 'stories', 'accounts'):
            result.add('https://instagram.com/' + handle)
    return sorted(result)


class Client:
    def __init__(self, raw):
        self.raw = raw
        raw.mkdir(parents=True, exist_ok=True)
        self.last = {}
        self.errors = []
        self.count = 0

    def get(self, url):
        host = urlsplit(url).hostname
        interval = 6.2 if 'geckoterminal' in host else 1.1
        for attempt in range(3):
            time.sleep(max(0, interval - (time.monotonic() - self.last.get(host, 0))))
            self.last[host] = time.monotonic()
            try:
                req = Request(url, headers={'User-Agent': 'Web3Hunt/0.1', 'Accept': 'application/json'})
                with urlopen(req, timeout=25) as response:
                    data = json.load(response)
                self.count += 1
                (self.raw / f'{self.count:04d}.json').write_text(json.dumps({'url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'data': data}, ensure_ascii=False))
                return data
            except HTTPError as exc:
                if exc.code == 429 or exc.code >= 500:
                    time.sleep(2 ** attempt)
                    continue
                self.errors.append(f'{url}: HTTP {exc.code}')
                return None
            except (URLError, TimeoutError, ValueError, OSError) as exc:
                self.errors.append(f'{url}: {type(exc).__name__}')
                return None
        self.errors.append(f'{url}: retry limit reached')
        return None


def discover(client, pages, seed_file=None):
    seeds = {}

    def add(chain, address, source, description='', links=None):
        if not chain or not address:
            return
        k = key(chain, address)
        s = seeds.setdefault(k, {'chain': chain, 'address': address, 'description': '', 'links': [], 'sources': []})
        s['description'] = s['description'] or description or ''
        s['links'].extend(links or [])
        if source not in s['sources']:
            s['sources'].append(source)

    for endpoint in ('token-profiles/latest/v1', 'token-boosts/latest/v1', 'token-boosts/top/v1'):
        url = DEX + '/' + endpoint
        rows = client.get(url)
        for row in rows if isinstance(rows, list) else []:
            add(row.get('chainId'), row.get('tokenAddress'), url, row.get('description'), row.get('links'))
    for page in range(1, pages + 1):
        url = GECKO + f'/networks/new_pools?page={page}'
        result = client.get(url) or {}
        for row in result.get('data', []):
            rel = row.get('relationships', {})
            network = rel.get('network', {}).get('data', {}).get('id', '')
            token = rel.get('base_token', {}).get('data', {}).get('id', '')
            prefix = network + '_'
            if token.startswith(prefix):
                add(NETWORKS.get(network, network), token[len(prefix):], url)
    if seed_file:
        for row in csv.DictReader(Path(seed_file).open(encoding='utf-8-sig', newline='')):
            add(row['chain'], row['address'], row['source_url'], row.get('description'), [{'url': row.get('contact_url', '')}])
    return seeds


def enrich(client, seeds):
    grouped = defaultdict(list)
    for seed in seeds.values():
        grouped[seed['chain']].append(seed)
    projects = []
    for chain, group in grouped.items():
        for start in range(0, len(group), 30):
            batch = group[start:start + 30]
            url = DEX + '/tokens/v1/' + quote(chain, safe='') + '/' + ','.join(quote(s['address'], safe='') for s in batch)
            response = client.get(url)
            rows = response if isinstance(response, list) else []
            for seed in batch:
                pairs = [r for r in rows if key(chain, r.get('baseToken', {}).get('address', '')) == key(chain, seed['address'])]
                if not pairs:
                    continue
                pairs.sort(key=lambda r: (r.get('liquidity') or {}).get('usd') or 0, reverse=True)
                pair = pairs[0]
                timestamps = [p['pairCreatedAt'] / 1000 for p in pairs if isinstance(p.get('pairCreatedAt'), (int, float))]
                links = list(seed['links'])
                sites = set()
                for p in pairs:
                    info = p.get('info') or {}
                    links.extend(info.get('socials') or [])
                    sites.update(w['url'] for w in info.get('websites', []) if safe_url(w.get('url', '')))
                sites.update(l['url'] for l in links if l.get('label', '').lower() == 'website' and safe_url(l.get('url', '')))
                created = min(timestamps) if timestamps else None
                projects.append({
                    'id': key(chain, seed['address']), 'name': pair['baseToken'].get('name', seed['address']),
                    'chain': chain, 'address': seed['address'], 'description': seed['description'],
                    'pool_created_at': datetime.fromtimestamp(created, timezone.utc).isoformat() if created else '',
                    'pool_timestamp': created, 'launch_date': 'Unverified — pool age is not project launch age',
                    'contact_links': contacts(links), 'contact_verification': 'Source-listed; team ownership and messaging availability not checked',
                    'websites': sorted(sites), 'website_status': 'Link listed; ownership/functionality unverified' if sites else 'No website link in retrieved metadata',
                    'community_size': 'Unknown', 'meme_classification': 'Unverified',
                    'sources': seed['sources'] + [url], 'listing': safe_url(pair.get('url')),
                    'research_status': 'Needs post and product review', 'facts': [], 'opportunities': [],
                    'developer_pitch': '', 'designer_pitch': '', 'follow_up_status': 'Not contacted',
                })
    return projects


def qualify(projects, emitted, now, max_days):
    return sorted([p for p in projects if p['id'] not in emitted and p['contact_links'] and p['pool_timestamp'] is not None and 0 <= now - p['pool_timestamp'] <= max_days * 86400], key=lambda p: p['pool_timestamp'], reverse=True)


def csv_safe(value):
    value = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def write_report(folder, projects, summary):
    (folder / 'leads.json').write_text(json.dumps({'summary': summary, 'projects': projects}, indent=2, ensure_ascii=False))
    fields = ['name', 'chain', 'address', 'pool_created_at', 'launch_date', 'description', 'contact_links', 'contact_verification', 'website_status', 'websites', 'community_size', 'research_status', 'facts', 'opportunities', 'developer_pitch', 'designer_pitch', 'follow_up_status', 'listing', 'sources']
    with (folder / 'leads.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for project in projects:
            writer.writerow({k: csv_safe(project.get(k, '')) for k in fields})
    esc = lambda x: html.escape(str(x), quote=True)
    cards = []
    for p in projects:
        anchors = ' '.join(f'<a href="{esc(u)}" target="_blank" rel="noopener noreferrer">{esc(u)}</a>' for u in p['contact_links'])
        cards.append(f'<article><span class="tag">RESEARCH QUEUE · {esc(p["chain"])}</span><h2>{esc(p["name"])}</h2><p>{esc(p["description"] or "Description not supplied by source.")}</p><p><b>Earliest retrieved pool:</b> {esc(p["pool_created_at"])}</p><p>{esc(p["launch_date"])}</p><p class="address">{esc(p["address"])}</p><p>{anchors}</p><p class="muted">{esc(p["contact_verification"])}</p><details><summary>Research before pitching</summary><ol><li>Match the contract to the project’s own profile.</li><li>Read launch, pinned and recent posts. Record URLs and dates.</li><li>Inspect the product and visuals. Record one observable issue.</li><li>Separate confirmed issues from proposed improvements.</li><li>Draft a developer or designer pitch around one deliverable.</li></ol></details></article>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Project Hunt · Research queue</title><style>body{font:16px/1.6 system-ui;background:#101817;color:#edf5ef;margin:0}main{max-width:1000px;margin:auto;padding:48px 22px}h1{font-size:44px;letter-spacing:-2px;margin:12px 0}h2{margin:10px 0}.eyebrow,.tag{color:#a6e5bc;font-size:12px;letter-spacing:1px}header{border-bottom:1px solid #40534a;padding-bottom:28px}article{background:#1b2723;border:1px solid #35473d;border-radius:16px;padding:24px;margin:18px 0}a{color:#acf3c8;overflow-wrap:anywhere;display:inline-block;margin-right:16px}.muted{color:#b5c6be;font-size:14px}.address{font:12px monospace;overflow-wrap:anywhere}input{box-sizing:border-box;width:100%;padding:14px;border:1px solid #52685b;border-radius:10px;background:#17221c;color:white;margin:22px 0}summary{cursor:pointer}pre{white-space:pre-wrap;color:#ffcf8e}</style><main><header><div class="eyebrow">PROJECT HUNT / DEVELOPER + DESIGNER</div><h1>Find the project.<br>Understand the opportunity.</h1><p>Public discovery → evidence review → tailored pitch → your outreach</p>'''
    page += f'<p><b>{len(projects)} candidates / {summary["target"]} daily target</b> · {summary["shortfall"]} shortfall</p><p class="muted">Generated {esc(summary["generated_at"])}. These are source-listed candidates, not fully researched or verified leads. No messages have been sent.</p></header><label for="search">Filter projects</label><input id="search" placeholder="Project, chain, description or contact"><section id="cards">' + ''.join(cards) + '</section>'
    if summary['errors']:
        page += '<h2>Collection gaps</h2><pre>' + esc('\n'.join(summary['errors'])) + '</pre>'
    page += '<script>document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("article").forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q))})</script></main></html>'
    (folder / 'index.html').write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=int, default=50)
    parser.add_argument('--max-age-days', type=int, default=7, help='Earliest retrieved pool age, NOT launch date')
    parser.add_argument('--gecko-pages', type=int, default=5)
    parser.add_argument('--seed-csv', help='Manual discovery import: chain,address,source_url,description,contact_url')
    parser.add_argument('--output', default='reports')
    parser.add_argument('--state', default='state.sqlite3')
    args = parser.parse_args()
    if not (1 <= args.target <= 500 and 1 <= args.max_age_days <= 365 and 0 <= args.gecko_pages <= 10):
        parser.error('target 1–500; max-age-days 1–365; gecko-pages 0–10')
    now = datetime.now(timezone.utc)
    folder = Path(args.output) / now.strftime('%Y-%m-%dT%H%M%S%fZ')
    folder.mkdir(parents=True)
    client = Client(folder / 'evidence')
    db = sqlite3.connect(args.state)
    db.execute('CREATE TABLE IF NOT EXISTS emitted (id TEXT PRIMARY KEY, emitted_at TEXT)')
    emitted = {r[0] for r in db.execute('SELECT id FROM emitted')}
    seeds = discover(client, args.gecko_pages, args.seed_csv)
    enriched = enrich(client, seeds)
    selected = qualify(enriched, emitted, now.timestamp(), args.max_age_days)[:args.target]
    summary = {'generated_at': now.isoformat(), 'target': args.target, 'discovered': len(seeds), 'enriched': len(enriched), 'candidates': len(selected), 'research_verified': 0, 'shortfall': max(0, args.target - len(selected)), 'errors': client.errors, 'coverage': 'DEX Screener and GeckoTerminal; manual seed import for other platforms. X/Instagram posts not automatically read.'}
    write_report(folder, selected, summary)
    db.executemany('INSERT OR IGNORE INTO emitted VALUES (?, ?)', [(p['id'], now.isoformat()) for p in selected])
    db.commit()
    db.close()
    print(json.dumps({'folder': str(folder.resolve()), **summary}, indent=2))
    if not seeds and client.errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
