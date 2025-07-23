import yaml
from lib.model import Book
from lib.bible_deon_api import BibleDeonApi
from lib.utils import read_yaml_file

BOOKS_FILE = "data/books.yml"


def books_to_dict(books: list[Book]) -> dict[dict]:
    return {book.abbr: book.to_dict() for book in books}


books_names = read_yaml_file(BOOKS_FILE)
bible_api = BibleDeonApi()


def prepare_book(book_data: dict):
    print(f"Preparing book: {book_data}")
    book = Book(name=book_data['name'], abbr=book_data['abbr'])
    chapters_data = bible_api.get_chapters_with_verses(book.abbr)
    for chapter_no, verses in chapters_data.items():
        book.add_chapter(chapter_no=chapter_no, verses_ids=verses)
    print(yaml.dump(book.to_dict(), sort_keys=False))
    return book

def prepare_books_list(testament: str):
    return [prepare_book(data) for data in books_names[testament]]

data = { name: books_to_dict(prepare_books_list(name)) for name in ["Old Testament", "New Testament"]}

with open("data/skeleton.yml", "w") as f:
    f.write(yaml.dump(data, sort_keys=False, allow_unicode=True))