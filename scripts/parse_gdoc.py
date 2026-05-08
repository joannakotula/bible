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
from typing import List, Optional
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from urllib.parse import urlparse, parse_qs
import argparse
from enum import Enum
from abc import ABC, abstractmethod

from lib.books import abbr_2_book_data
from lib.model import Fragment, BOOK_CHAPTER_PATTERN

EXPORT_HTML_TEMPLATE = "https://docs.google.com/document/d/{doc_id}/export?format=html"

SUMMARY_TITLE = 'Streszczenie'
SOURCES_TITLE = 'Źródła'
MENTIONS_TITLE = 'Wzmianki'
COMMENTS_TITLE = 'Komentarze'

TYPE_ARTICLE="artykuł"
TYPE_MOVIE="film"
# other types: playlista kanał książka podcast


class WikiElement(ABC):
    @abstractmethod
    def to_wikicode(self):
        pass

@dataclass
class Source(WikiElement):
    title: str
    url: str
    description: str
    type: str


    def to_wikicode(self):
        return f"""{{{{Source
|typ={self.type}
|url={self.url}
|nazwa={self.title}
|opis={self.description}
}}}}"""        

@dataclass
class Quote(WikiElement):
    text: str
    source: Source

    def to_wikicode(self):
        return f"""{{{{Cytat
  |tekst={self.text}
  |link={self.source.url}
  |zrodlo={self.source.title}
}}}}"""        


@dataclass
class BibleVerse(WikiElement):
    verse: str
    content: str
    internal_link: str

    def to_wikicode(self):
        return f"""{{{{Cytat biblijny
    |tekst={self.content}
    |werset={self.verse}
    |link_sekcji={self.internal_link}|}}}}"""
    
    @staticmethod
    def create(verse: str, content: str):
        fragments_list:list[Fragment] = Fragment.parse(verse)
        if not fragments_list:
            raise Exception(f"Couldn't parse {verse}")
        fragment = fragments_list[0]
        full_book = abbr_2_book_data[fragment.book_abbr]['name'].replace('według', 'wg')
        internal_link = f"{full_book}#{fragment.book_abbr} {fragment.chapter}"
        return BibleVerse(verse=verse, content=content, internal_link=internal_link)

    @staticmethod
    def parse(text: str):
        if ':' in text:
            idx = text.index(':')
            return BibleVerse.create(verse=text[:idx].strip(), content=text[idx+1:].strip())
        else:
            # fallback: spróbuj dopasować pattern typu "Ps 23, 1-4" na początku
            m = re.match(r'^([A-Za-ząćęłńóśżźĄĆĘŁŃÓŚŻŹ0-9\.,\s]+)\s+-\s+(.*)$', text)
            if m:
                return BibleVerse.create(verse = m.group(1).strip(), content = m.group(2).strip())
            else:
                # ostatecznie: spróbuj rozdzielić po pierwszych kilku tokenach jeśli wygląda jak ref
                m2 = re.match(r'^([A-Za-z]{1,4}\s*\d{1,3}[,\d\-]*)\s+(.*)$', text)
                if m2:
                    return BibleVerse.create(verse = m2.group(1).strip(), content = m2.group(2).strip())
                else:
                    raise Exception(f"Not a Bible verse: {text}")

@dataclass
class Section:
    name: str
    elements: list

    def to_wikicode(self):
        content = '\n'.join([el.to_wikicode() if isinstance(el, WikiElement) else str(el) for el in self.elements])
        return f"== {self.name} ==\n\n{content}"

    def to_dict(self):
        return {self.name: [asdict(s) for s in self.elements]}

    
class Format(Enum):
    wiki = "wiki"
    pretty = "pretty"

class SectionName(Enum):
    summary = "summary"
    quotes = "quotes"
    mentions = "mentions"
    sources = "sources"

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
    Z listy Tag/NavigableString zwraca listę linii tekstowych,
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


def lines_to_text(lines: list[str]) -> str:
    return ' '.join(l for l in (lines or [])).strip() or None

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

def is_header_of_type(node, header_name : str) -> bool:
    return isinstance(node, Tag) and re.match(r'^h[1-6]$', node.name, re.I) and node.name.lower() == header_name

def collect_until_next_h1(start_tag: Tag):
    """
    Zbieramy kolejne rodzeństwo (siblings) od start_tag.next_sibling aż do kolejnego h1
    (lub końca dokumentu). Zwracamy listę node'ów.
    """
    nodes = []
    for sib in start_tag.next_siblings:
        if is_header_of_type(sib, 'h1'):
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
    next_node_idx = 0
    nodes_size = len(nodes)
    def peek():
        return nodes[next_node_idx]
    
    def has_next() -> bool:
        return next_node_idx < nodes_size
    
    def next():
        nonlocal next_node_idx
        idx = next_node_idx
        next_node_idx += 1
        return nodes[idx]
    
    def get_until(condition):
        while has_next() and not condition(peek()):
            yield next()

    def get_until_next_source():
        return get_until(lambda node: is_header_of_type(node, 'h2'))
        # while has_next() and not is_header_of_type(peek(), 'h2'):
        #     yield next()
    
    def get_type(url_line: str) -> str:
        if "youtube" in url_line or "youtu.be" in url_line:
            return TYPE_MOVIE
        return TYPE_ARTICLE

    sources = []
    quotes = []

    while has_next():
        get_until_next_source()
        title = next().get_text(strip=True)
        # get all non empty lines until next h2
        lines = [line for line in text_lines_from_nodes(get_until_next_source()) if line ]
        url_idx = None
        url = None
        for i, ln in enumerate(lines):
            if re.match(r'^(https?://|www\.)', ln.strip(), re.I):
                url = ln.strip()
                url_idx = i
                break
        if url is None:
            raise Exception(f"Cannot find url for {title}")
        
        description = lines_to_text(lines[0:url_idx])
        sep_indices = [i for i, ln in enumerate(lines) if is_separator(ln)]
        source = Source(title=title, url=url, description=description, type=get_type(url))
        sources.append(source)
        
        if len(sep_indices) > 0:
            prev_sep_idx = sep_indices[0]
            sep_indices.append(len(lines))
            for sep_idx in sep_indices[1:]:
                quote_lines = lines[prev_sep_idx+1:sep_idx]
                prev_sep_idx = sep_idx
                if quote_lines:
                    quotes.append(Quote(text=lines_to_text(quote_lines), source=source))
    return sources, quotes

def parse_summary_section(nodes) -> List[str]:
    lines = text_lines_from_nodes(nodes)
    
    def parse_line(line):
        # usuń punktory typu •, -, *, numeracja "1." itp.
        cleaned = re.sub(r'^[\u2022\-\*\s\d\.\)]+', '', line).strip()
        if cleaned:
            if is_separator(cleaned):
                return ""
            if re.match(BOOK_CHAPTER_PATTERN, cleaned):
                return BibleVerse.parse(cleaned)
            return cleaned
        return None

    return [element for line in lines if (element := parse_line(line)) is not None]

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
        verses.append(BibleVerse.create(verse=verse, content=content))
    return verses

def section_nodes_between(soup: BeautifulSoup, h1_title: str):
    h1 = find_h1_by_title(soup, h1_title)
    if not h1:
        return []
    return collect_until_next_h1(h1)

class ArticleDataParser:
    def __init__(self, soup: BeautifulSoup) -> None:
        self.soup = soup
        self.sections = {}
    
    def get_section(self, section_name: SectionName):
        if section_name in self.sections:
            return self.sections[section_name]
        return self.__build_section(section_name)
        
    def __build_section(self, section_name: SectionName):
        match section_name:
            case SectionName.summary:
                summary_content = parse_summary_section(section_nodes_between(self.soup, SUMMARY_TITLE))
                section = Section(SUMMARY_TITLE, summary_content)
                self.sections[section_name] = section
                return section
            case SectionName.mentions:
                mentions_content = parse_mentions_section(section_nodes_between(self.soup, MENTIONS_TITLE))
                section = Section(MENTIONS_TITLE, mentions_content)
                self.sections[section_name] = section
                return section
            case SectionName.sources | SectionName.quotes:
                sources, quotes = parse_sources_section(section_nodes_between(self.soup, SOURCES_TITLE))
                self.sections[SectionName.sources] = Section(SOURCES_TITLE, sources)
                self.sections[SectionName.quotes] = Section(COMMENTS_TITLE, quotes)
                return self.sections[section_name]


    

def main():
    parser = argparse.ArgumentParser(description="Parse google doc and prepare wiki structure")
    parser.add_argument("gdoc_link")
    parser.add_argument("--out", "--output", "-o", type=argparse.FileType("w", encoding="UTF-8"), default=sys.stdout)
    parser.add_argument("--format", "-f", type=Format, choices=list(Format), default=Format.wiki)
    parser.add_argument("--sections", type=SectionName, nargs="*",  choices=list(SectionName), default=list(SectionName))

    args = parser.parse_args()
    print(args)

    try:
        html = fetch_doc_html(args.gdoc_link)
    except Exception as e:
        print(f"Błąd pobierania dokumentu: {e}")
        sys.exit(2)

    articleParser = ArticleDataParser(BeautifulSoup(html, 'html.parser'))

    sections = [section for section_name in args.sections if (section := articleParser.get_section(section_name)) is not None]
    
    if not sections:
        print("No sections to print", file=sys.stderr)
        exit(1)
    
    match args.format:
        case Format.wiki:
            txt = "\n".join([s.to_wikicode() for s in sections])
            args.out.write(txt)
        case Format.pretty:
            from pprint import pprint
            printable = {k: v for s in sections for k, v in s.to_dict()}
            pprint(printable, width=140, compact=False, stream=args.out)


if __name__ == '__main__':
    main()
