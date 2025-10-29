from lib.utils import read_yaml_file
from lib.data_files import BOOKS_FILE

books_list_per_testament = read_yaml_file(BOOKS_FILE)


all_books_list = [book | {'testament': testament} for testament, books in books_list_per_testament.items() for book in books]

abbr_2_book_data = {book['abbr']:  book for book in all_books_list}