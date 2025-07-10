import unittest
from parameterized import parameterized
from lib.model import LiturgicalDay, SUNDAY, SPECIALDAY, WEEKDAY


class TestLiturgicalDayParser(unittest.TestCase):
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
    def test_liturgical_day_parser(self, name, day_type, year):
        expected = LiturgicalDay(full_name=name, day_type=day_type, year=year)
        self.assertEqual(LiturgicalDay.parse(name), expected)


if __name__ == "__main__":
    unittest.main()