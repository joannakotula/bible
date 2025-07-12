import unittest
import yaml
from lib.model import Reading, LiturgicalDay, Fragment, SUNDAY


reading_yaml="""
name: I Niedziela Wielkiego Postu rok A
periods: &id008
- Wielki Post
- 1 tydzień Wielkiego Postu
readings:
    second: Rz 5, 12.17-19
    gospel: Mt 4, 1-11
    first: Rdz 2, 7-9
    psalm: 'Ps 51 (50), 3-4. 5-6b. 12-13. 14 i 17 (R.: por. 3a)'
"""

class TestReadingParser(unittest.TestCase):

    def test_reading_parser(self):
        data = yaml.safe_load(reading_yaml)
        reading = Reading(data)
        self.assertEquals(reading.day, LiturgicalDay(
                full_name="I Niedziela Wielkiego Postu rok A",
                day_type=SUNDAY,
                year='A'
                ))
        expectedFragments = {
            'first' : Fragment.create(book_abbr='Rdz', chapter=2, verses=[(7, 9)]),
            'second': Fragment.create(book_abbr='Rz', chapter=5, verses=[('12',), ('17', '19')]),
            'psalm' : Fragment.create(book_abbr='Ps', chapter=51, verses=[(3, 4), (5, '6b'), (12, 13),(14,), (17,)]),
            'gospel': [Fragment(book_abbr='Mt', chapter=4, first_verse='1',last_verse='11')],

        }
        for key, value in expectedFragments.items():
            self.assertEquals(reading.fragments[key], value, key)


if __name__ == "__main__":
    unittest.main()