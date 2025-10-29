import sys

from lib.model import Reading, SPECIALDAY, SUNDAY
from lib.utils import read_yaml_file
from lib.data_files import READINGS_FILE

def warn(msg: str):
  print(f"WARN: {msg}", file=sys.stderr)

def error(msg: str):
  print(f"ERROR: {msg}", file=sys.stderr)

def info(msg: str):
  print(f"INFO: {msg}")

READINGS_KEY = "readings"
def check_expected_content(readings_data: dict) -> bool:
  expected = {
    "1 maja - św. Józefa rzemieślnika": {
      READINGS_KEY: {
        "psalm": "Ps 90 (89), 2 i 4. 12-13. 14 i 16",
      }
    },
    "IV Niedziela Zwykła rok B": {
      READINGS_KEY: {
        'first': 'Pwt 18, 15-20',
        'gospel': 'Mk 1, 21-28',
        'psalm': 'Ps 95 (94), 1-2. 6-7c. 7d-9 (R.: por. 7d-8a)',
        'second': '1 Kor 7, 32-35'
      }
    },
    "2 Niedziela po Narodzeniu Pańskim": {
      READINGS_KEY: {
        "first": "Syr 24, 1-2. 8-12",
        "psalm": "Ps 147B, 12-13. 14-15. 19-20 (R.: por. J 1, 14)",
        "second": "Ef 1, 3-6. 15-18",
        "gospel": "J 1, 1-18"
      }
    },
    "Czwartek, 29 tydzień zwykły, Rok I": {
      READINGS_KEY: {
        "gospel": "Łk 12, 49-53"
      }
    },
    "Czwartek, 29 tydzień zwykły, Rok II": {
      READINGS_KEY: {
        "gospel": "Łk 12, 49-53"
      }
    }, 
    "Środa, XIV tydzień zwykły, rok I": {
      READINGS_KEY: {
        "first": "Rdz 41, 55-57; 42, 5-7. 14-15a. 17-24a",
        "psalm": "Ps 33 (32), 2-3. 10-11. 18-19 (R.: por. 22)",
        "gospel": "Mt 10, 1-7"
      }
    },
    # TODO: different gospel for year A and years B/C
    "Poniedziałek IV tygodnia wielkanocnego": {
      READINGS_KEY: {
        "gospel": "J 10, 11-18"
      }
    }
    # TODO: Vigil of Pentecost
    # TODO: March 4 - St. Casimir the Prince (second)
    # TODO: Immaculate Heart of the Blessed Virgin Mary
  }
  errors = 0
  validated_days = []
  for reading in readings_data:
    name = reading['name']
    if name in expected.keys():
      validated_days.append(name)
      expected_readings = expected[reading['name']][READINGS_KEY]
      actual_readings = reading[READINGS_KEY]
      for key, value in expected_readings.items():
        if not (key in actual_readings and actual_readings[key] == value):
          warn(f"Day {name} has {key} reading '{actual_readings.get(key)}' but should have '{value}'")
          errors += 1
  missing_days = list(set(expected.keys()) - set(validated_days))
  if missing_days:
    warn(f"The following days were not parsed: {missing_days}")
    errors += 0
  return errors == 0

def validate_pre_parsing(readings_data: dict):
  return run_check("days have expected readings", lambda: check_expected_content(readings_data))

def check_all_sundays_and_feast_have_at_least_4(readings: dict[str, Reading]) -> bool:
  errors = 0
  for r in readings.values():
    if r.day.day_type in [SPECIALDAY, SUNDAY]:
      fragments_count = len(r.fragments)
      if fragments_count < 4:
        warn(f"Day {r.day.full_name} contains only {fragments_count} fragments but should at least 4 as a day type is {r.day.day_type}")
        errors += 1
  return errors == 0

def validate_post_parsing(readings: dict[str, Reading]):
  return run_check("all Sundays and Fests have at least 4 readings", lambda: check_all_sundays_and_feast_have_at_least_4(readings))

def run_check(name: str, check_fun):
  valid = check_fun()
  status = "✅ OK" if valid else "❌ Error"
  info(f"Checking {name}: {status}")
  return valid

info("loading readings...")
readings_data = read_yaml_file(READINGS_FILE)

if not validate_pre_parsing(readings_data):
  error("Pre parsing validation failed, exiting")
  exit(1)

info("mapping readings...")
readings = {d['name']: Reading(d) for d in readings_data}

if not validate_post_parsing(readings):
  exit(1)



