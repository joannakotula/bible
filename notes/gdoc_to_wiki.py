#!/usr/bin/env python3
"""
gdoc_to_wiki.py
Fetches a public Google Doc (link) and converts it to simple MediaWiki wikicode.

Usage:
    python gdoc_to_wiki.py "https://docs.google.com/document/d/ID/edit"

Requirements:
    pip install requests beautifulsoup4
"""

import sys
import re
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from html import unescape
from urllib.parse import urlparse, parse_qs

EXPORT_HTML_TEMPLATE = "https://docs.google.com/document/d/{doc_id}/export?format=html"

def extract_doc_id(url: str) -> str:
    """
    Tries to extract the document ID from the given Google Docs link.
    Returns None if it cannot be found.
    """
    # common patterns: /d/<id>/ or id in query param ?id=...
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if m:
        return m.group(1)
    # fallback: maybe full URL with u/0/... or ?id=
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    if 'id' in q:
        return q['id'][0]
    return None

def fetch_doc_html(link: str) -> str:
    doc_id = extract_doc_id(link)
    if doc_id:
        export_url = EXPORT_HTML_TEMPLATE.format(doc_id=doc_id)
        r = requests.get(export_url, timeout=15)
        if r.status_code == 200 and r.text.strip():
            return r.text
        # if the export does not work (e.g. not public), try fetching directly
    # last resort: fetch the URL directly (it may be a published link)
    r = requests.get(link, timeout=15)
    r.raise_for_status()
    return r.text

def escape_wiki_text(s: str) -> str:
    # minimal cleanup: remove excess whitespace, reverse HTML encoding
    s = unescape(s)
    # additionally remove \xa0 (non-breaking space) -> normal space
    s = s.replace('\xa0', ' ')
    return s

def inline_text(node) -> str:
    """
    Converts a node (NavigableString or Tag) into inline wikiformat:
     - <b>/<strong> -> '''bold'''
     - <i>/<em> -> ''italic''
     - <u> -> <u>...</u> (MediaWiki supports the <u> tag)
     - <a href="...">text</a> -> [url text] (if the URL is external)
     - <code> / <tt> -> <code>...</code> (inline block)
    Recursively for children.
    """
    if isinstance(node, NavigableString):
        return escape_wiki_text(str(node))
    if not isinstance(node, Tag):
        return ''
    tag = node.name.lower()
    # handle tags that should not contain trailing whitespace
    if tag in ('br',):
        return '\n'
    pieces = []
    if tag in ('b', 'strong'):
        pieces.append("'''")
        for c in node.children:
            pieces.append(inline_text(c))
        pieces.append("'''")
        return ''.join(pieces)
    if tag in ('i', 'em'):
        pieces.append("''")
        for c in node.children:
            pieces.append(inline_text(c))
        pieces.append("''")
        return ''.join(pieces)
    if tag == 'u':
        pieces.append("<u>")
        for c in node.children:
            pieces.append(inline_text(c))
        pieces.append("</u>")
        return ''.join(pieces)
    if tag in ('code', 'tt'):
        pieces.append('<code>')
        for c in node.children:
            pieces.append(inline_text(c))
        pieces.append('</code>')
        return ''.join(pieces)
    if tag == 'a':
        href = node.get('href', '').strip()
        text = ''.join(inline_text(c) for c in node.children).strip()
        if not href:
            return text
        # If this is an internal wiki link (small heuristic test: no http or wiki domain), leave it as [[...]]
        if href.startswith('/') or href.startswith('#'):
            return f'[[{text or href}]]'
        # normal external link: [URL text]
        if text and text != href:
            return f'[{href} {text}]'
        else:
            return f'[{href}]'
    # images inline
    if tag == 'img':
        src = node.get('src') or node.get('data-src') or ''
        alt = node.get('alt', '')
        if src:
            # MediaWiki prefers files in File:, but for a quick import we will leave <img>
            return f'<img src="{src}" alt="{alt}">'
        return ''
    # default: join the children
    for c in node.children:
        pieces.append(inline_text(c))
    return ''.join(pieces)

def list_to_wiki(nodes, list_type='ul', depth=0):
    """
    nodes: list of <li> Tag
    list_type: 'ul' or 'ol'
    depth: nesting level (0 = top)
    """
    lines = []
    for li in nodes:
        # compute prefix: '*' for ul, '#' for ol, repeated for depth+1
        prefix_sym = '*' if list_type == 'ul' else '#'
        prefix = prefix_sym * (depth + 1)
        # li may contain paragraphs or further lists; build inline text from its
        line_parts = []
        for child in li.children:
            if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                continue  # we will build nested lists separately
            line_parts.append(inline_text(child))
        line = prefix + ' ' + ''.join(line_parts).strip()
        lines.append(line)
        # check nested lists directly under li
        for child in li.children:
            if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                lines.extend(list_to_wiki(child.find_all('li', recursive=False),
                                          list_type=('ul' if child.name == 'ul' else 'ol'),
                                          depth=depth+1))
    return lines

def element_to_wiki(elem) -> list:
    """
    Converts the direct elements of <body> into a list of wikicode lines.
    Supported: h1..h6, p, pre, ul, ol, img, blockquote, hr, table (simply)
    """
    lines = []
    if isinstance(elem, NavigableString):
        txt = escape_wiki_text(str(elem)).strip()
        if txt:
            lines.append(txt)
        return lines

    if not isinstance(elem, Tag):
        return lines

    name = elem.name.lower()
    if name in ('h1','h2','h3','h4','h5','h6'):
        # map: h1 -> =title=, h2 -> == ..., h3 -> === ...
        level = int(name[1])
        # MediaWiki: '='..'=' ; typically the first level is =Title= (less common), but we will leave it as:
        eqs = '=' * level
        inner = ''.join(inline_text(c) for c in elem.children).strip()
        lines.append(f'{eqs} {inner} {eqs}')
        return lines
    if name == 'p':
        txt = ''.join(inline_text(c) for c in elem.children).strip()
        if txt == '':
            # empty paragraph -> empty line
            lines.append('')
        else:
            lines.append(txt)
        return lines
    if name in ('ul','ol'):
        lis = elem.find_all('li', recursive=False)
        if lis:
            list_lines = list_to_wiki(lis, list_type=('ul' if name=='ul' else 'ol'), depth=0)
            lines.extend(list_lines)
        return lines
    if name == 'li':
        txt = ''.join(inline_text(c) for c in elem.children).strip()
        lines.append('* ' + txt)
        # nested lists
        for child in elem.children:
            if isinstance(child, Tag) and child.name in ('ul','ol'):
                lines.extend(element_to_wiki(child))
        return lines
    if name == 'pre':
        # keep the pre block as <pre>...</pre>
        content = ''.join(str(c) for c in elem.contents)
        lines.append('<pre>')
        lines.append(content.rstrip('\n'))
        lines.append('</pre>')
        return lines
    if name == 'blockquote':
        # simple blockquote -> start with >
        inner = ''.join(inline_text(c) for c in elem.children).strip()
        for l in inner.splitlines():
            lines.append('> ' + l)
        return lines
    if name == 'hr':
        lines.append('----')
        return lines
    if name == 'img':
        src = elem.get('src') or elem.get('data-src') or ''
        alt = elem.get('alt','')
        if src:
            lines.append(f'<img src="{src}" alt="{alt}">')
        return lines
    if name == 'table':
        # simple table conversion to wikitable
        lines.append('{| class="wikitable"')
        for tr in elem.find_all('tr', recursive=False):
            lines.append('|-')
            tds = tr.find_all(['th','td'], recursive=False)
            row_parts = []
            for td in tds:
                prefix = '!' if td.name == 'th' else '|'
                cell_text = ''.join(inline_text(c) for c in td.children).strip()
                row_parts.append(prefix + ' ' + cell_text)
            lines.extend(row_parts)
        lines.append('|}')
        return lines

    # by default: recurse into children for other tags
    child_text = []
    for child in elem.children:
        # if the child is a block (p, ul, h2, etc.) — use the element_to_wiki function
        if isinstance(child, Tag) and child.name in ('p','h1','h2','h3','h4','h5','h6','ul','ol','pre','table','blockquote','hr','img'):
            lines.extend(element_to_wiki(child))
        else:
            text = inline_text(child)
            if text.strip():
                child_text.append(text)
    if child_text:
        # join and add as a paragraph
        joined = ''.join(child_text).strip()
        lines.append(joined)
    return lines

def html_to_wiki(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    # Google export HTML usually contains <body> with the content; find the main container
    body = soup.body or soup
    output_lines = []
    # many Google documents have a <div id="contents"> or .kix... container
    # iterate over the direct children of body to preserve block order
    for child in body.children:
        # ignore empty navigable strings that are only whitespace
        if isinstance(child, NavigableString) and not child.strip():
            continue
        block_lines = element_to_wiki(child)
        if block_lines:
            output_lines.extend(block_lines)
            # add an empty line after the block (readability)
            output_lines.append('')
    # remove excess empty lines (at most two in a row)
    cleaned = []
    blank_count = 0
    for l in output_lines:
        if l.strip() == '':
            blank_count += 1
        else:
            blank_count = 0
        if blank_count <= 2:
            cleaned.append(l)
    return '\n'.join(cleaned).strip() + '\n'

def main():
    if len(sys.argv) < 2:
        print("Użycie: python gdoc_to_wiki.py <link_do_google_doc>")
        sys.exit(1)
    link = sys.argv[1]
    try:
        html = fetch_doc_html(link)
    except Exception as e:
        print(f"Błąd pobierania dokumentu: {e}")
        sys.exit(2)
    wiki = html_to_wiki(html)
    # write to stdout; the user can redirect to a file
    print(wiki)

if __name__ == '__main__':
    main()
