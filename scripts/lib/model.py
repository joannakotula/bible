from enum import Enum
import re

SUNDAY = 'sunday'
SPECIALDAY = 'special'
WEEKDAY = 'weekday'

SUNDAY_YEARS = ['A','B','C']
WEEKDAY_YEARS = ['I', 'II']

class Reading(object):
    def __init__(self, full_name: str, day_type: str, year: str = None):
        self.full_name = full_name
        self.day_type = day_type
        self.year = year

    def __eq__(self, other):
        return (self.full_name == other.full_name and
                self.day_type == other.day_type and
                self.year == other.year)

    def __repr__(self):
        return f"Reading(full_name='{self.full_name}', type='{self.day_type}', year='{self.year}')"


    @staticmethod
    def parse(name: str):
        name = name.strip()

        # Szukamy roku liturgicznego: rok A, B, C, I, II
        match_year = re.search(r'rok\s+(A|B|C|II|I)', name, re.IGNORECASE)
        year = match_year.group(1) if match_year else None

        def get_date_type(year: str):
            if year in SUNDAY_YEARS:
                return SUNDAY
            elif year in WEEKDAY_YEARS:
                return WEEKDAY
            else:
                return SPECIALDAY

        return Reading(full_name=name, day_type=get_date_type(year), year=year)




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
