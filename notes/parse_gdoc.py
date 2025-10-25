#!/usr/bin/env python3
"""
parse_gdoc.py

Pobiera publiczny Google Doc i parsuje sekcje:
 - H1 "Źródła"   -> lista Source(title, url, description, quotes: List[Quote])
 - H1 "Streszczenie" -> lista stringów
 - H1 "Wzmianki" -> lista BibleVerse(verse, content)

Użycie:
    python parse_gdoc.py "https://docs.google.com/document/d/<ID>/edit" [--output json] [--out-file wynik.json]

Wymagania:
    pip install requests beautifulsoup4

Uwaga:
- wieloliniowy opis źródła jest scalany w jeden string, linie łączone spacją.
- wzmianki mogą zajmować kilka linii; poszczególne wzmianki powinny być oddzielone pustą linią.
"""
from dataclasses import dataclass, asdict
import sys
import re
import json
from typing import List, Optional
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from urllib.parse import urlparse, parse_qs

EXPORT_HTML_TEMPLATE = "https://docs.google.com/document/d/{doc_id}/export?format=html"

@dataclass
class Quote:
    text: str
    source: str

@dataclass
class Source:
    title: str
    url: Optional[str]
    description: Optional[str]
    quotes: List[Quote]

@dataclass
class BibleVerse:
    verse: str
    content: str

def extract_doc_id(url: str) -> Optional[str]:
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if m:
        return m.group(1)
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
        # fallback: try input link directly
    r = requests.get(link, timeout=15)
    r.raise_for_status()
    return r.text

def text_lines_from_nodes(nodes):
    """
    Z listy Tag/NavigableString zwraca listę linii tekstowych (bez pustych),
    zachowując kolejność.
    """
    lines = []
    for n in nodes:
        if isinstance(n, NavigableString):
            text = str(n).strip()
            if text:
                for l in text.splitlines():
                    ll = l.strip()
                    lines.append(ll)
            else:
                lines.append("")
            continue
        if not isinstance(n, Tag):
            continue
        # Rozbijamy paragrafy i br na linie
        if n.name in ('p','div'):
            txt = n.get_text(separator='\n').strip()
            if txt:
                for l in txt.splitlines():
                    ll = l.strip()
                    lines.append(ll)
            else:
                lines.append("")
            continue
        # nagłówki, li, pre, etc.
        txt = n.get_text(separator='\n').strip()
        if txt:
            for l in txt.splitlines():
                ll = l.strip()
                lines.append(ll)
            else:
                lines.append("")
    return lines

def find_h1_by_title(soup: BeautifulSoup, title: str):
    title_norm = title.strip().lower()
    # znajdź element h1 (lub element o podobnym nagłówku) z pasującym tekstem
    for tag in soup.find_all(re.compile('^h[1-6]$')):
        if tag.get_text(strip=True).strip().lower() == title_norm:
            return tag
    # czasem Google używa <p class="..."> jako nagłówków; spróbuj prostszego dopasowania
    for tag in soup.find_all():
        if tag.name.startswith('h') and tag.get_text(strip=True).strip().lower() == title_norm:
            return tag
    return None

def collect_until_next_h1(start_tag: Tag):
    """
    Zbieramy kolejne rodzeństwo (siblings) od start_tag.next_sibling aż do kolejnego h1
    (lub końca dokumentu). Zwracamy listę node'ów.
    """
    nodes = []
    for sib in start_tag.next_siblings:
        if isinstance(sib, Tag) and re.match(r'^h[1-6]$', sib.name, re.I):
            # zatrzymaj przy następnym nagłówku poziomu 1 (lub dowolnym h?), ale preferujemy h1
            # stopujemy na każdym h1; jeśli to niższy nagłówek, też bierzemy pod uwagę (ale nie przerywamy)
            if sib.name.lower() == 'h1':
                return nodes
            # inaczej dołączamy (np. h2 wewnątrz sekcji Źródła)
        nodes.append(sib)
    return nodes

def is_separator(line: str):
    stripped = line.strip()
    return stripped.startswith('--') or stripped.startswith('–')

def parse_sources_section(nodes) -> List[Source]:
    """
    nodes: lista elementów należących do sekcji Źródła (między H1 a następnym H1)
    Logika:
      - każdy <h2> (albo nagłówek poziomu 2) oznacza nowy Source (tytuł)
      - następne linie to: URL (heurystycznie rozpoznany), opis (do '--'), potem cytaty oddzielone '--'
    """
    sources = []
    # znajdź wszystkie h2 w nodes (kolejność)
    # jeśli nie ma h2, spróbuj interpretować cały blok jako pojedyncze źródło
    h2s = [n for n in nodes if isinstance(n, Tag) and re.match(r'^h[2]$', n.name, re.I)]
    if not h2s:
        # fallback: spróbkuj podzielić bloczki paragrafów jako kolejne źródła — ale prostsze: zwróć pustą listę
        return sources

    for h2 in h2s:
        title = h2.get_text(strip=True)
        # zbierz nodes należące do tego źródła: od h2.next_siblings aż do następnego h2
        block = []
        for sib in h2.next_siblings:
            if isinstance(sib, Tag) and re.match(r'^h[2]$', sib.name, re.I):
                break
            block.append(sib)
        lines = text_lines_from_nodes(block)
        # Heurystyka: znajdź URL (linia zaczynająca się od http/https/www)
        url = None
        url_idx = None
        for i, ln in enumerate(lines):
            if re.match(r'^(https?://|www\.)', ln.strip(), re.I):
                url = ln.strip()
                url_idx = i
                break
        # jeśli URL zgodnie z założeniem powinien być na pierwszej pozycji — ale jeśli nie znaleziono, ustaw None
        # description: linie od (url_idx+1) aż do pierwszego '--' (exclusive)
        description_lines = []
        quotes = []
        # znajdź indeks pierwszego separatora '--'
        sep_indices = [i for i, ln in enumerate(lines) if is_separator(ln)]
        first_sep = sep_indices[0] if sep_indices else None

        if url_idx is None:
            # jeśli nie znaleziono URL, traktujemy pierwszą linię jako URL tylko jeśli wygląda jak link; już sprawdziliśmy
            # brak URL — description do pierws_sep
            desc_start = 0
        else:
            desc_start = url_idx + 1

        if first_sep is None:
            # brak separatorów: wszystkie linie od desc_start do końca jako description
            description_lines = lines[desc_start:]
        else:
            description_lines = lines[desc_start:first_sep]
            # cytaty: podziel resztę na bloki oddzielone '--'
            # utwórz listę bloków między separatorami
            rest = lines[first_sep+1:]
            # split by '--' markers:
            cur = []
            for ln in rest:
                if is_separator(ln):
                    if cur:
                        quotes.append(' '.join(l.strip() for l in cur if l.strip()))
                        cur = []
                else:
                    cur.append(ln)
            if cur:
                quotes.append(' '.join(l.strip() for l in cur if l.strip()))
        # łączymy description linie według przyjętej reguły B: join with spaces
        description = ' '.join(l for l in (description_lines or [])).strip() or None
        quote_objs = [Quote(text=q, source=title) for q in quotes if q.strip()]
        sources.append(Source(title=title, url=url, description=description, quotes=quote_objs))
    return sources

def parse_summary_section(nodes) -> List[str]:
    lines = text_lines_from_nodes(nodes)
    items = []
    for ln in lines:
        # usuń punktory typu •, -, *, numeracja "1." itp.
        cleaned = re.sub(r'^[\u2022\-\*\s\d\.\)]+', '', ln).strip()
        if cleaned:
            items.append(cleaned)
    return items

def parse_mentions_section(nodes) -> List[BibleVerse]:
    """
    Wzmianki:
      - mogą być rozłożone na kilka linii
      - poszczególne wzmianki oddzielone są pustą linią (czyli blok tekstu)
      - każdy blok: spróbuj podzielić na 'verse' i 'content' według pierwszego ':'.
        jeśli brak ':', weź pierwszy token (do pierwszego '- ' lub do pierwszego cyfr) — jednak prosta heurystyka:
        - jeśli nie ma ':', bierzemy pierwsze słowo/listę do pierwszego wystąpienia dwóch spacji lub myślnika — jako fallback umieść cały blok jako content i verse="".
    """
    lines = text_lines_from_nodes(nodes)
    blocks = []
    cur = []
    for ln in lines:
        if ln.strip() == '':
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)

    verses = []
    for blk in blocks:
        joined = ' '.join(l.strip() for l in blk).strip()
        if not joined:
            continue
        # split at first colon ':'
        if ':' in joined:
            idx = joined.index(':')
            verse = joined[:idx].strip()
            content = joined[idx+1:].strip()
        else:
            # fallback: spróbuj dopasować pattern typu "Ps 23, 1-4" na początku
            m = re.match(r'^([A-Za-ząćęłńóśżźĄĆĘŁŃÓŚŻŹ0-9\.,\s]+)\s+-\s+(.*)$', joined)
            if m:
                verse = m.group(1).strip()
                content = m.group(2).strip()
            else:
                # ostatecznie: spróbuj rozdzielić po pierwszych kilku tokenach jeśli wygląda jak ref
                m2 = re.match(r'^([A-Za-z]{1,4}\s*\d{1,3}[,\d\-]*)\s+(.*)$', joined)
                if m2:
                    verse = m2.group(1).strip()
                    content = m2.group(2).strip()
                else:
                    # nie udało się wydzielić — ustaw verse jako empty, content cały blok
                    verse = ''
                    content = joined
        verses.append(BibleVerse(verse=verse, content=content))
    return verses

def section_nodes_between(soup: BeautifulSoup, h1_title: str):
    h1 = find_h1_by_title(soup, h1_title)
    if not h1:
        return []
    return collect_until_next_h1(h1)

def to_serializable(result):
    # Konwertujemy dataclass do struktur słownikowych dla JSON
    return {
        "sources": [asdict(s) for s in result['sources']],
        "summary": result['summary'],
        "mentions": [asdict(m) for m in result['mentions']],
    }

def main():
    if len(sys.argv) < 2:
        print("Użycie: python parse_gdoc.py <link_do_google_doc> [--output json] [--out-file filename.json]")
        sys.exit(1)
    link = sys.argv[1]
    out_json = False
    out_file = None
    if '--output' in sys.argv:
        i = sys.argv.index('--output')
        if i+1 < len(sys.argv) and sys.argv[i+1].lower() == 'json':
            out_json = True
    if '--out-file' in sys.argv:
        i = sys.argv.index('--out-file')
        if i+1 < len(sys.argv):
            out_file = sys.argv[i+1]

    try:
        html = fetch_doc_html(link)
    except Exception as e:
        print(f"Błąd pobierania dokumentu: {e}")
        sys.exit(2)

    soup = BeautifulSoup(html, 'html.parser')

    src_nodes = section_nodes_between(soup, 'Źródła')
    summary_nodes = section_nodes_between(soup, 'Streszczenie')
    mentions_nodes = section_nodes_between(soup, 'Wzmianki')

    sources = parse_sources_section(src_nodes)
    summary = parse_summary_section(summary_nodes)
    mentions = parse_mentions_section(mentions_nodes)

    result = {
        "sources": sources,
        "summary": summary,
        "mentions": mentions
    }

    if out_json or out_file:
        serial = to_serializable(result)
        json_text = json.dumps(serial, ensure_ascii=False, indent=2)
        if out_file:
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(json_text)
            print(f"Zapisano JSON do {out_file}")
        else:
            print(json_text)
    else:
        # wydrukuj przyjazną reprezentację
        from pprint import pprint
        printable = {
            "sources": [asdict(s) for s in sources],
            "summary": summary,
            "mentions": [asdict(m) for m in mentions],
        }
        pprint(printable, width=140, compact=False)

if __name__ == '__main__':
    main()
