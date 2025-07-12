import requests
from bs4 import BeautifulSoup
import yaml
import time
from dataclasses import dataclass

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

OUTPUT_FILE="data/readings.yaml"

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

    # Znajdujemy wszystkie linki do okresów liturgicznych
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

    # Znajdujemy wszystkie linki do czytań w danym okresie
    for a in soup.select("div.menu_vert_open_ ul li a"):
        title = a.get_text(strip=True)
        href = a.get("href")
        if href and "/Czytania_mszalne/" in href:
            readings = readings + get_readings_from_period(PeriodLink(title, BASE_URL + href), periods)
        elif href and READINGS_PATH in href:
            readings.append(ReadingLink(title, BASE_URL + href, periods))
    return readings

def get_key_from_title(title: str):
    key_map = {
        "pierwsze czytanie": "first",
        "drugie czytanie": "second",
        "psalm": "psalm",
        "ewangelia": "gospel"
    }
    for k, key in key_map.items():
        if title.lower().startswith(k):
            return key
    return None

def parse_readings(url):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    content = soup.select_one("div.txt__content")
    if not content:
        return {}
    
    paragraphs = content.select(f"p.{TITLE_CLASS}, p.{VERSE_CLASS}")
    readings = {}
    current_key = None

    for p in paragraphs:
        text = p.get_text(strip=True)
        if not text:
            continue

        paragraph_class = p['class']
        if TITLE_CLASS in paragraph_class:
            current_key = get_key_from_title(text)
        elif current_key and VERSE_CLASS in paragraph_class:
            readings[current_key] = text

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
                    "readings": content,
                    "periods": reading.periods
                })
                time.sleep(0.5)  # unikanie przeciążenia serwera
            except Exception as e:
                print(f"❌ Błąd przy {reading.name}: {e}")
                continue

    return all_readings

def save_to_yaml(data, filename=OUTPUT_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)

if __name__ == "__main__":
    # ret = parse_readings("https://liturgia.wiara.pl/doc/413312.I-Niedziela-Adwentu-rok-A")
    # print(yaml.dump(ret))
    readings = collect_all_readings()
    save_to_yaml(readings)
    print(f"✅ Gotowe! Dane zapisane do {OUTPUT_FILE}")
