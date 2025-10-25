#!/usr/bin/env python3
"""
gdoc_to_wiki.py
Pobiera publiczny Google Doc (link) i konwertuje go na prosty wikikod MediaWiki.

Użycie:
    python gdoc_to_wiki.py "https://docs.google.com/document/d/ID/edit"

Wymagania:
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
    Próbuje wyciągnąć ID dokumentu z podanego linku Google Docs.
    Zwraca None jeśli nie uda się znaleźć.
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
        # jeśli eksport nie działa (np. niepubliczny), spróbuj pobrać bezpośrednio
    # ostatnia deska ratunku: pobierz bezpośrednio URL (może być publikowany "published" link)
    r = requests.get(link, timeout=15)
    r.raise_for_status()
    return r.text

def escape_wiki_text(s: str) -> str:
    # minimalne oczyszczanie: usuń nadmiar białych znaków, odwrotne encodowanie HTML
    s = unescape(s)
    # dodatkowo usuwamy \xa0 (non-breaking space) -> normalna spacja
    s = s.replace('\xa0', ' ')
    return s

def inline_text(node) -> str:
    """
    Konwertuje node (NavigableString lub Tag) na wikiformat inline:
     - <b>/<strong> -> '''bold'''
     - <i>/<em> -> ''italic''
     - <u> -> <u>...</u> (MediaWiki obsługuje tag <u>)
     - <a href="...">text</a> -> [url text] (jeśli URL zewnętrzny)
     - <code> / <tt> -> <code>...</code> (blok inline)
    Rekurencyjnie dla dzieci.
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
        # Jeśli to wewnętrzny link do Wiki (mały heurystyczny test: brak http lub domeny wiki), zostaw jako [[...]]
        if href.startswith('/') or href.startswith('#'):
            return f'[[{text or href}]]'
        # normalny zewnętrzny link: [URL tekst]
        if text and text != href:
            return f'[{href} {text}]'
        else:
            return f'[{href}]'
    # images inline
    if tag == 'img':
        src = node.get('src') or node.get('data-src') or ''
        alt = node.get('alt', '')
        if src:
            # MediaWiki preferuje pliki w File:, lecz do szybkiego importu zostawimy <img>
            return f'<img src="{src}" alt="{alt}">'
        return ''
    # default: łączymy dzieci
    for c in node.children:
        pieces.append(inline_text(c))
    return ''.join(pieces)

def list_to_wiki(nodes, list_type='ul', depth=0):
    """
    nodes: list of <li> Tag
    list_type: 'ul' albo 'ol'
    depth: poziom zagnieżdżenia (0 = top)
    """
    lines = []
    for li in nodes:
        # compute prefix: '*' dla ul, '#' dla ol, wielokrotnie dla depth+1
        prefix_sym = '*' if list_type == 'ul' else '#'
        prefix = prefix_sym * (depth + 1)
        # li może zawierać paragrafy lub dalsze listy; zbuduj inline tekst z jego
        line_parts = []
        for child in li.children:
            if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                continue  # zrobimy listy zagnieżdżone osobno
            line_parts.append(inline_text(child))
        line = prefix + ' ' + ''.join(line_parts).strip()
        lines.append(line)
        # sprawdź zagnieżdżone listy bezpośrednio pod li
        for child in li.children:
            if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                lines.extend(list_to_wiki(child.find_all('li', recursive=False),
                                          list_type=('ul' if child.name == 'ul' else 'ol'),
                                          depth=depth+1))
    return lines

def element_to_wiki(elem) -> list:
    """
    Konwertuje bezpośrednie elementy z <body> na listę linii wikikodu.
    Obsługiwane: h1..h6, p, pre, ul, ol, img, blockquote, hr, table (prosto)
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
        # mapujemy: h1 -> =title=, h2 -> == ..., h3 -> === ...
        level = int(name[1])
        # MediaWiki: '='..'=' ; typowo pierwszy poziom =Title= (rzadziej), ale zostawimy tak:
        eqs = '=' * level
        inner = ''.join(inline_text(c) for c in elem.children).strip()
        lines.append(f'{eqs} {inner} {eqs}')
        return lines
    if name == 'p':
        txt = ''.join(inline_text(c) for c in elem.children).strip()
        if txt == '':
            # pusty paragraf -> pusty wiersz
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
        # zagnieżdżone listy
        for child in elem.children:
            if isinstance(child, Tag) and child.name in ('ul','ol'):
                lines.extend(element_to_wiki(child))
        return lines
    if name == 'pre':
        # zachowujemy blok pre jako <pre>...</pre>
        content = ''.join(str(c) for c in elem.contents)
        lines.append('<pre>')
        lines.append(content.rstrip('\n'))
        lines.append('</pre>')
        return lines
    if name == 'blockquote':
        # prosty blockquote -> zaczynamy od >
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
        # prosta konwersja tabeli do wikitable
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

    # domyślnie: dla innych tagów zrób rekurencję po dzieciach
    child_text = []
    for child in elem.children:
        # jeśli child to blok (p, ul, h2 itd.) — użyj funkcji element_to_wiki
        if isinstance(child, Tag) and child.name in ('p','h1','h2','h3','h4','h5','h6','ul','ol','pre','table','blockquote','hr','img'):
            lines.extend(element_to_wiki(child))
        else:
            text = inline_text(child)
            if text.strip():
                child_text.append(text)
    if child_text:
        # połącz i dodaj jako akapit
        joined = ''.join(child_text).strip()
        lines.append(joined)
    return lines

def html_to_wiki(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    # Google export HTML zwykle zawiera <body> z zawartością; znajdź główny kontener
    body = soup.body or soup
    output_lines = []
    # wiele dokumentów google ma kontener <div id="contents"> albo .kix...
    # iterujemy po bezpośrednich dzieciach body, aby zachować kolejność bloków
    for child in body.children:
        # ignorujemy puste navigable strings będące tylko whitespace
        if isinstance(child, NavigableString) and not child.strip():
            continue
        block_lines = element_to_wiki(child)
        if block_lines:
            output_lines.extend(block_lines)
            # dodajemy pusty wiersz po bloku (czytelność)
            output_lines.append('')
    # usuń nadmiarowe puste linie (maksymalnie dwie z rzędu)
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
    # wypisujemy na stdout; użytkownik może przekierować do pliku
    print(wiki)

if __name__ == '__main__':
    main()
