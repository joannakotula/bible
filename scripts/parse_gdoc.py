#!/usr/bin/env python3
"""
parse_gdoc.py

Fetches a Google Doc or Google Drive folder and parses sections:
 - H1 "Sources"   -> list of Source(title, url, description, quotes: List[Quote])
 - H1 "Summary" -> list of strings
 - H1 "Mentions" -> list of BibleVerse(verse, content)

Usage:
    python parse_gdoc.py "https://docs.google.com/document/d/<ID>/edit" [--out FILE|DIR]
    python parse_gdoc.py "https://drive.google.com/drive/folders/<ID>" --out DIR --api-key KEY

Google Drive folders require an API key for public folders or an OAuth access token
for private folders. These can also be provided through GOOGLE_API_KEY and
GOOGLE_ACCESS_TOKEN.

Requirements:
    pip install requests beautifulsoup4

Note:
- a multi-line source description is merged into one string, lines joined with a space.
- mentions may span multiple lines; individual mentions should be separated by a blank line.
"""
from dataclasses import dataclass, asdict, is_dataclass
import sys
import re
from typing import Any, Callable, Iterable, Iterator, List, Optional, Sequence
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PageElement
import argparse
import os
import unicodedata
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path

from lib.books import abbr_2_book_data
from lib.google_docs import GoogleApiError, GoogleDriveApi
from lib.model import Fragment, BOOK_CHAPTER_PATTERN

SUMMARY_TITLE = 'Streszczenie'
SOURCES_TITLE = 'Źródła'
MENTIONS_TITLE = 'Wzmianki'
COMMENTS_TITLE = 'Komentarze'

TYPE_ARTICLE="artykuł"
TYPE_MOVIE="film"
# other types: playlist channel book podcast


class WikiElement(ABC):
    @abstractmethod
    def to_wikicode(self) -> str:
        pass

@dataclass
class Source(WikiElement):
    title: str
    url: str
    description: Optional[str]
    language: str
    type: str


    def to_wikicode(self) -> str:
        return f"""{{{{Source
|typ={self.type}
|url={self.url}
|nazwa={self.title}
|opis={self.description}
|jezyk={self.language}
}}}}"""        

@dataclass
class Quote(WikiElement):
    text: Optional[str]
    source: Source

    def to_wikicode(self) -> str:
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

    def to_wikicode(self) -> str:
        return f"""{{{{Cytat biblijny
    |tekst={self.content}
    |werset={self.verse}
    |link_sekcji={self.internal_link}|}}}}"""
    
    @staticmethod
    def create(verse: str, content: str) -> "BibleVerse":
        fragments_list:list[Fragment] = Fragment.parse(verse)
        if not fragments_list:
            raise Exception(f"Couldn't parse {verse}")
        fragment = fragments_list[0]
        
        try:
            full_book = abbr_2_book_data[fragment.book_abbr]['name'].replace('według', 'wg')
            internal_link = f"{full_book}#{fragment.book_abbr} {fragment.chapter}"
            return BibleVerse(verse=verse, content=content, internal_link=internal_link)
        except Exception as ex:
            raise Exception(f"Error while parsing {verse} - got {fragment}") from ex

    @staticmethod
    def parse(text: str) -> "BibleVerse":
        if ':' in text:
            idx = text.index(':')
            return BibleVerse.create(verse=text[:idx].strip(), content=text[idx+1:].strip())
        else:
            # fallback: try to match a pattern like "Ps 23, 1-4" at the beginning
            m = re.match(r'^([A-Za-ząćęłńóśżźĄĆĘŁŃÓŚŻŹ0-9\.,\s]+)\s+-\s+(.*)$', text)
            if m:
                return BibleVerse.create(verse = m.group(1).strip(), content = m.group(2).strip())
            else:
                # finally: try to split after the first few tokens if it looks like a ref
                m2 = re.match(r'^([A-Za-z]{1,4}\s*\d{1,3}[,\d\-]*)\s+(.*)$', text)
                if m2:
                    return BibleVerse.create(verse = m2.group(1).strip(), content = m2.group(2).strip())
                else:
                    raise Exception(f"Not a Bible verse: {text}")

@dataclass
class Section:
    name: str
    elements: Sequence[WikiElement | str]

    def to_wikicode(self) -> str:
        content = '\n'.join([el.to_wikicode() if isinstance(el, WikiElement) else str(el) for el in self.elements])
        return f"== {self.name} ==\n\n{content}"

    def to_dict(self) -> dict[str, list[Any]]:
        return {self.name: [asdict(s) if is_dataclass(s) else s for s in self.elements]}

    
class Format(Enum):
    wiki = "wiki"
    pretty = "pretty"

class SectionName(Enum):
    summary = "summary"
    quotes = "quotes"
    mentions = "mentions"
    sources = "sources"

_SLUG_TRANSLATION = str.maketrans({
    'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
    'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z',
})


def slugify(value: str) -> str:
    value = value.translate(_SLUG_TRANSLATION)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value)
    value = re.sub(r'[_\s-]+', '-', value).strip('-').lower()
    return value or 'document'


def text_lines_from_nodes(nodes: Iterable[PageElement]) -> list[str]:
    """
    Returns a list of text lines from a list of Tag/NavigableString,
    preserving the order.
    """
    lines: list[str] = []
    for n in nodes:
        if isinstance(n, NavigableString):
            text = str(n).strip()
            if text:
                for l in text.splitlines():
                    ll = l.strip()
                    lines.append(ll)
            # skip whitespace-only text nodes between tags (they are not blank lines)
            continue
        if not isinstance(n, Tag):
            continue
        # Split paragraphs and br into lines
        txt = n.get_text(separator='\n').strip()
        if n.name in ('p','div'):
            if txt:
                for l in txt.splitlines():
                    ll = l.strip()
                    lines.append(ll)
            else:
                lines.append("")
            continue
        if txt:
            m = re.match("h([1-6])", n.name)
            if m:
                level = int(m.group(1)) + 1
                header = '=' * level;
                lines.append(f"{header} {txt} {header}")
            else:
                for l in txt.splitlines():
                    ll = l.strip()
                    lines.append(ll)
        else:
            lines.append("")
    return lines


def lines_to_text(lines: list[str]) -> Optional[str]:
    return ' '.join(l for l in (lines or [])).strip() or None

def find_h1_by_title(soup: BeautifulSoup, title: str) -> Optional[Tag]:
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

def is_header_of_type(node: PageElement, header_name : str) -> bool:
    return (
        isinstance(node, Tag)
        and re.match(r'^h[1-6]$', node.name, re.I) is not None
        and node.name.lower() == header_name
    )

def collect_until_next_h1(start_tag: Tag) -> list[PageElement]:
    """
    Collect successive siblings from start_tag.next_sibling up to the next h1
    (or the end of the document). Return the list of nodes.
    """
    nodes: list[PageElement] = []
    for sib in start_tag.next_siblings:
        if is_header_of_type(sib, 'h1'):
            return nodes
        # otherwise append it (e.g. h2 inside the Sources section)
        nodes.append(sib)
    return nodes

def is_separator(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith('--') or stripped.startswith('–')

def parse_sources_section(nodes: Sequence[PageElement]) -> tuple[list[Source], list[Quote]]:
    """
    nodes: list of elements belonging to the Sources section (between one H1 and the next H1)
    Logic:
      - each <h2> (or level-2 heading) denotes a new Source (title)
      - the following lines are: URL (heuristically recognized), description (up to '--'), then quotes separated by '--'
    """
    next_node_idx = 0
    nodes_size = len(nodes)
    def peek() -> PageElement:
        return nodes[next_node_idx]
    
    def has_next() -> bool:
        return next_node_idx < nodes_size
    
    def next() -> PageElement:
        nonlocal next_node_idx
        idx = next_node_idx
        next_node_idx += 1
        return nodes[idx]
    
    def get_until(condition: Callable[[PageElement], bool]) -> Iterator[PageElement]:
        while has_next() and not condition(peek()):
            yield next()

    def get_until_next_source() -> Iterator[PageElement]:
        return get_until(lambda node: is_header_of_type(node, 'h2'))
        # while has_next() and not is_header_of_type(peek(), 'h2'):
        #     yield next()
    
    def get_type(url_line: str) -> str:
        if "youtube" in url_line or "youtu.be" in url_line:
            return TYPE_MOVIE
        return TYPE_ARTICLE

    sources: list[Source] = []
    quotes: list[Quote] = []

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
        
        assert url_idx is not None
        description = lines_to_text(lines[0:url_idx])
        sep_indices = [i for i, ln in enumerate(lines) if is_separator(ln)]
        match = re.match(r"^\((\w+)\)\s*(.*)", title)
        if match:
            language, title = match.groups()
        else:
            language = "pl"
        source = Source(title=title, url=url, description=description, type=get_type(url), language=language)
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

def _single_fragment(ref: str) -> Optional[Fragment]:
    try:
        fragments = Fragment.parse(ref)
    except Exception:
        return None
    if len(fragments) != 1 or fragments[0].book_abbr not in abbr_2_book_data:
        return None
    return fragments[0]


def _verse_number(value: str) -> Optional[int]:
    m = re.search(r'\d+', str(value))
    return int(m.group()) if m else None


def _merged_verse_ref(prev_ref: str, next_ref: str) -> Optional[str]:
    prev = _single_fragment(prev_ref)
    nxt = _single_fragment(next_ref)
    if not prev or not nxt:
        return None
    if prev.book_abbr != nxt.book_abbr or prev.chapter != nxt.chapter:
        return None
    prev_last = _verse_number(prev.last_verse)
    next_first = _verse_number(nxt.first_verse)
    if prev_last is None or next_first is None or next_first != prev_last + 1:
        return None
    return f"{prev.book_abbr} {prev.chapter}, {prev.first_verse}-{nxt.last_verse}"


def _join_contents(first: str, second: str) -> str:
    return ' '.join(part for part in (first.strip(), second.strip()) if part)


def _merge_verse_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    merged: list[tuple[str, str]] = []
    for ref, content in entries:
        if merged:
            prev_ref, prev_content = merged[-1]
            new_ref = _merged_verse_ref(prev_ref, ref)
            if new_ref is not None:
                merged[-1] = (new_ref, _join_contents(prev_content, content))
                continue
        merged.append((ref, content))
    return merged


def _split_verse_line(line: str) -> Optional[tuple[str, str]]:
    if ':' not in line:
        return None
    idx = line.index(':')
    ref = line[:idx].strip()
    content = line[idx + 1:].strip()
    if not ref or not re.match(BOOK_CHAPTER_PATTERN, ref):
        return None
    if _single_fragment(ref) is None:
        return None
    return ref, content


def parse_summary_section(nodes: Sequence[PageElement]) -> list[str | BibleVerse]:
    lines = text_lines_from_nodes(nodes)
    
    def parse_line(line: str) -> str | BibleVerse | None:
        if is_separator(line):
            return ""
        # remove bullets such as •, -, *, numbering "1." etc.
        cleaned = re.sub(r'^\s*([\u2022\-\*]|\d[\.\)])\s*', '', line).strip()
        if cleaned:
            if re.match(BOOK_CHAPTER_PATTERN, cleaned):
                return BibleVerse.parse(cleaned)
            return cleaned
        return None

    elements: list[str | BibleVerse] = []
    last_verse: Optional[BibleVerse] = None
    for line in lines:
        element = parse_line(line)
        if element is None:
            last_verse = None
            continue
        if isinstance(element, BibleVerse) and last_verse is not None:
            new_ref = _merged_verse_ref(last_verse.verse, element.verse)
            if new_ref is not None:
                last_verse = BibleVerse.create(new_ref, _join_contents(last_verse.content, element.content))
                elements[-1] = last_verse
                continue
        elements.append(element)
        last_verse = element if isinstance(element, BibleVerse) else None
    return elements

def parse_mentions_section(nodes: Sequence[PageElement]) -> List[BibleVerse]:
    """
    Mentions:
      - a single mention may span multiple lines
      - separate mentions are delimited by a blank line (i.e. a block of text)
      - consecutive lines may start with consecutive verses; such entries are merged
        into a single BibleVerse with a verse range (e.g. "J 2, 1" + "J 2, 2" -> "J 2, 1-2")
      - blank lines and separator lines (starting with "--" or "–") break merging
    """
    lines = text_lines_from_nodes(nodes)
    blocks: list[list[str]] = []
    cur: list[str] = []
    for ln in lines:
        if ln.strip() == '' or is_separator(ln):
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)

    verses: list[BibleVerse] = []
    for blk in blocks:
        entries: list[tuple[str, str]] = []
        current_ref: Optional[str] = None
        current_content: list[str] = []

        for line in blk:
            split = _split_verse_line(line)
            if split is not None:
                if current_ref is not None:
                    entries.append((current_ref, ' '.join(current_content).strip()))
                current_ref, content = split
                current_content = [content] if content else []
            elif current_ref is not None:
                current_content.append(line.strip())

        if current_ref is not None:
            entries.append((current_ref, ' '.join(current_content).strip()))

        if not entries:
            joined = ' '.join(l.strip() for l in blk).strip()
            if not joined:
                continue
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
            entries = [(verse, content)]

        for verse, content in _merge_verse_entries(entries):
            verses.append(BibleVerse.create(verse=verse, content=content))
    return verses

def section_nodes_between(soup: BeautifulSoup, h1_title: str) -> list[PageElement]:
    h1 = find_h1_by_title(soup, h1_title)
    if not h1:
        return []
    return collect_until_next_h1(h1)

class ArticleDataParser:
    def __init__(self, soup: BeautifulSoup) -> None:
        self.soup = soup
        self.sections: dict[SectionName, Section] = {}
    
    def get_section(self, section_name: SectionName) -> Section:
        if section_name in self.sections:
            return self.sections[section_name]
        return self.__build_section(section_name)
        
    def __build_section(self, section_name: SectionName) -> Section:
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


    

def render_document(html: str, section_names: Sequence[SectionName], output_format: Format) -> str:
    article_parser = ArticleDataParser(BeautifulSoup(html, 'html.parser'))
    sections = [
        section for section_name in section_names
        if (section := article_parser.get_section(section_name)) is not None
    ]
    if not sections:
        raise ValueError("No sections to print")

    match output_format:
        case Format.wiki:
            return "\n".join(section.to_wikicode() for section in sections)
        case Format.pretty:
            from pprint import pformat
            printable = {key: value for section in sections for key, value in section.to_dict().items()}
            return pformat(printable, width=140, compact=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse google doc and prepare wiki structure")
    parser.add_argument("gdoc_link")
    parser.add_argument("--out", "--output", "-o", type=Path, default=None)
    parser.add_argument("--api-key", default=os.environ.get("GOOGLE_API_KEY"))
    parser.add_argument("--access-token", default=os.environ.get("GOOGLE_ACCESS_TOKEN"))
    parser.add_argument("--format", "-f", type=Format, choices=list(Format), default=Format.wiki)
    parser.add_argument("--sections", type=SectionName, nargs="*",  choices=list(SectionName), default=list(SectionName))

    args = parser.parse_args()
    api = GoogleDriveApi(args.api_key, args.access_token)
    is_folder = api.is_folder_url(args.gdoc_link)

    if is_folder:
        if args.out is None or not args.out.is_dir():
            parser.error("--out must be an existing directory when gdoc_link is a Google Drive folder")
        if not args.api_key and not args.access_token:
            parser.error(
                "Google Drive folder access requires credentials. Set GOOGLE_API_KEY or --api-key "
                "for a public folder, or GOOGLE_ACCESS_TOKEN or --access-token for a private folder."
            )

    try:
        docs = api.fetch_docs_from_folder(args.gdoc_link) if is_folder else [api.fetch_doc(args.gdoc_link)]
    except GoogleApiError as e:
        print(f"Błąd: {e.user_message}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Błąd pobierania dokumentu: {e}", file=sys.stderr)
        sys.exit(2)

    if is_folder and not docs:
        parser.error("No Google Docs found in the Google Drive folder")

    for doc in docs:
        try:
            txt = render_document(doc.html, args.sections, args.format)
        except Exception as e:
            print(f"Błąd parsowania dokumentu {doc.name}: {e}", file=sys.stderr)
            sys.exit(2)

        if args.out is None or str(args.out) == '-':
            sys.stdout.write(txt)
        elif args.out.is_dir():
            output_file = args.out / f"{slugify(doc.name)}.txt"
            output_file.write_text(txt, encoding="UTF-8")
        else:
            args.out.write_text(txt, encoding="UTF-8")


if __name__ == '__main__':
    main()
