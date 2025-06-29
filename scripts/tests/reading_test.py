import unittest
from parameterized import parameterized
from lib.model import Reading, SUNDAY, SPECIALDAY, WEEKDAY




class TestReadingParser(unittest.TestCase):
    @parameterized.expand([
        ["Środa I tygodnia Wielkiego Postu", 
            SPECIALDAY, None],
        ["Niedziela w oktawie Narodzenia Pańskiego - Święto Świętej Rodziny rok B", 
            SUNDAY, "B"],
        ["Środa, I tydzień zwykły, rok II", 
            WEEKDAY, "II"],
        ["17 grudnia", 
            SPECIALDAY, None],
        ["Wielki Czwartek - Msza z poświęceniem krzyżma",
            SPECIALDAY, None],
        ["Wtorek II tygodnia Adwentu",
            SPECIALDAY, None]
    ])
    def test_reading_parser(self, name, day_type, year):
        expected = Reading(full_name=name, day_type=day_type, year=year)
        self.assertEqual(Reading.parse(name), expected)


if __name__ == "__main__":
    unittest.main()