import re
import functools
import operator

SUNDAY = 'sunday'
SPECIALDAY = 'special'
WEEKDAY = 'weekday'

SUNDAY_YEARS = ['A','B','C']
WEEKDAY_YEARS = ['I', 'II']

WEEKDAY_DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"]
WEEKDAY_DAYS_EXCEPTIONS = ['wielki poniedziałek', 'wielki wtorek', 'wielka środa', 'wielki czwartek', 'wielki piątek', 'wielka sobota', 'poniedziałek wielkanocny']


FIRST_VERSE = "__FIRST__"
LAST_VERSE = "__LAST__"

BOOK_CHAPTER_PATTERN = "([\d]? ?\w+) (\d+.*)"


def contains_any(haystack: str, needles: list[str]):
    return any(v in haystack for v in needles)

class ReadStats(object):
    def __init__(self, verses_count: int = 0, data = None) -> None:
        self.data: dict[str, int] = data if data else {}
        self.verses_count = verses_count

    def get_percent(self, key: str):
        return self.data[key]/self.verses_count * 100

    def contains(self, key: str) -> bool:
        return (key in self.data and self.data[key] > 0)
    
    def filter_out_existing(self, keys: list[str]) -> list[str]:
        return [key for key in keys if not self.contains(key)]
    
    def increment(self, key):
        if not key in self.data:
            self.data[key] = 1
        else:
            self.data[key]+=1
    
    def add(self, other):
       self.verses_count += other.verses_count
       for key, value in other.data.items():
            if key in self.data:
               self.data[key] += value
            else:
                self.data[key] = value

    def to_dict(self):
        if self.is_empty():
            return {}
        else:
            return {
                'verses_count': self.verses_count,
                'stats': self.data
            }

    def is_empty(self):
        return self.verses_count == 0

    @staticmethod
    def from_dict(data: dict):
        return ReadStats(data['verses_count'], data['stats'])
    

class Fragment(object):

    def __init__(self, book_abbr: str, chapter: int, first_verse: str, last_verse: str) -> None:
        self.book_abbr = book_abbr
        self.chapter = chapter
        self.first_verse = str(first_verse)
        self.last_verse = str(last_verse)

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
        return [Fragment(book_abbr=book_abbr, 
                         chapter=chapter, 
                         first_verse=str(t[0]), 
                         last_verse=str(t[1]) if len(t) > 1 else str(t[0])) 
                    for t in verses]

    @staticmethod
    def parse(verses_str: str) -> list:
        def get_verses(rest: str) -> list[tuple]:
            found_groups=re.findall("(\d\w*)(-(\d\w*))?",rest)
            return [(g[0], g[2] if g[2] else g[0]) for g in found_groups]
        def get_chapter_fragments(book: str, one_chapter_content: str):
            match_chapter=re.match("(\d+)[^,]*, ?([^\(]*)", one_chapter_content)
            if match_chapter:
                return Fragment.create(book, int(match_chapter.group(1)), get_verses(match_chapter.group(2)))
            raise ValueError(f"Unable to parse {verses_str}: '{one_chapter_content}' doesn't match chapter regex")

        # clear and normalize
        verses_str = re.sub(r'\([^)]*\)', '', verses_str).strip()
        verses_str = verses_str.replace("–", "-") 

        match_book_chapter=re.match(BOOK_CHAPTER_PATTERN, verses_str)
        if not match_book_chapter:
            raise ValueError(f"Unable to determine book/chapter from '{verses_str}'")
        
        book, rest = match_book_chapter.groups()
        if ';' in rest:
            result = []
            for part in rest.split(';'):
                next_part=part.strip()
                if not re.match(BOOK_CHAPTER_PATTERN, next_part):
                    next_part=f"{book} {next_part}"
                result += Fragment.parse(next_part)
            return result
        
        cross_chapter_match = re.match(r"(\d+),\s*(\w+) *- *(\d+),\s*(\w+)", rest.strip())
        if cross_chapter_match:
            chapter1, verse1, chapter2, verse2 = cross_chapter_match.groups()
            return [
                Fragment(book, int(chapter1), verse1, LAST_VERSE),
                Fragment(book, int(chapter2), FIRST_VERSE, verse2)
            ]
        
        return [fragment 
                for fragment in get_chapter_fragments(book, rest.strip())
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
        lower_name = name.lower()

        # Szukamy roku liturgicznego: rok A, B, C, I, II
        match_year = re.search(r'rok\s+(A|B|C|II|I)', name, re.IGNORECASE)
        year = match_year.group(1) if match_year else None

        def get_date_type(year: str):
            if year in SUNDAY_YEARS:
                return SUNDAY
            elif year in WEEKDAY_YEARS:
                return WEEKDAY
            elif contains_any(lower_name, WEEKDAY_DAYS) \
                and not contains_any(lower_name, WEEKDAY_DAYS_EXCEPTIONS):
                return WEEKDAY
            else:
                return SPECIALDAY

        return LiturgicalDay(full_name=name, day_type=get_date_type(year), year=year)

class Reading(object):
    def __init__(self, data: dict) -> None:
        self.day = LiturgicalDay.parse(data["name"])
        self.fragments:dict[str,list[Fragment]] = {k: Fragment.parse(v) for k, v in data['readings'].items()}
        self.periods = data.get('periods', [])

    def __eq__(self, other):
        if not isinstance(other, Reading):
            return NotImplemented
        return (
            self.day == other.day and
            self.fragments == other.fragments and
            self.periods == other.periods
        )

    def __repr__(self):
        return (f"Reading(day={self.day!r}, "
                f"fragments={self.fragments!r}, "
                f"periods={self.periods!r})")

class Verse(object):

    def __init__(self, book_abbr: str, chapter_no: int, verse_no: str, readings: list[str] = [], stats: ReadStats = None) -> None:
        self.book_abbr = book_abbr
        self.chapter_no = chapter_no
        self.verse_no = verse_no
        self.readings = readings
        if stats is not None:
            self.stats = stats
        else:
            self.stats = ReadStats(verses_count=1)

    def to_dict(self):
        base = {
            'number': self.verse_no
        }
        if self.readings:
            return base | {
                "readings": self.readings,
            } | self.stats.to_dict()
        else:
            return base
        
    def add_reading(self, day: str, day_keys: list[str]):
        self.readings.append(day)
        for key in self.stats.filter_out_existing(day_keys):
            self.stats.increment(key)
        
def get_clear_number(verse_number: str) -> str:
    matcher = re.search(r"(\d+)", verse_number)
    if not matcher:
        raise ValueError(f"Invalid verse number: {verse_number}")
    return matcher.group(1)

class Chapter(object):
    def __init__(self, book_abbr: str, chapter_no: int, verses_ids: list = [], verses: list[Verse] = [], stats: ReadStats = None) -> None:
        self.book_abbr = book_abbr
        self.chapter_no = chapter_no
        self.stats = stats
        if verses:
            self.verses = verses
        else:
            self.verses = [Verse(book_abbr=book_abbr, chapter_no=chapter_no, verse_no=id) for id in verses_ids]
        self.verses_idxs = {v.verse_no: idx for idx, v in enumerate(self.verses) }
        stats = stats if stats else ReadStats()

    def to_dict(self):
        return {
            "verses": [v.to_dict() for v in self.verses],
        } | self.stats.to_dict()
    
    def calculate_stats(self):
        if not self.stats.is_empty():
            raise ValueError("Stats already calculated")
        for verse in self.verses:
            self.stats.add(verse.stats)
        return self.stats
    
    def _get_verse_idx(self, verse_no):
        if verse_no == LAST_VERSE:
            return len(self.verses_idxs)
        if verse_no == FIRST_VERSE:
            return 0
        if verse_no in self.verses_idxs:
            return self.verses_idxs[verse_no]
        cleared_no = get_clear_number(verse_no)
        if cleared_no in self.verses_idxs:
            return self.verses_idxs[cleared_no]
        raise ValueError(f"Cannot find verse: {verse_no} ({cleared_no}) in {self.book_abbr} {self.chapter_no}")
    
    def add_fragment(self, day_name: str, day_keys: list[str], fragment: Fragment) -> None:
        start_verse_idx = self._get_verse_idx(fragment.first_verse)
        end_verse_idx = self._get_verse_idx(fragment.last_verse)
        print(f"--- adding for {day_name}")
        for i in range(start_verse_idx, end_verse_idx+1):
            print(f"      {self.verses[i].verse_no} ({i})")
            self.verses[i].add_reading(day_name, day_keys)


    @staticmethod
    def fromDict(book_abbr: str, chapter_no: int, data: dict):
        stats = ReadStats(data.get("verses_count", 0), data=data.get("stats", {}))
        return Chapter(book_abbr=book_abbr, 
                       chapter_no=chapter_no, 
                       verses=[Verse(
                           book_abbr=book_abbr, 
                           chapter_no=chapter_no,
                           verse_no=verse_data['number'],
                           readings=verse_data['readings'] if verse_data and 'readings' in verse_data else [],
                           stats=ReadStats.from_dict(verse_data) if verse_data and 'stats' in verse_data else None
                          )
                        for verse_data in data['verses']],
                        stats=stats)
    


class Book(object):
    def __init__(self, name: str, abbr: str, chapters: dict[int, Chapter] = {}, stats: ReadStats = None) -> None:
        self.name = name
        self.abbr = abbr
        self.chapters = chapters
        self.stats = stats if stats else ReadStats()

    def add_chapter(self, chapter_no: int, verses_ids: list):
        self.chapters[chapter_no] = Chapter(book_abbr=self.abbr, chapter_no=chapter_no, verses_ids=verses_ids)
    
    def to_dict(self):
        return {
            "full_name": self.name,
            "chapters": {ch_no: ch.to_dict() for ch_no, ch in self.chapters.items()}
        } | self.stats.to_dict()
    
    def calculate_stats(self):
        if not self.stats.is_empty():
            raise ValueError("Stats already calculated")
        for chapter in self.chapters.values():
            self.stats.add(chapter.calculate_stats())
        return self.stats
    
    def add_fragment(self, day_name: str, day_keys: list[str], fragment: Fragment) -> None:
        print(f"----------- Adding {fragment} as {day_keys}")
        self.chapters[fragment.chapter].add_fragment(day_name, day_keys, fragment)

    @staticmethod
    def fromDict(abbr: str, data: dict):
        stats = ReadStats(data.get("verses_count", 0), data=data.get("stats", {}))
        return Book(data['full_name'], abbr, 
                    {chapter_no: Chapter.fromDict(abbr, chapter_no, chapter_data) 
                     for chapter_no, chapter_data in data['chapters'].items()
                     }, stats=stats)

def add_readings(books: dict[str, Book], readings: list[Reading]) -> ReadStats:
    for reading in readings:
        day = reading.day
        keys = ['all', day.day_type]
        if day.year:
            keys.append(day.year)
        all_fragments:list[Fragment] = functools.reduce(operator.iconcat, reading.fragments.values(), [])
        for fragment in all_fragments:
            book = books[fragment.book_abbr]
            book.add_fragment(
                day_name=day.full_name,
                day_keys=keys,
                fragment=fragment
            )
    summary = ReadStats()
    for book in books.values():
        summary.add(book.calculate_stats())
    return summary