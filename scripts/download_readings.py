import requests
from bs4 import BeautifulSoup
import yaml
import time
import re
import sys
import traceback
from dataclasses import dataclass
from lib.data_files import READINGS_FILE

############################################################
## There are some known issues:
# * some sundays do not have information about their number
# * some fragments have prefix "KROTSZE" - script took the
#   shorter fragments and added prefix
############################################################


BASE_URL = "https://liturgia.wiara.pl"
NAWIGATOR_URL = f"{BASE_URL}/Czytania_mszalne/Nawigator/"
READINGS_PATH=f"/doc/"
VERSE_CLASS = "bible-verse"
TITLE_CLASS = "block-title"
SHORTER_PREFIX = "KRÓTSZ"
LONGER_PREFIX = "DŁUŻSZ"


READING_KEYS_MAP = {
    "pierwsze czytanie": "first",
    "drugie czytanie": "second",
    "psalm responsoryjny": "psalm",
    "ewangelia": "gospel"
}

# Data for pages that cannot be parsed correctly 
# as they lack e.g. proper tag on verses
# PRESET_PARSE_DATA = {
#     "https://liturgia.wiara.pl/doc/410527.30-grudnia-szosty-dzien-w-Oktawie-Narodzenia-Panskiego": {
#         'first': '1 J 2, 12-17',
#         'psalm': 'Ps 96 (95), 7-8. 9-10 (R.: por. 11a)',
#         'gospel': 'Łk 2, 36-40'
#     }
# }

visited_urls = []

@dataclass
class PeriodLink:
    name: str
    url: str

@dataclass
class ReadingLink:
    name: str
    url: str
    periods: list[str]

def get_period_links():
    res = requests.get(NAWIGATOR_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    period_links = []

    # Find all links to liturgical periods
    for a in soup.select("div.menu_vert_open_ ul li a"):
        href = a.get("href")
        if href and "/Czytania_mszalne/" in href:
            period_links.append(PeriodLink('', BASE_URL + href))
    return period_links

def get_readings_from_period(link: PeriodLink, parents_periods=[]) -> list[ReadingLink]:
    if link.url in visited_urls:
        return []
    visited_urls.append(link.url)
    res = requests.get(link.url)
    soup = BeautifulSoup(res.text, "html.parser")
    readings = []
    periods = parents_periods + [link.name] if link.name else parents_periods

    print(f"Getting readings from {link.url}")

    # Find all links to readings in the given period
    for a in soup.select("div.menu_vert_open_ ul li a"):
        title = a.get_text(strip=True)
        href = a.get("href")
        if href and "/Czytania_mszalne/" in href:
            readings = readings + get_readings_from_period(PeriodLink(title, BASE_URL + href), periods)
        elif href and READINGS_PATH in href:
            readings.append(ReadingLink(title, BASE_URL + href, periods))
    return readings

def get_key_from_title(title: str):
    for k, key in READING_KEYS_MAP.items():
        if title.lower().startswith(k):
            return key
    return None

def get_matching_key_name(text: str):
    normalized_text = text.lower()
    names = [name for name in READING_KEYS_MAP.keys() if normalized_text.startswith(name)]
    if names:
        return names[0]
    return None

def remove_key_name(text: str, key_name: str):
    return text[len(key_name):].strip()

def is_valid_fragment(text: str, debug_info: str):
    match_book_chapter=re.match("([\d]? ?\w+) (\d+.*)", text)
    if match_book_chapter:
        return True
    print(f"Verse: '{text}' doesn't look like Bible verse (for {debug_info})", file=sys.stderr)
    return False

    

def parse_readings(url):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    content = soup.select_one("div.txt__content")
    if not content:
        return {}
    current_key = None
    readings = {}

    def add_reading(key: str, text: str):
        nonlocal current_key
        nonlocal readings
        readings[key] = text
        current_key = None

    all_paragraphs = content.select("p")
    for p in all_paragraphs:
        text = p.get_text(strip=True)
        if not text:
            continue
        paragraph_class = p.get('class', '')
        if TITLE_CLASS in paragraph_class:
            current_key = get_key_from_title(text)
        elif current_key and VERSE_CLASS in paragraph_class:
            if is_valid_fragment(text, debug_info=url):
                add_reading(current_key, text)
        elif current_key and is_valid_fragment(text, debug_info=url):
            add_reading(current_key, text)
        else:
            matching_name = get_matching_key_name(text)
            if matching_name:
                key = READING_KEYS_MAP[matching_name]
                fragment = text[len(matching_name):].strip()
                if fragment.startswith(LONGER_PREFIX):
                    fragment = fragment[len(LONGER_PREFIX)+1:].strip()
                if not fragment.startswith(SHORTER_PREFIX) and is_valid_fragment(fragment, debug_info=url):
                    add_reading(key, fragment)

    if not readings:
        print(f"No readings for {url}", file=sys.stderr)
    return readings

def collect_all_readings():
    period_links = get_period_links()
    all_readings = []

    for link in period_links:
        period_readings = get_readings_from_period(link)
        for reading in period_readings:
            print(f"Pobieram: {reading.name}")
            print(reading.url)
            try:
                content = parse_readings(reading.url)
                all_readings.append({
                    "name": reading.name,
                    "url": reading.url,
                    "readings": content,
                    "periods": reading.periods
                })
                time.sleep(0.5)  # avoid overloading the server
            except Exception as e:
                print(f"❌ Błąd przy {reading.name}: {traceback.format_exc()}", file=sys.stderr)
                exit(1)

    return all_readings

def save_to_yaml(data, filename=READINGS_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)

if __name__ == "__main__":
    # ret = parse_readings("https://liturgia.wiara.pl/doc/410527.30-grudnia-szosty-dzien-w-Oktawie-Narodzenia-Panskiego")
    # print(yaml.dump(ret, allow_unicode=True))
    readings = collect_all_readings()
    save_to_yaml(readings)
    print(f"✅ Gotowe! Dane zapisane do {READINGS_FILE}")
