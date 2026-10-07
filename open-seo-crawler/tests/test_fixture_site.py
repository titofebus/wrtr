#!/usr/bin/env python3
"""End to end: crawl a site built to carry every fault, assert what comes back.

test_page_checks.py calls each check with a fixture string. This does the whole
pipeline instead: a real site over real HTTP, through the real crawl route, and
then asserts the issue list on each row. It catches what unit tests cannot, such
as a check that never gets called, a crawl-level pass that does not run, or a
finding attached to the wrong URL.

Every page carries ONE named fault, so a failure names the broken check. The
clean pages are asserted too, because a check that fires everywhere is as
useless as one that never fires.

    python3 tests/test_fixture_site.py

No network: the fixture is served from 127.0.0.1 and the crawler runs in
process. Takes about 20 seconds.
"""
import json
import os
import socket
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(HERE, 'fixture_site'))

PASS = 0
FAILURES = []


def check(name, cond):
    global PASS
    if cond:
        PASS += 1
    else:
        FAILURES.append(name)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ── build and serve the fixture ───────────────────────────────────────────────
import build as fixture_build          # noqa: E402
import serve as fixture_serve          # noqa: E402

SITE_PORT = free_port()
BASE = f'http://127.0.0.1:{SITE_PORT}'
fixture_build.build(BASE)
httpd, _ = fixture_serve.start(SITE_PORT)

# ── run the real crawler in process ───────────────────────────────────────────
import app as crawler                  # noqa: E402

CRAWL_PORT = free_port()
threading.Thread(
    target=lambda: crawler.app.run(host='127.0.0.1', port=CRAWL_PORT,
                                   debug=False, threaded=True),
    daemon=True).start()

for _ in range(60):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{CRAWL_PORT}/', timeout=1).read()
        break
    except Exception:
        time.sleep(0.25)


def post(path, payload, timeout=120):
    req = urllib.request.Request(
        f'http://127.0.0.1:{CRAWL_PORT}{path}', data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


rows, complete = [], None
with post('/crawl', {'url': BASE + '/', 'max_pages': 60, 'delay': 0,
                     'render_js': False}, timeout=300) as resp:
    for raw in resp:
        line = raw.decode('utf-8', 'replace').strip()
        if not line.startswith('data: '):
            continue
        msg = json.loads(line[6:])
        kind = msg.get('type')
        if kind == 'page':
            rows.append(msg.get('data') or msg)
        elif kind == 'limit_reached':
            post('/crawl/continue', {'crawl_id': msg.get('crawl_id'),
                                     'action': 'finalize'}, timeout=30).read()
        elif kind == 'complete':
            complete = msg
            break

httpd.shutdown()


def _key(u):
    """Path only, no query, no trailing slash. The search page is reached as
    /search/?q=widgets, so keying on the raw URL would never match it."""
    u = (u or '').split('?')[0].split('#')[0]
    return u.rstrip('/')


by_url = {}
for r in rows:
    by_url.setdefault(_key(r.get('url')), r)
    if r.get('original_url'):
        by_url.setdefault(_key(r['original_url']), r)

# The crawl-level findings ride on the complete event, because they cannot
# exist until every row is in and the rows were streamed long before that. The
# browser merges them onto the rows it holds; this does the same, so the test
# exercises the same path the UI does.
late = (complete or {}).get('late_issues') or {}
for _u, _list in late.items():
    _row = by_url.get(_key(_u))
    if not _row:
        continue
    _row.setdefault('issues', [])
    for _i in _list:
        if _i not in _row['issues']:
            _row['issues'].append(_i)


def issues(path):
    row = by_url.get(_key(BASE + path))
    return [i.lower() for i in (row.get('issues') or [])] if row else None


def fires(path, fragment):
    got = issues(path)
    if got is None:
        return False
    return any(fragment.lower() in i for i in got)


def quiet(path, fragment):
    got = issues(path)
    if got is None:
        return False
    return not any(fragment.lower() in i for i in got)


# ── the crawl itself ──────────────────────────────────────────────────────────
check('the crawl completed', complete is not None)
check('the crawl found the fixture pages', len(rows) >= 18)
for path in ('/', '/lorem', '/images-no-dims', '/dead-end', '/blog',
             '/only-from-noindex', '/hreflang-en', '/big', '/no-head'):
    check(f'crawled {path or "/"}', issues(path) is not None)

# ── one fault per page ────────────────────────────────────────────────────────
check('lorem ipsum is found', fires('/lorem', 'lorem ipsum placeholder'))
check('images with no dimensions are found',
      fires('/images-no-dims', 'image(s) with no width or height'))
check('the sized image is not counted',
      fires('/images-no-dims', '2 image(s) with no width or height'))
check('the insecure form is found',
      fires('/forms-insecure', 'form(s) submit over http'))
check('local and staging links are found',
      fires('/local-links', 'link(s) to a local or staging host'))
check('the real website is not called staging',
      quiet('/local-links', 'dev.to'))
check('the canonical fragment is found',
      fires('/canonical-fragment', 'canonical contains a fragment'))
check('a canonical naming a 404 is found',
      fires('/canonical-to-404', 'canonical points to a non-200'))
check('a canonical naming a redirect is found',
      fires('/canonical-to-redirect', 'canonical points to a url that redirects'))
check('a canonical naming a noindex page is found',
      fires('/canonical-to-noindex', 'canonical points to a non-indexable'))
check('a page with no outgoing links is found',
      fires('/dead-end', 'no internal outlinks'))
check('a page linked only from noindex is found',
      fires('/only-from-noindex', 'only from non-indexable'))
check('unreachable pagination is found',
      fires('/blog', 'pagination url(s) declared by rel'))
check('a one-way hreflang pair is found',
      fires('/hreflang-en', 'do not link back'))
# A repeated path segment is NOT asserted: the crawler refuses to fetch such a
# URL at all, which is a better defence than reporting on it afterwards.
check('the crawler never fetched the repeated-slug URL',
      issues('/blog/blog/post') is None)
check('an internal search page is found',
      fires('/search', 'internal search result page'))
check('a missing head element is found', fires('/no-head', 'no <head> element'))
check('a missing body element is found', fires('/no-body', 'no <body> element'))
check('an oversized document is found', fires('/big', 'over 2mb'))

# ── the clean pages must stay clean ───────────────────────────────────────────
NEW_FINDINGS = (
    'lorem ipsum placeholder', 'link(s) to a local or staging host',
    'form(s) submit over http', 'image(s) with no width or height',
    'pagination url(s) declared by rel', 'canonical contains a fragment',
    'canonical points to a', 'no <head> element', 'no <body> element',
    'over 2mb', 'no internal outlinks', 'only from non-indexable',
    'do not link back', 'repetitive path', 'internal search result page',
)
for path, label in (('/', 'the home page'), ('/clean-second', 'the clean second page'),
                    ('/about', 'the about page'), ('/services', 'the services page')):
    got = issues(path) or []
    noisy = [f for f in NEW_FINDINGS if any(f in i for i in got)]
    check(f'{label} carries none of the new findings (got {noisy})', not noisy)

# A site served from localhost must not have every link called a local link.
check('internal links on a localhost site are not called local links',
      quiet('/', 'link(s) to a local or staging host'))
check('a form posting to localhost is not called insecure',
      quiet('/', 'form(s) submit over http'))

# ── report ────────────────────────────────────────────────────────────────────
if FAILURES:
    for f in FAILURES:
        print('FAIL: ' + f)
    print('\ncrawled URLs and how many late findings arrived:')
    print(f'  late_issues on the complete event: {len(late)} url(s)')
    for u in sorted(by_url):
        print('   ' + (u.replace(BASE, '') or '/'))
    print(f'{PASS}/{PASS + len(FAILURES)} fixture-site checks passed')
    sys.exit(1)
print(f'{PASS}/{PASS} fixture-site checks passed ({len(rows)} pages crawled)')
