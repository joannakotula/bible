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
