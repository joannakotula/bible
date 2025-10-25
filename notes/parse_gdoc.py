#!/usr/bin/env python3
"""
parse_gdoc.py

Fetches a public Google Doc and parses sections:
 - H1 "Sources"   -> list of Source(title, url, description, quotes: List[Quote])
 - H1 "Summary" -> list of strings
 - H1 "Mentions" -> list of BibleVerse(verse, content)

Usage:
    python parse_gdoc.py "https://docs.google.com/document/d/<ID>/edit" [--output json] [--out-file wynik.json]

Requirements:
    pip install requests beautifulsoup4

Note:
- a multi-line source description is merged into one string, lines joined with a space.
- mentions may span multiple lines; individual mentions should be separated by a blank line.
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
    Returns a list of text lines (without empty ones) from a list of Tag/NavigableString,
    preserving the order.
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
        # Split paragraphs and br into lines
        if n.name in ('p','div'):
            txt = n.get_text(separator='\n').strip()
            if txt:
                for l in txt.splitlines():
                    ll = l.strip()
                    lines.append(ll)
            else:
                lines.append("")
            continue
        # headings, li, pre, etc.
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
    # find the h1 element (or an element with a similar heading) with matching text
    for tag in soup.find_all(re.compile('^h[1-6]$')):
        if tag.get_text(strip=True).strip().lower() == title_norm:
            return tag
    # sometimes Google uses <p class="..."> as headings; try a simpler match
    for tag in soup.find_all():
        if tag.name.startswith('h') and tag.get_text(strip=True).strip().lower() == title_norm:
            return tag
    return None

def collect_until_next_h1(start_tag: Tag):
    """
    Collect successive siblings from start_tag.next_sibling up to the next h1
    (or the end of the document). Return the list of nodes.
    """
    nodes = []
    for sib in start_tag.next_siblings:
        if isinstance(sib, Tag) and re.match(r'^h[1-6]$', sib.name, re.I):
            # stop at the next level-1 heading (or any h?), but prefer h1
            # stop at every h1; if it is a lower-level heading, also consider it (but do not stop)
            if sib.name.lower() == 'h1':
                return nodes
            # otherwise append it (e.g. h2 inside the Sources section)
        nodes.append(sib)
    return nodes

def is_separator(line: str):
    stripped = line.strip()
    return stripped.startswith('--') or stripped.startswith('–')

def parse_sources_section(nodes) -> List[Source]:
    """
    nodes: list of elements belonging to the Sources section (between one H1 and the next H1)
    Logic:
      - each <h2> (or level-2 heading) denotes a new Source (title)
      - the following lines are: URL (heuristically recognized), description (up to '--'), then quotes separated by '--'
    """
    sources = []
    # find all h2 elements in nodes (in order)
    # if there is no h2, try to interpret the whole block as a single source
    h2s = [n for n in nodes if isinstance(n, Tag) and re.match(r'^h[2]$', n.name, re.I)]
    if not h2s:
        # fallback: try to split paragraph blocks as successive sources — but simpler: return an empty list
        return sources

    for h2 in h2s:
        title = h2.get_text(strip=True)
        # collect the nodes belonging to this source: from h2.next_siblings up to the next h2
        block = []
        for sib in h2.next_siblings:
            if isinstance(sib, Tag) and re.match(r'^h[2]$', sib.name, re.I):
                break
            block.append(sib)
        lines = text_lines_from_nodes(block)
        # Heuristic: find the URL (a line starting with http/https/www)
        url = None
        url_idx = None
        for i, ln in enumerate(lines):
            if re.match(r'^(https?://|www\.)', ln.strip(), re.I):
                url = ln.strip()
                url_idx = i
                break
        # if the URL should be in the first position as assumed — but if not found, set None
        # description: lines from (url_idx+1) up to the first '--' (exclusive)
        description_lines = []
        quotes = []
        # find the index of the first '--' separator
        sep_indices = [i for i, ln in enumerate(lines) if is_separator(ln)]
        first_sep = sep_indices[0] if sep_indices else None

        if url_idx is None:
            # if no URL was found, treat the first line as a URL only if it looks like a link; we have already checked
            # brak URL — description do pierws_sep
            desc_start = 0
        else:
            desc_start = url_idx + 1

        if first_sep is None:
            # no separators: all lines from desc_start to the end as description
            description_lines = lines[desc_start:]
        else:
            description_lines = lines[desc_start:first_sep]
            # quotes: split the rest into blocks separated by '--'
            # create a list of blocks between separators
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
        # join the description lines according to rule B: join with spaces
        description = ' '.join(l for l in (description_lines or [])).strip() or None
        quote_objs = [Quote(text=q, source=title) for q in quotes if q.strip()]
        sources.append(Source(title=title, url=url, description=description, quotes=quote_objs))
    return sources

def parse_summary_section(nodes) -> List[str]:
    lines = text_lines_from_nodes(nodes)
    items = []
    for ln in lines:
        # remove bullets such as •, -, *, numbering "1." etc.
        cleaned = re.sub(r'^[\u2022\-\*\s\d\.\)]+', '', ln).strip()
        if cleaned:
            items.append(cleaned)
    return items

def parse_mentions_section(nodes) -> List[BibleVerse]:
    """
    Mentions:
      - may span multiple lines
      - separate mentions are delimited by a blank line (i.e. a block of text)
      - each block: try to split into 'verse' and 'content' at the first ':'.
        if there is no ':', take the first token (up to the first '- ' or the first digits) — a simple heuristic:
        - if there is no ':', take the first word/list up to the first occurrence of two spaces or a dash — as a fallback, put the whole block as content and verse="".
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
            # fallback: try to match a pattern like "Ps 23, 1-4" at the beginning
            m = re.match(r'^([A-Za-ząćęłńóśżźĄĆĘŁŃÓŚŻŹ0-9\.,\s]+)\s+-\s+(.*)$', joined)
            if m:
                verse = m.group(1).strip()
                content = m.group(2).strip()
            else:
                # finally: try to split after the first few tokens if it looks like a ref
                m2 = re.match(r'^([A-Za-z]{1,4}\s*\d{1,3}[,\d\-]*)\s+(.*)$', joined)
                if m2:
                    verse = m2.group(1).strip()
                    content = m2.group(2).strip()
                else:
                    # could not extract it — set verse to empty, content to the whole block
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
    # Convert the dataclass to dictionary structures for JSON
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
        # print a friendly representation
        from pprint import pprint
        printable = {
            "sources": [asdict(s) for s in sources],
            "summary": summary,
            "mentions": [asdict(m) for m in mentions],
        }
        pprint(printable, width=140, compact=False)

if __name__ == '__main__':
    main()
