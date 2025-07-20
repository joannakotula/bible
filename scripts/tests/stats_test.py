import unittest
from parameterized import parameterized
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

sample_book_with_some_stats_yaml="""
Book:
  full_name: Full Book
  verses_count: 10
  stats:
    all: 7
    sunday: 7
    A: 3
    B: 2
    C: 3
  chapters:
    1:
      verses:
        '1':
          readings:
            - I Niedziela Wielkiego Postu rok B
            - II Niedziela Wielkiego Postu rok A
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            A: 1
            B: 1
        '2':
          readings:
            - I Niedziela Wielkiego Postu rok B
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            B: 1
        '3': {}
        '4a': {}
        '4b': {}
        '4c':
          readings:
            - I Niedziela Wielkiego Postu rok A
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            A: 1
        '5':
          readings:
            - I Niedziela Wielkiego Postu rok A
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            A: 1
      verses_count: 7
      stats:
        all: 4
        sunday: 4
        A: 3
        B: 2
    2:
      verses:
        '1':
          readings:
            - I Niedziela Wielkiego Postu rok C
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            C: 1
        '2':
          readings:
            - II Niedziela Wielkiego Postu rok C
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            C: 1
        '3':
          readings:
            - III Niedziela Wielkiego Postu rok C
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            C: 1
      verses_count: 3
      stats:
        all: 3
        sunday: 3
        C: 3
"""


class TestStatsGenerator(unittest.TestCase):

  @parameterized.expand([
     ("sample book", sample_book_yaml),
     ("sample book with stats", sample_book_with_some_stats_yaml)
  ])
  def test_serialize_deserialize_book(self, name, book_yaml):
     self.maxDiff = 1000
     data = yaml.safe_load(book_yaml)
     book = Book.fromDict("Book", data["Book"])
     actual_data = {book.abbr: book.to_dict()}
     print('--')
     print(yaml.dump(actual_data, sort_keys=False))
     print('--')
     self.assertDictEqual(actual_data, data)


if __name__ == "__main__":
    unittest.main()