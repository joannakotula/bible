import unittest
from parameterized import parameterized
from lib.model import Fragment, FIRST_VERSE, LAST_VERSE

class TestFragmentParser(unittest.TestCase):
    @parameterized.expand([
        ["1 Sm 1, 19-20", [Fragment(book_abbr="1 Sm", chapter=1, first_verse="19", last_verse="20")]],
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
         ],
         ["Ps 42 (41), 2-3; Ps 43 (42), 3. 4 (R.: por. Ps 42 [41], 3cd)",
             [
                 Fragment(book_abbr="Ps", chapter=42, first_verse='2', last_verse='3'),
                 Fragment(book_abbr="Ps", chapter=43, first_verse='3', last_verse='3'),
                 Fragment(book_abbr="Ps", chapter=43, first_verse='4', last_verse='4')
             ]
         ],
         ["Jud 17. 20b-25",
            [
                Fragment(book_abbr="Jud", chapter=17, first_verse="20b", last_verse="25")
            ]
             
         ],
         ["Flm 7-20",
             [
                 Fragment(book_abbr="Flm", chapter=1, first_verse='7', last_verse='20')
             ]
         ]

    ])
    def test_fragment_parser(self, verses_str: str, expected: list):
        self.assertEqual(Fragment.parse(verses_str), expected)


if __name__ == "__main__":
    unittest.main()