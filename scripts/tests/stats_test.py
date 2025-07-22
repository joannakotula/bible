import unittest
from parameterized import parameterized
import yaml
from lib.model import Book, Verse, Reading, ReadStats, SUNDAY, SPECIALDAY, WEEKDAY, add_readings

sample_book_yaml="""
Book:
  full_name: Full Book
  chapters:
    1:
      verses:
        - number: '1'
        - number: '2'
        - number: '3'
        - number: '4a'
        - number: '4b'
        - number: '4c'
        - number: '5'
    2:
      verses:
        - number: '1'
        - number: '2'
        - number: '3'
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
        - number: '1'
          readings:
            - I Niedziela Wielkiego Postu rok B
            - II Niedziela Wielkiego Postu rok A
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            A: 1
            B: 1
        - number: '2'
          readings:
            - I Niedziela Wielkiego Postu rok B
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            B: 1
        - number: '3'
        - number: '4a'
        - number: '4b'
        - number: '4c'
          readings:
            - I Niedziela Wielkiego Postu rok A
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            A: 1
        - number: '5'
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
        - number: '1'
          readings:
            - I Niedziela Wielkiego Postu rok C
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            C: 1
        - number: '2'
          readings:
            - II Niedziela Wielkiego Postu rok C
          verses_count: 1
          stats:
            all: 1
            sunday: 1
            C: 1
        - number: '3'
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

sample_readings_yaml="""
- name: I Niedziela Wielkiego Postu rok A
  readings:
    first: Book 2, 1b-2
- name: Wtorek I tygodnia Wielkiego Postu
  readings:
    first: Book 1, 4c-5
- name: Uroczystość Wniebowstąpienia Pańskiego rok C
  readings:
    first: Book 2, 3
- name: Poniedziałek, I tydzień zwykły, rok I
  readings:
    first: Book 1, 1-4a
- name: Piątek, I tydzień zwykły, rok II
  readings:
    first: Book 2, 1
- name: Sobota, I tydzień zwykły, rok II
  readings:
    first: Book 1, 2-3
- name: II Niedziela zwykła, rok B
  readings:
    first: Book 2, 1
"""

first_chapter_expected_stats_yaml = """
verses_count: 7
stats:
  all: 6
  weekday: 6
  I: 4
  II: 2
"""

second_chapter_expected_stats_yaml = """
verses_count: 3
stats:
  all: 3
  sunday: 3
  weekday: 1
  A: 2
  B: 1
  C: 1
  II: 1
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
    #  print('--')
    #  print(yaml.dump(actual_data, sort_keys=False))
    #  print('--')
     self.assertDictEqual(actual_data, data)

  def test_verse_add_fragment(self):
     verse = Verse(book_abbr="a", chapter_no="1", verse_no="2")
     self.assertDictEqual(verse.stats.data, {})
    #  Added first reading
     verse.add_reading(day="Some day", day_keys=["a", "b", "all"])
     self.assertDictEqual(verse.stats.data, {'a': 1,'b': 1, 'all': 1})

    #  Added second reading
     verse.add_reading(day="Other day", day_keys=["b", "c", "all"])
     self.assertDictEqual(verse.stats.data, {'a': 1, 'b': 1, 'c': 1, 'all': 1})

  def test_add_stats(self):
    #  given
     data1 = {'a': 1, 'b': 1, 'all': 1}
     data2 = {'b': 1, 'c': 1, 'all': 1}
     expected_sum = {'a': 1, 'b': 2, 'c': 1, 'all': 2}

     stat1 = ReadStats(1, data1)
     stat2 = ReadStats(1, data2)

    # when
     sum = ReadStats()
     for s in [stat1, stat2]:
        sum.add(s)

    # then
     self.assertDictEqual(sum.data, expected_sum)

  def test_generate_stats(self):
    #  given
    book_data = yaml.safe_load(sample_book_yaml)
    book = Book.fromDict("Book", book_data["Book"])
    readings = [Reading(one_reading) for one_reading in yaml.safe_load(sample_readings_yaml)]
    first_chapter_expected_stats = ReadStats.from_dict(yaml.safe_load(first_chapter_expected_stats_yaml))
    second_chapter_expected_stats = ReadStats.from_dict(yaml.safe_load(second_chapter_expected_stats_yaml))

    #  when
    stats = add_readings({'Book': book}, readings)
    print('------')
    print(yaml.safe_dump(book.to_dict(), sort_keys=False, allow_unicode=True, ))
    print('--')
    print(yaml.dump(stats.to_dict(), sort_keys=False))
    print('------')
    

    # then
    self.assertEqual(book.chapters[1].stats.verses_count, first_chapter_expected_stats.verses_count)
    self.assertEqual(book.chapters[2].stats.verses_count, second_chapter_expected_stats.verses_count)
    self.assertDictEqual(book.chapters[1].stats.data, first_chapter_expected_stats.data)
    self.assertDictEqual(book.chapters[2].stats.data, second_chapter_expected_stats.data)
    self.assertDictEqual(book.stats.data, {
       'all': 9,
       SUNDAY: 3,
       WEEKDAY: 7,
       "A": 2,
       "B": 1,
       "C": 1,
       "I": 4,
       "II": 3
    })


if __name__ == "__main__":
    unittest.main()