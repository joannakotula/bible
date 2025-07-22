import unittest
from parameterized import parameterized
from lib.model import Fragment, FIRST_VERSE, LAST_VERSE

class TestFragmentParser(unittest.TestCase):
    @parameterized.expand([
        ["2 Sm 7, 1-5. 8b-12. 14a. 16", [
            Fragment(book_abbr="2 Sm", chapter=7, first_verse="1", last_verse="5"),
            Fragment(book_abbr="2 Sm", chapter=7, first_verse="8b", last_verse="12"),
            Fragment(book_abbr="2 Sm", chapter=7, first_verse="14a", last_verse="14a"),
            Fragment(book_abbr="2 Sm", chapter=7, first_verse="16", last_verse="16"),
            ]],
        ["Mt 1, 1-25", [Fragment(book_abbr="Mt", chapter=1, first_verse='1', last_verse='25')]],
        ["Ps 25 (24), 4-5. 8-9. 10 i 14 (R.: por. Łk 21, 28)",
            Fragment.create(book_abbr="Ps", chapter=25, verses=[('4', '5'), ('8','9'), ('10', '10'), ('14', '14')])
        ],
        ["Rdz 2, 7-9; 3, 1-7",
            [Fragment(book_abbr="Rdz", chapter=2, first_verse="7", last_verse="9"),
            Fragment(book_abbr="Rdz", chapter=3, first_verse="1", last_verse="7")
            ]
         ],
         ["Rdz 1, 20 – 2, 4a",
             [
                Fragment(book_abbr="Rdz", chapter=1, first_verse='20', last_verse=LAST_VERSE),
                Fragment(book_abbr="Rdz", chapter=2, first_verse=FIRST_VERSE, last_verse="4a")
              ]
         ],
         ["Rdz 1, 20 - 2, 4a; 3, 1",
             [
                Fragment(book_abbr="Rdz", chapter=1, first_verse='20', last_verse=LAST_VERSE),
                Fragment(book_abbr="Rdz", chapter=2, first_verse=FIRST_VERSE, last_verse="4a"),
                Fragment(book_abbr="Rdz", chapter=3, first_verse=1, last_verse=1)
              ]
         ]

    ])
    def test_fragment_parser(self, verses_str: str, expected: list):
        self.assertEqual(Fragment.parse(verses_str), expected)


if __name__ == "__main__":
    unittest.main()