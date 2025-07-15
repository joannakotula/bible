import unittest
import yaml
from lib.model import Book

sample_book_yaml="""
Book:
  full_name: Full Book
  chapters:
    1:
      verses:
        '1': {}
        '2': {}
        '3': {}
        '4a': {}
        '4b': {}
        '4c': {}
        '5': {}
    2:
      verses:
        '1': {}
        '2': {}
        '3': {}
"""

class TestStatsGenerator(unittest.TestCase):

  def test_serialize_deserialize_book(self):
     self.maxDiff = 1000
     data = yaml.safe_load(sample_book_yaml)
     book = Book.fromDict("Book", data["Book"])
     actual_data = {book.abbr: book.to_dict()}
     print('--')
     print(yaml.dump(actual_data, sort_keys=False))
     print('--')
     self.assertDictEqual(actual_data, data)


if __name__ == "__main__":
    unittest.main()