import unittest

from bs4 import BeautifulSoup

from parse_gdoc import BibleVerse, parse_mentions_section, parse_summary_section


def make_nodes(lines: list[str]) -> list:
    soup = BeautifulSoup("<div></div>", "html.parser")
    container = soup.div
    for line in lines:
        paragraph = soup.new_tag("p")
        paragraph.string = line
        container.append(paragraph)
    return list(container.children)


class TestVerseMerging(unittest.TestCase):
    parsers = (parse_mentions_section, parse_summary_section)

    def assert_verses(self, parser, nodes, expected):
        elements = parser(nodes)
        verses = [element for element in elements if isinstance(element, BibleVerse)]
        self.assertEqual([verse.verse for verse in verses], expected)
        return verses

    def test_merges_consecutive_verses(self):
        nodes = make_nodes([
            "J 2, 1: Trzeciego dnia odbywało się wesele w Kanie Galilejskiej.",
            "J 2, 2: Zaproszono na to wesele także Jezusa i Jego uczniów.",
        ])

        for parser in self.parsers:
            with self.subTest(parser=parser.__name__):
                verses = self.assert_verses(parser, nodes, ["J 2, 1-2"])
                self.assertEqual(len(verses), 1)
                self.assertEqual(
                    verses[0].content,
                    "Trzeciego dnia odbywało się wesele w Kanie Galilejskiej. "
                    "Zaproszono na to wesele także Jezusa i Jego uczniów.",
                )

    def test_extends_existing_verse_range(self):
        nodes = make_nodes([
            "J 2, 1-2: Dwa pierwsze wersety.",
            "J 2, 3: Trzeci werset.",
        ])

        for parser in self.parsers:
            with self.subTest(parser=parser.__name__):
                verses = self.assert_verses(parser, nodes, ["J 2, 1-3"])
                self.assertEqual(len(verses), 1)
                self.assertEqual(verses[0].content, "Dwa pierwsze wersety. Trzeci werset.")

    def test_does_not_merge_non_consecutive_verses(self):
        nodes = make_nodes([
            "J 2, 1: Pierwszy werset.",
            "J 2, 4: Czwarty werset.",
        ])

        for parser in self.parsers:
            with self.subTest(parser=parser.__name__):
                self.assert_verses(parser, nodes, ["J 2, 1", "J 2, 4"])

    def test_does_not_merge_verses_from_different_chapters(self):
        nodes = make_nodes([
            "J 2, 2: Drugi werset.",
            "J 3, 1: Pierwszy werset kolejnego rozdziału.",
        ])

        for parser in self.parsers:
            with self.subTest(parser=parser.__name__):
                self.assert_verses(parser, nodes, ["J 2, 2", "J 3, 1"])

    def test_does_not_merge_consecutive_verses_across_soft_separator(self):
        nodes = make_nodes([
            "Ps 2, 7: Ogłoszę postanowienie Pana.",
            "Ps 2, 8: Żądaj ode Mnie, a dam Ci narody w dziedzictwo.",
            "",
            "Ps 2, 9: Żelazną rózgą będziesz nimi rządzić.",
        ])

        for parser in self.parsers:
            with self.subTest(parser=parser.__name__):
                self.assert_verses(parser, nodes, ["Ps 2, 7-8", "Ps 2, 9"])

    def test_does_not_merge_consecutive_verses_across_hard_separator(self):
        nodes = make_nodes([
            "Ps 2, 7: Ogłoszę postanowienie Pana.",
            "Ps 2, 8: Żądaj ode Mnie, a dam Ci narody w dziedzictwo.",
            "--",
            "Ps 2, 9: Żelazną rózgą będziesz nimi rządzić.",
        ])

        for parser in self.parsers:
            with self.subTest(parser=parser.__name__):
                self.assert_verses(parser, nodes, ["Ps 2, 7-8", "Ps 2, 9"])


class TestParseMentionsSection(unittest.TestCase):
    def test_merges_continuation_lines_into_content(self):
        nodes = make_nodes([
            "J 2, 1: Trzeciego dnia odbywało się wesele",
            "w Kanie Galilejskiej i była tam Matka Jezusa.",
            "J 2, 2: Zaproszono na to wesele także Jezusa i Jego uczniów.",
        ])

        verses = parse_mentions_section(nodes)

        self.assertEqual(len(verses), 1)
        self.assertEqual(verses[0].verse, "J 2, 1-2")
        self.assertEqual(
            verses[0].content,
            "Trzeciego dnia odbywało się wesele w Kanie Galilejskiej i była tam Matka Jezusa. "
            "Zaproszono na to wesele także Jezusa i Jego uczniów.",
        )


class TestParseSummarySection(unittest.TestCase):
    def test_does_not_merge_verses_separated_by_prose(self):
        nodes = make_nodes([
            "J 2, 1: Pierwszy werset.",
            "Jakiś komentarz między wersetami.",
            "J 2, 2: Drugi werset.",
        ])

        elements = parse_summary_section(nodes)

        self.assertEqual(len(elements), 3)
        self.assertEqual(elements[0].verse, "J 2, 1")
        self.assertEqual(elements[1], "Jakiś komentarz między wersetami.")
        self.assertEqual(elements[2].verse, "J 2, 2")

    def test_hard_separator_is_preserved_in_summary(self):
        nodes = make_nodes([
            "J 2, 1: Pierwszy werset.",
            "J 2, 2: Drugi werset.",
            "--",
            "J 2, 3: Trzeci werset.",
        ])

        elements = parse_summary_section(nodes)

        self.assertEqual(len(elements), 3)
        self.assertEqual(elements[0].verse, "J 2, 1-2")
        self.assertEqual(elements[1], "")
        self.assertEqual(elements[2].verse, "J 2, 3")


if __name__ == "__main__":
    unittest.main()
