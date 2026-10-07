#!/usr/bin/env python3
"""page_checks tests: fixtures in, issue strings out. No network, no server.

Sits next to test_data_correctness.py, but needs neither Playwright nor a
running app: every check calls page_checks directly with a fixture string.

    python3 test_page_checks.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup

import page_checks as pc

PASS = 0


def check(name, cond):
    global PASS
    if not cond:
        print(f'FAIL: {name}')
        sys.exit(1)
    PASS += 1


def has(issues, fragment):
    return any(fragment.lower() in i.lower() for i in issues)


def soup_of(html):
    return BeautifulSoup(html, 'html.parser')


def result(**kw):
    base = {
        'url': 'https://example.com/page', 'status_code': 200, 'indexable': True,
        'title': '', 'meta_description': '', 'h1': '', 'h1_list': [],
        'word_count': 800, 'canonical': '', 'canonical_kind': 'missing',
        'hreflang': [], 'security': {'is_https': True}, 'is_pagination': False,
        'images_all_data': [],
    }
    base.update(kw)
    return base


# --- head position -----------------------------------------------------------
# A browser closes head at the <img>, so everything after it lands in body.
BROKEN_HEAD = '''<!doctype html><html><head><meta charset="utf-8">
<img src="logo.png">
<title>Still in the markup head</title>
<link rel="canonical" href="https://example.com/page">
</head><body><h1>Hi</h1></body></html>'''

GOOD_HEAD = '''<!doctype html><html><head><meta charset="utf-8">
<title>Fine</title><link rel="canonical" href="https://example.com/page">
<!-- <div>a comment must not close the head</div> -->
</head><body><img src="logo.png"><h1>Hi</h1></body></html>'''

hi = pc.head_issues(BROKEN_HEAD)
check('title outside head', has(hi, 'Title outside head'))
check('canonical outside head', has(hi, 'Canonical outside head'))
check('clean head stays quiet', pc.head_issues(GOOD_HEAD) == [])
check('no head at all is quiet', pc.head_issues('<html><body>x</body></html>') == [])
check('script in head does not close it',
      pc.head_issues('<head><script>var a=1</script><title>t</title></head>') == [])

# --- duplicate tags ----------------------------------------------------------
d = pc.duplicate_tag_issues(soup_of(
    '<head><title>a</title><title>b</title>'
    '<link rel="canonical" href="/a"><link rel="canonical" href="/b">'
    '<meta name="description" content="1"><meta name="description" content="2">'
    '</head>'))
check('multiple titles', has(d, 'Multiple title tags (2)'))
check('conflicting canonicals', has(d, 'Multiple conflicting canonicals'))
check('multiple descriptions', has(d, 'Multiple meta descriptions'))
same = pc.duplicate_tag_issues(soup_of(
    '<head><link rel="canonical" href="/a"><link rel="canonical" href="/a"></head>'))
check('same canonical twice is not a conflict',
      has(same, 'Multiple canonical tags') and not has(same, 'conflicting'))
check('one of each is quiet', pc.duplicate_tag_issues(soup_of(
    '<head><title>a</title><meta name="description" content="1"></head>')) == [])

# --- canonical ---------------------------------------------------------------
c = pc.canonical_issues(
    result(canonical='https://example.com/other', canonical_kind='canonicalised',
           indexable=False),
    {'link': '<https://example.com/third>; rel="canonical"'}, soup_of(''))
check('header vs html canonical', has(c, 'HTML and HTTP header disagree'))
check('noindex plus canonical', has(c, 'Noindex plus a canonical'))
check('canonical to http flagged', has(pc.canonical_issues(
    result(canonical='http://example.com/page', canonical_kind='self'), {}, soup_of('')),
    'Canonical points to HTTP'))
check('relative canonical flagged', has(pc.canonical_issues(
    result(canonical='/page', canonical_kind='self'), {}, soup_of('')),
    'Canonical is a relative URL'))
check('cross-host canonical flagged', has(pc.canonical_issues(
    result(canonical='https://cdn.example.com/page', canonical_kind='canonicalised'), {},
    soup_of('')), 'another host (cdn.example.com)'))
# Seen live: a template printed an unresolved variable straight into the tag.
junk = pc.canonical_issues(
    result(canonical='https://www.example.comundefined', canonical_kind='canonicalised'),
    {}, soup_of(''))
check('malformed canonical flagged', has(junk, 'Canonical is malformed'))
check('malformed canonical is reported once', len(junk) == 1)
check('null segment canonical flagged', has(pc.canonical_issues(
    result(canonical='https://example.com/null', canonical_kind='self'), {}, soup_of('')),
    'malformed'))
# A real article about undefined behaviour, and a word that merely contains the
# letters of null, must both survive.
check('undefined in a slug is not junk', not has(pc.canonical_issues(
    result(canonical='https://example.com/blog/undefined-behaviour-in-c',
           canonical_kind='self'), {}, soup_of('')), 'malformed'))
check('annulled is not junk', not has(pc.canonical_issues(
    result(canonical='https://example.com/annulled-marriages', canonical_kind='self'),
    {}, soup_of('')), 'malformed'))
check('header-only canonical noted', has(pc.canonical_issues(
    result(), {'link': '<https://example.com/page>; rel="canonical"'}, soup_of('')),
    'only in the HTTP header'))
check('self canonical is quiet', pc.canonical_issues(
    result(canonical='https://example.com/page', canonical_kind='self'), {},
    soup_of('')) == [])

# --- directives --------------------------------------------------------------
dirs = pc.directive_issues(
    soup_of('<meta name="robots" content="index, noindex, nosnippet">'),
    {'x-robots-tag': 'noindex'}, result())
check('conflicting directives', has(dirs, 'Conflicting robots directives'))
check('nosnippet', has(dirs, 'nosnippet'))
check('x-robots noindex', has(dirs, 'X-Robots-Tag'))
check('none directive', has(pc.directive_issues(
    soup_of('<meta name="robots" content="none">'), {}, result()), '"none"'))
check('past unavailable_after', has(pc.directive_issues(
    soup_of('<meta name="robots" content="unavailable_after: 2020-01-01">'), {},
    result()), 'unavailable_after'))
check('future unavailable_after quiet', not has(pc.directive_issues(
    soup_of('<meta name="robots" content="unavailable_after: 2099-01-01">'), {},
    result()), 'unavailable_after'))
check('plain index is quiet', pc.directive_issues(
    soup_of('<meta name="robots" content="index, follow">'), {}, result()) == [])

# --- soft 404 ----------------------------------------------------------------
check('soft 404 by title', has(pc.soft_404_issues(
    result(title='404 Page Not Found', word_count=40)), 'Soft 404'))
check('soft 404 by h1', has(pc.soft_404_issues(
    result(h1='Page not found', word_count=40)), 'Soft 404'))
# A WordPress term archive for a term that reads like an error is a real page.
check('term archive is not a soft 404', pc.soft_404_issues(
    result(title='404 Archives | Example', h1='404', word_count=300)) == [])
check('long article about 404s is not a soft 404', pc.soft_404_issues(
    result(title='How to fix a 404 error', word_count=1400)) == [])
check('real 404 status is left alone', pc.soft_404_issues(
    result(status_code=404, title='Not found', word_count=20)) == [])

# --- pixel width -------------------------------------------------------------
wide = 'W' * 40          # 40 caps blow past the report point well inside 60 chars
check('wide title may truncate', has(pc.pixel_issues(result(title=wide)), 'Title may truncate'))
# Just over the raw limit but inside the tolerance: measured median of real
# over-limit titles, and reporting it would be noise.
check('title just over the limit stays quiet',
      pc.pixel_issues(result(title='Best Plumber Melbourne For Hot Water Repairs')) == [])
check('narrow title fine', pc.pixel_issues(result(title='i' * 55)) == [])
check('char-length overlap suppressed', pc.pixel_issues(result(title='W' * 70)) == [])
# 20 chars of average-width text at 20px Arial measures near 196px, and the
# 580px limit therefore lands close to the 60-character rule.
check('px estimate sane', 180 < pc.text_px('Plumber in Melbourne', 20) < 215)
check('caps measure wider than dots', pc.text_px('W' * 10, 20) > pc.text_px('.' * 10, 20) * 2)

# --- hreflang ----------------------------------------------------------------
h = pc.hreflang_issues(result(hreflang=[
    {'lang': 'en-AU', 'href': 'https://example.com/au'},
    {'lang': 'english', 'href': 'https://example.com/en'},
    {'lang': 'en-AU', 'href': 'https://example.com/dupe'},
]))
check('invalid hreflang code', has(h, 'Invalid hreflang code'))
check('duplicate hreflang code', has(h, 'Duplicate hreflang code'))
check('missing self hreflang', has(h, 'No self-referencing hreflang'))
ok = pc.hreflang_issues(result(
    canonical='https://example.com/page', canonical_kind='self',
    html_lang='en',
    hreflang=[{'lang': 'en', 'href': 'https://example.com/page'},
              {'lang': 'x-default', 'href': 'https://example.com/'}]))
check('healthy cluster is quiet', ok == [])
mismatch = pc.hreflang_issues(result(
    html_lang='de', hreflang=[{'lang': 'en', 'href': 'https://example.com/page'}]))
check('lang vs hreflang mismatch', has(mismatch, 'does not match'))
check('no hreflang is quiet', pc.hreflang_issues(result()) == [])
# Shopify variant and ?page=2 URLs carry the canonical page's cluster, so the
# self-reference belongs to that page, not this one.
check('canonicalised page skips the cluster', pc.hreflang_issues(result(
    canonical_kind='canonicalised',
    hreflang=[{'lang': 'en-AU', 'href': 'https://example.com/product'}])) == [])

# --- lang --------------------------------------------------------------------
r = result()
check('missing lang', has(pc.lang_issues(soup_of('<html><body></body></html>'), r),
                          'No lang attribute'))
check('invalid lang', has(pc.lang_issues(soup_of('<html lang="english">'), result()),
                          'Invalid lang'))
r2 = result()
check('good lang quiet', pc.lang_issues(soup_of('<html lang="en-AU">'), r2) == [])
check('lang recorded on result', r2['html_lang'] == 'en-AU')

# --- headings ----------------------------------------------------------------
hh = pc.heading_issues(result(h1='x' * 80), soup_of('<h2>a</h2><h1>b</h1><h3>c</h3>'))
check('h1 too long', has(hh, 'H1 too long'))
check('first heading not h1', has(hh, 'First heading is H2'))
check('skipped level', has(pc.heading_issues(
    result(h1='ok'), soup_of('<h1>a</h1><h3>b</h3>')), 'Heading level skips'))
check('tidy headings quiet', pc.heading_issues(
    result(h1='ok'), soup_of('<h1>a</h1><h2>b</h2><h3>c</h3><h2>d</h2>')) == [])
check('empty headings ignored', pc.heading_issues(
    result(h1='ok'), soup_of('<h2></h2><h1>a</h1><h2>b</h2>')) == [])

# --- links -------------------------------------------------------------------
li = pc.link_issues(soup_of('''
  <a href="http://example.com/a">insecure</a>
  <a href="https://example.com/b" rel="nofollow">nofollow</a>
  <a href="#nowhere">dead anchor</a>
  <a href="#real">live anchor</a>
  <div id="real"></div>
  <a href="mailto:x@example.com">mail</a>
  <a href="https://cdn.example.com/x" rel="nofollow">external nofollow</a>'''),
    result(), 'https://example.com/page', 'example.com')
check('internal http link', has(li, 'point to HTTP'))
check('internal nofollow', has(li, '1 internal link(s) are nofollow'))
check('dead on-page anchor', has(li, '#nowhere'))
check('live anchor not flagged', not has(li, '#real'))
check('clean links quiet', pc.link_issues(
    soup_of('<a href="/a">a</a><a href="#top">top</a>'), result(),
    'https://example.com/page', 'example.com') == [])

# --- delivery and markup -----------------------------------------------------
big = '<html><head><title>t</title></head><body>' + ('x' * 60_000) + '</body></html>'
dl = pc.delivery_issues({}, big)
check('no compression', has(dl, 'No compression'))
check('no cache-control', has(dl, 'No cache-control'))
check('compressed page quiet on encoding', not has(
    pc.delivery_issues({'content-encoding': 'br', 'cache-control': 'max-age=60'}, big),
    'No compression'))
check('small page not flagged for compression',
      not has(pc.delivery_issues({}, '<html></html>'), 'No compression'))

mk = pc.markup_issues('<html><head><meta charset="iso-8859-1"><title>t</title></head>'
                      '<body></body></html>',
                      soup_of('<html><head><meta charset="iso-8859-1">'
                              '</head><body></body></html>'))
check('no doctype', has(mk, 'No doctype'))
check('charset not utf-8', has(mk, 'not UTF-8'))
check('utf-8 doctype page quiet', pc.markup_issues(
    '<!doctype html><html><head><meta charset="utf-8"></head><body></body></html>',
    soup_of('<head><meta charset="utf-8"></head>')) == [])
check('http-equiv charset counts', not has(pc.markup_issues(
    '<!doctype html><html>',
    soup_of('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">')),
    'No charset'))

# --- dom, images, pagination -------------------------------------------------
check('large dom', has(pc.dom_issues(soup_of('<div></div>' * 1600)), 'Large DOM'))
check('small dom quiet', pc.dom_issues(soup_of('<div></div>' * 10)) == [])
check('long alt', has(pc.image_issues(result(images_all_data=[
    {'alt': 'a' * 200}, {'alt': 'short'}, {'alt': None}])), '1 image(s) with alt text'))
check('a 120 char caption is left alone',
      pc.image_issues(result(images_all_data=[{'alt': 'a' * 120}])) == [])
check('short alts quiet', pc.image_issues(result(images_all_data=[{'alt': 'fine'}])) == [])
pg = pc.pagination_issues(result(is_pagination=True, indexable=False,
                                 canonical_kind='canonicalised'))
check('paginated noindex', has(pg, 'Paginated page set to noindex'))
check('paginated canonicalised', has(pg, 'canonicalised to another URL'))
check('non-paginated quiet', pc.pagination_issues(result(indexable=False)) == [])

# --- placeholder copy --------------------------------------------------------
check('lorem ipsum caught',
      has(pc.placeholder_issues(result(body_text='Intro. Lorem ipsum dolor sit amet.')),
          'Lorem ipsum placeholder'))
check('real copy quiet', pc.placeholder_issues(result(body_text='Real copy here.')) == [])
check('no body text quiet', pc.placeholder_issues(result()) == [])

# --- local and staging outlinks ----------------------------------------------
LOCAL_LINKS = (
    '<html><body>'
    '<a href="http://localhost:3000/admin">admin</a>'
    '<a href="https://10.0.0.5/panel">panel</a>'
    '<a href="https://staging.example.com/thing">staging</a>'
    '<a href="https://example.com/real">real</a>'
    '<a href="https://dev.to/article">an actual website</a>'
    '</body></html>')
ol = pc.outlink_issues(soup_of(LOCAL_LINKS), 'https://example.com/page', 'example.com')
check('localhost outlink caught', has(ol, 'localhost'))
check('private ip outlink caught', has(ol, '10.0.0.5'))
check('same-domain staging caught', has(ol, 'staging.example.com'))
check('dev.to is not treated as staging', not has(ol, 'dev.to'))
check('clean page quiet',
      pc.outlink_issues(soup_of('<a href="/x">x</a>'), 'https://example.com/p',
                        'example.com') == [])

# --- insecure forms ----------------------------------------------------------
check('http form action caught',
      has(pc.form_issues(soup_of('<form action="http://example.com/post"></form>'),
                         result(), 'https://example.com/page'), 'submit over HTTP'))
check('https form quiet',
      pc.form_issues(soup_of('<form action="/post"></form>'), result(),
                     'https://example.com/page') == [])
check('relative form on an http page caught',
      has(pc.form_issues(soup_of('<form action="/post"></form>'),
                         result(security={'is_https': False}), 'http://example.com/p'),
          'submit over HTTP'))
check('https action on an http page is fine',
      pc.form_issues(soup_of('<form action="https://example.com/post"></form>'),
                     result(security={'is_https': False}), 'http://example.com/p') == [])

# --- image dimensions --------------------------------------------------------
check('missing dimensions caught',
      has(pc.image_dimension_issues(soup_of('<img src="a.jpg">')), 'no width or height'))
check('sized image quiet',
      pc.image_dimension_issues(soup_of('<img src="a.jpg" width="4" height="3">')) == [])
check('inline sized image quiet',
      pc.image_dimension_issues(
          soup_of('<img src="a.jpg" style="width:4px;height:3px">')) == [])
check('svg skipped', pc.image_dimension_issues(soup_of('<img src="a.svg">')) == [])

# --- pagination reachability -------------------------------------------------
REL_ONLY = '<html><head><link rel="next" href="/blog/2/"></head><body></body></html>'
REL_LINKED = ('<html><head><link rel="next" href="/blog/2/"></head>'
              '<body><a href="/blog/2/">next</a></body></html>')
check('rel next with no anchor caught',
      has(pc.pagination_anchor_issues(soup_of(REL_ONLY), 'https://example.com/blog/'),
          'not linked in an anchor tag'))
check('rel next with an anchor quiet',
      pc.pagination_anchor_issues(soup_of(REL_LINKED), 'https://example.com/blog/') == [])
check('no rel next quiet',
      pc.pagination_anchor_issues(soup_of('<html></html>'), 'https://example.com/') == [])

# --- url shape ---------------------------------------------------------------
# A repeated path segment is not reported here on purpose: the crawler refuses
# to fetch such a URL, so this check could never see one.
check('repeated segments are left to the crawler filter',
      pc.url_shape_issues('https://example.com/blog/blog/post') == [])
check('search path caught',
      has(pc.url_shape_issues('https://example.com/search/widgets'), 'internal search'))
check('search param caught',
      has(pc.url_shape_issues('https://example.com/?s=widgets'), 'internal search'))
check('ordinary url quiet', pc.url_shape_issues('https://example.com/about/team') == [])

# --- canonical fragment ------------------------------------------------------
check('canonical fragment caught',
      has(pc.canonical_issues(result(canonical='https://example.com/page#reviews'), {},
                              soup_of('')), 'fragment'))
check('clean canonical quiet',
      not has(pc.canonical_issues(result(canonical='https://example.com/page'), {},
                                  soup_of('')), 'fragment'))

# --- document structure ------------------------------------------------------
NO_HEAD = '<!doctype html><html><body><p>hi</p></body></html>'
check('missing head caught', has(pc.markup_issues(NO_HEAD, soup_of(NO_HEAD)), 'No <head>'))
NO_BODY = '<!doctype html><html><head><title>t</title></head></html>'
check('missing body caught', has(pc.markup_issues(NO_BODY, soup_of(NO_BODY)), 'No <body>'))
BIG = '<!doctype html><html><head></head><body>' + ('x' * 2_100_000) + '</body></html>'
check('oversize document caught', has(pc.markup_issues(BIG, soup_of('')), 'over 2MB'))

# --- crawl-level checks ------------------------------------------------------
def row(url, **kw):
    r = result(url=url)
    r.update(kw)
    return r


rows = [row('https://example.com/a', canonical='https://example.com/b'),
        row('https://example.com/b', indexable=False)]
check('canonical to a noindex target',
      has(pc.crawl_issues(rows).get('https://example.com/a', []), 'non-indexable URL'))
rows = [row('https://example.com/a', canonical='https://example.com/b'),
        row('https://example.com/b', status_code=404)]
check('canonical to a 404 target',
      has(pc.crawl_issues(rows).get('https://example.com/a', []), 'non-200'))
# The crawler follows redirects, so the row for a redirecting URL carries the
# DESTINATION as `url` and the redirecting address as `original_url`. Only a
# canonical naming the address that redirects is a fault: one naming the
# destination is a correctly written tag, which is what trailing-slash
# normalisation produces on every WordPress site.
rows = [row('https://example.com/a', canonical='https://example.com/b-old'),
        row('https://example.com/b', original_url='https://example.com/b-old',
            redirect_url='https://example.com/b')]
check('canonical naming the URL that redirects',
      has(pc.crawl_issues(rows).get('https://example.com/a', []), 'redirects'))
rows = [row('https://example.com/a', canonical='https://example.com/b'),
        row('https://example.com/b', original_url='https://example.com/b-old',
            redirect_url='https://example.com/b')]
check('canonical naming the destination is not a fault',
      not has(pc.crawl_issues(rows).get('https://example.com/a', []), 'redirects'))
rows = [row('https://example.com/a', canonical='https://example.com/b'),
        row('https://example.com/b')]
check('healthy canonical quiet',
      not any('Canonical points' in i
              for i in pc.crawl_issues(rows).get('https://example.com/a', [])))

# A redirecting row still carries the destination response, so it stays indexable.
check('redirect row counts as indexable',
      pc._is_indexable_row({'status_code': 200, 'indexable': True,
                            'redirect_url': 'https://example.com/x'}))

rows = [row('https://example.com/en/', internal_link_urls=['x'],
            hreflang=[{'lang': 'fr', 'href': 'https://example.com/fr/'}]),
        row('https://example.com/fr/', internal_link_urls=['x'], hreflang=[])]
check('missing hreflang return link',
      has(pc.crawl_issues(rows).get('https://example.com/en/', []), 'do not link back'))
rows = [row('https://example.com/en/', internal_link_urls=['x'],
            hreflang=[{'lang': 'fr', 'href': 'https://example.com/fr/'}]),
        row('https://example.com/fr/', internal_link_urls=['x'],
            hreflang=[{'lang': 'en', 'href': 'https://example.com/en/'}])]
check('paired hreflang quiet',
      not has(pc.crawl_issues(rows).get('https://example.com/en/', []), 'link back'))
rows = [row('https://example.com/dup', canonical_kind='canonicalised',
            internal_link_urls=['x'],
            hreflang=[{'lang': 'fr', 'href': 'https://example.com/fr/'}]),
        row('https://example.com/fr/', internal_link_urls=['x'], hreflang=[])]
check('canonicalised page is not judged on hreflang',
      not has(pc.crawl_issues(rows).get('https://example.com/dup', []), 'link back'))

check('no internal outlinks caught',
      has(pc.crawl_issues([row('https://example.com/a')]).get('https://example.com/a', []),
          'No internal outlinks'))
check('a PDF is not called a dead end',
      not has(pc.crawl_issues([row('https://example.com/a.pdf',
                                   content_type='application/pdf')])
              .get('https://example.com/a.pdf', []), 'No internal outlinks'))
check('an html row still is',
      has(pc.crawl_issues([row('https://example.com/a',
                               content_type='text/html; charset=utf-8')])
          .get('https://example.com/a', []), 'No internal outlinks'))
check('errored row is not called a dead end',
      not has(pc.crawl_issues([row('https://example.com/a', error='timeout')])
              .get('https://example.com/a', []), 'No internal outlinks'))
check('foreign host row skipped',
      pc.crawl_issues([row('https://example.com/a', internal_link_urls=['x']),
                       row('https://example.com/b', internal_link_urls=['x']),
                       row('https://other.com/x')],
                      domain='example.com').get('https://other.com/x') is None)

rows = [row('https://example.com/post', internal_link_urls=['x']),
        row('https://example.com/tag', internal_link_urls=['x'], indexable=False)]
inl = {'https://example.com/post': [{'source': 'https://example.com/tag'}]}
check('non-indexable inlinks only',
      has(pc.crawl_issues(rows, inl).get('https://example.com/post', []),
          'only from non-indexable'))
rows = [row('https://example.com/post', internal_link_urls=['x']),
        row('https://example.com/hub', internal_link_urls=['x'])]
inl = {'https://example.com/post': [{'source': 'https://example.com/hub'}]}
check('indexable inlink quiet',
      not has(pc.crawl_issues(rows, inl).get('https://example.com/post', []),
              'only from non-indexable'))

check('crawl_issues never raises on junk', pc.crawl_issues([], None) == {})
check('crawl_issues ignores malformed rows', pc.crawl_issues([{}, None, 3]) == {})


# --- the whole module together ----------------------------------------------
everything = pc.extra_issues(
    BROKEN_HEAD, soup_of(BROKEN_HEAD), {},
    result(title='404 Not Found', word_count=30), 'https://example.com/page',
    'example.com')
check('extra_issues gathers across checks', len(everything) >= 3)
check('extra_issues finds the head fault', has(everything, 'outside head'))
check('extra_issues finds the soft 404', has(everything, 'Soft 404'))
check('extra_issues never raises on junk',
      isinstance(pc.extra_issues('', soup_of(''), {}, {}, '', ''), list))

print(f'{PASS}/{PASS} page_checks checks passed')
