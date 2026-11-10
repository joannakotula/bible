import functools
import operator
from lib.model import Book, Reading, add_readings
from lib.utils import read_yaml_file
from lib.data_files import READINGS_FILE, SKELETON_FILE, STATS_FILE

print("loading readings...")
readings_data = read_yaml_file(READINGS_FILE)
print("loading skeleton...")
skeleton_data = read_yaml_file(SKELETON_FILE)

print("mapping readings...")
readings = [Reading(d) for d in readings_data]

print("mapping skeleton")
bible_stats = {
  testament:  {abbr: Book.fromDict(abbr, book_data) for abbr, book_data in testament_data}
  for testament, testament_data in skeleton_data
}

all_books = bible_stats["Old Testament"] | bible_stats["New Testament"]


print(len(all_books))
# add_readings(books=)