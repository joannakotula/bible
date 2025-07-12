from enum import Enum
import re

SUNDAY = 'sunday'
SPECIALDAY = 'special'
WEEKDAY = 'weekday'

SUNDAY_YEARS = ['A','B','C']
WEEKDAY_YEARS = ['I', 'II']

class Fragment(object):

    def __init__(self, book_abbr: str, chapter: int, first_verse: str, last_verse: str) -> None:
        self.book_abbr = book_abbr
        self.chapter = chapter
        self.first_verse = first_verse
        self.last_verse = last_verse

    def __eq__(self, other: object) -> bool:
        return (self.book_abbr == other.book_abbr 
                and self.chapter == other.chapter and
                self.first_verse == other.first_verse and
                self.last_verse == other.last_verse
                )
    
    def __repr__(self) -> str:
        return f"{self.book_abbr} {self.chapter}: ({self.first_verse}-{self.last_verse})"
    
    @staticmethod
    def create(book_abbr: str, chapter: int, verses: list[tuple]) -> list:
        return [Fragment(book_abbr=book_abbr, chapter=chapter, first_verse=t[0], last_verse=t[1]) for t in verses]

    @staticmethod
    def parse(verses_str: str) -> list:
        def get_verses(rest: str) -> list[tuple]:
            found_groups=re.findall("(\d\w*)(-(\d\w*))?",rest)
            return [(g[0], g[2] if g[2] else g[0]) for g in found_groups]
        def get_chapter_fragments(book: str, one_chapter_content: str):
            match_chapter=re.match("(\d+)[^,]*, ([^\(]*)", one_chapter_content)
            return Fragment.create(book, int(match_chapter.group(1)), get_verses(match_chapter.group(2)))

        verses_str = verses_str.strip()
        match_book_chapter=re.match("([\d]? ?\w+) (\d+.*)", verses_str)
        if not match_book_chapter:
            raise ValueError(f"Unable to determine book/chapter from '{verses_str}'")
        book = match_book_chapter.group(1)
        return [fragment 
                for one_chapter_content in match_book_chapter.group(2).split(';')
                for fragment in get_chapter_fragments(book, one_chapter_content.strip())
                ]

class LiturgicalDay(object):
    def __init__(self, full_name: str, day_type: str, year: str = None):
        self.full_name = full_name
        self.day_type = day_type
        self.year = year

    def __eq__(self, other):
        return (self.full_name == other.full_name and
                self.day_type == other.day_type and
                self.year == other.year)

    def __repr__(self):
        return f"LiturgicalDay(full_name='{self.full_name}', type='{self.day_type}', year='{self.year}')"


    @staticmethod
    def parse(name: str):
        name = name.strip()

        # Look for the liturgical year: year A, B, C, I, II
        match_year = re.search(r'rok\s+(A|B|C|II|I)', name, re.IGNORECASE)
        year = match_year.group(1) if match_year else None

        def get_date_type(year: str):
            if year in SUNDAY_YEARS:
                return SUNDAY
            elif year in WEEKDAY_YEARS:
                return WEEKDAY
            else:
                return SPECIALDAY

        return LiturgicalDay(full_name=name, day_type=get_date_type(year), year=year)




class Verse(object):

    def __init__(self, book_abbr: str, chapter_no: int, verse_no: str) -> None:
        self.book_abbr = book_abbr
        self.chapter_no = chapter_no
        self.verse_no = verse_no
        self.readings = []

    def to_dict(self):
        if self.readings:
            return {
                "readings": self.readings
            }
        else:
            return {}

class Chapter(object):
    def __init__(self, book_abbr: str, chapter_no: int, verses: list) -> None:
        self.book_abbr = book_abbr
        self.chapter_no = chapter_no
        self.verses = [Verse(book_abbr=book_abbr, chapter_no=chapter_no, verse_no=id) for id in verses]

    def to_dict(self):
        return {
            "verses": {v.verse_no: v.to_dict() for v in self.verses}
        }

class Book(object):
    def __init__(self, name: str, abbr: str) -> None:
        self.name = name
        self.abbr = abbr
        self.chapters: list[Chapter] = []

    def add_chapter(self, chapter_no: int, verses: list):
        self.chapters.append(Chapter(book_abbr=self.abbr, chapter_no=chapter_no, verses=verses))
    
    def to_dict(self):
        return {
            "chapters": {ch.chapter_no: ch.to_dict() for ch in self.chapters}
        }
