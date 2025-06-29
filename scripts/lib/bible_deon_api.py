import requests
from bs4 import BeautifulSoup
from pathlib import Path


BIBLE_URL='https://biblia.deon.pl'
BOOKS_IDS = {
    'Rdz': 1,
    'Wj': 2,
    'Kpł': 3,
    'Lb': 4,
    'Pwt': 5,
    'Joz': 6,
    'Sdz': 7,
    'Rt': 8,
    '1 Sm': 9,
    '2 Sm': 10,
    '1 Krl': 11,
    '2 Krl': 12,
    '1 Krn': 13,
    '2 Krn': 14,
    'Ezd': 15,
    'Ne': 16,
    'Tb': 17,
    'Jdt': 18,
    'Est': 19,
    '1 Mch': 20,
    '2 Mch': 21,
    'Hi': 22,
    'Ps': 23,
    'Prz': 24,
    'Koh': 25,
    'Pnp': 26,
    'Mdr': 27,
    'Syr': 28,
    'Iz': 29,
    'Jr': 30,
    'Lm': 31,
    'Ba': 32,
    'Ez': 33,
    'Dn': 34,
    'Oz': 35,
    'Jl': 36,
    'Am': 37,
    'Ab': 38,
    'Jon': 39,
    'Mi': 40,
    'Na': 41,
    'Ha': 42,
    'So': 43,
    'Ag': 44,
    'Za': 45,
    'Ml': 46,
    'Mt': 47,
    'Mk': 48,
    'Łk': 49,
    'J': 50,
    'Dz': 51,
    'Rz': 52,
    '1 Kor': 53,
    '2 Kor': 54,
    'Ga': 55,
    'Ef': 56,
    'Flp': 57,
    'Kol': 58,
    '1 Tes': 59,
    '2 Tes': 60,
    '1 Tm': 61,
    '2 Tm': 62,
    'Tt': 63,
    'Flm': 64,
    'Hbr': 65,
    'Jk': 66,
    '1 P': 67,
    '2 P': 68,
    '1 J': 69,
    '2 J': 70,
    '3 J': 71,
    'Jud': 72,
    'Ap': 73
}
BIBLE_CACHE_DIR="cache/bible"

def to_dict(response_data):
    if isinstance(response_data, dict):
        return response_data
    if isinstance(response_data, list):
        return {index: response_data[index] for index in range(len(response_data))}
    raise NotImplementedError(f"unknown type for {response_data}")

def get_chapter_html(chapter_id):
    html_path = Path(f"{BIBLE_CACHE_DIR}/chapter_{chapter_id}.html")
    if html_path.exists():
        with html_path.open() as f:
            return f.read()
    else:
        Path(BIBLE_CACHE_DIR).mkdir(parents=True, exist_ok=True)
        res = requests.get(f"{BIBLE_URL}/rozdzial.php?id={chapter_id}")
        with html_path.open(mode="w") as f:
            f.write(res.text)
        return res.text


def get_verses(chapter_id):
    soup = BeautifulSoup(get_chapter_html(chapter_id), "html.parser")
    verses = soup.select(".werset")
    return [v.get_text(strip=True) for v in verses]

class BibleDeonApi(object):
    def get_chapters_with_verses(self, book_abbr: str):
        book_id = BOOKS_IDS[book_abbr]
        header = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' 
        }
        response = requests.post(f"{BIBLE_URL}", data=f"action=ksiega_change&book={book_id}", headers=header)
        chapters_ids = to_dict(response.json())
        return {index: get_verses(id) for index, id in chapters_ids.items()}




if __name__ == "__main__":
    api = BibleDeonApi()
    chapters_data = api.get_chapters_with_verses("Est")
    print(chapters_data)