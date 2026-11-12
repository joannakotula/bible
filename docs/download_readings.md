# download_readings.py

[Back to README](../README.md)

`scripts/download_readings.py` downloads Catholic liturgical readings from
[liturgia.wiara.pl](https://liturgia.wiara.pl) and writes them to
`data/readings.yaml`.

The resulting file is used by `validate_readings.py` and `prepare_stats.py`.

## What it does

1. Loads the liturgical period links from the site navigator.
2. Walks the period tree recursively.
3. Collects links to individual liturgical day pages.
4. Parses the readings from each page.
5. Writes all results to `data/readings.yaml`.

The parser recognizes these reading types:

| Page label | YAML key |
| --- | --- |
| `pierwsze czytanie` | `first` |
| `drugie czytanie` | `second` |
| `psalm responsoryjny` | `psalm` |
| `ewangelia` | `gospel` |

## Usage

Run from the repository root:

```bash
source .venv/bin/activate
python3 scripts/download_readings.py
```

The script takes no command-line arguments.

At the end it prints the output path:

```text
Dane zapisane do data/readings.yaml
```

## Output

`data/readings.yaml` is a YAML list. Each entry looks like this:

```yaml
- name: I Niedziela Adwentu rok A
  periods:
    - Adwent
    - I Tydzień Adwentu
  readings:
    first: Iz 2, 1-5
    gospel: Mt 24, 37-44
    psalm: 'Ps 122 (121), 1b-2. 4-5. 6-7. 8-9 (R.: por. 1bc)'
    second: Rz 13, 11-14
  url: https://liturgia.wiara.pl/doc/413312.I-Niedziela-Adwentu-rok-A
```

Fields:

- `name` — liturgical day name.
- `periods` — liturgical periods the day belongs to.
- `readings` — reading references keyed by reading type.
- `url` — source page URL.

## Important notes

- The script overwrites `data/readings.yaml`. Review the diff before committing.
- It requires network access to `liturgia.wiara.pl`.
- Requests are separated by a short delay to avoid overloading the server.
- If a page cannot be parsed or an exception occurs, the script exits with
  status 1.
- Some readings use the shorter or longer variant of a passage. The parser
  strips the `DŁUŻSZ` prefix for longer variants and skips `KRÓTSZ` shorter
  variants.
- Some Sundays may not include their number in the page title. This is a known
  limitation of the source pages.
- `visited_urls` is tracked for the lifetime of one script run, so a normal
  single run is expected.

## Validation

After downloading, run:

```bash
python3 scripts/validate_readings.py
```

See [validate_readings documentation](validate_readings.md).
