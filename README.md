# Bible Reading Scripts

This repository contains Python scripts for working with Catholic liturgical
readings and Bible verse statistics, plus a tool for converting Google Docs
articles into wiki syntax.

The scripts support two main workflows:

1. Collecting liturgical readings, validating them, and preparing Bible
   statistics.
2. Parsing Google Docs or Google Drive folders into wiki/pretty output for
   articles, sources, quotes, and Bible verse mentions.

The generated data files live in `data/`. Downloaded Bible chapter HTML is cached
in `cache/bible/`.

## Prerequisites

### Python and virtual environment

Use Python 3.10 or newer. The project is currently tested with Python 3.14.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r scripts/requirements.txt
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

### Dependencies

Runtime dependencies are listed in `scripts/requirements.txt`:

- `requests`
- `beautifulsoup4`
- `pyyaml`
- `parameterized`

### Important: run from the repository root

The scripts use paths relative to the current working directory, for example
`data/readings.yaml` and `cache/bible/`. Run them from the repository root:

```bash
python3 scripts/download_readings.py
python3 scripts/parse_gdoc.py "https://docs.google.com/document/d/<ID>/edit"
```

### External services and credentials

- `download_readings.py` requires network access to `liturgia.wiara.pl`.
- `generate_stats_skeleton.py` requires network access to `biblia.deon.pl`.
- `parse_gdoc.py` can access public Google Docs without credentials. Google Drive
  folders require an API key for public folders or an OAuth access token for
  private folders. Private documents also require an OAuth access token. See
  [parse_gdoc documentation](docs/parse_gdoc.md) for details.

## Scripts

| Script | Short description | Detailed documentation |
| --- | --- | --- |
| `scripts/download_readings.py` | Scrapes liturgical readings from `liturgia.wiara.pl` and writes `data/readings.yaml`. | [download_readings](docs/download_readings.md) |
| `scripts/validate_readings.py` | Validates `data/readings.yaml` against known expected readings and Sunday/feast completeness. | [validate_readings](docs/validate_readings.md) |
| `scripts/generate_stats_skeleton.py` | Builds the Bible book/chapter/verse skeleton in `data/skeleton.yml` using the `biblia.deon.pl` API. | [generate_stats_skeleton](docs/generate_stats_skeleton.md) |
| `scripts/prepare_stats.py` | Work-in-progress script for combining readings with the Bible skeleton to produce verse statistics. | [prepare_stats](docs/prepare_stats.md) |
| `scripts/parse_gdoc.py` | Parses a Google Doc or Google Drive folder into wiki or pretty output. | [parse_gdoc](docs/parse_gdoc.md) |

### Shared library modules

The `scripts/lib/` package contains shared code used by the scripts:

| Module | Purpose | Detailed documentation |
| --- | --- | --- |
| `scripts/lib/model.py` | Reading, fragment, liturgical day, verse, chapter, book, and statistics models. | [lib](docs/lib.md) |
| `scripts/lib/bible_deon_api.py` | Fetches Bible chapter HTML and verse IDs from `biblia.deon.pl`, with a local cache. | [lib](docs/lib.md) |
| `scripts/lib/google_docs.py` | Google Docs/Drive URL parsing, folder listing, export, credentials, and error messages. | [lib](docs/lib.md) |
| `scripts/lib/books.py` | Loads `data/books.yml` and provides book abbreviation lookups. | [lib](docs/lib.md) |
| `scripts/lib/data_files.py` | Defines the standard data file paths. | [lib](docs/lib.md) |
| `scripts/lib/utils.py` | Small YAML loading helper. | [lib](docs/lib.md) |

## Typical workflows

### Refresh liturgical readings

```bash
source .venv/bin/activate
python3 scripts/download_readings.py
python3 scripts/validate_readings.py
```

`download_readings.py` overwrites `data/readings.yaml`. Review the diff before
committing the result.

### Build the Bible skeleton

```bash
source .venv/bin/activate
python3 scripts/generate_stats_skeleton.py
```

This overwrites `data/skeleton.yml` and may take a while. Chapter HTML is cached
in `cache/bible/`; delete that directory to force fresh downloads.

### Convert a Google Doc to wiki output

Public Google Doc:

```bash
python3 scripts/parse_gdoc.py \
  "https://docs.google.com/document/d/<ID>/edit" \
  --out notes_out/article.txt
```

Public Google Drive folder:

```bash
export GOOGLE_API_KEY="your-google-api-key"
mkdir -p notes_out/folder
python3 scripts/parse_gdoc.py \
  "https://drive.google.com/drive/folders/<FOLDER_ID>" \
  --out notes_out/folder
```

See [parse_gdoc documentation](docs/parse_gdoc.md) for output formats, section
selection, folder limitations, and instructions for obtaining a Google API key.

### Run tests

```bash
make tests
```

The Makefile sets `PYTHONPATH` to `scripts/` and runs all `*_test.py` files in
`scripts/tests/`. To run one test module directly:

```bash
PYTHONPATH="$(pwd)/scripts" python3 -m unittest scripts.tests.parse_gdoc_test -v
```

## Data files

| File | Description |
| --- | --- |
| `data/books.yml` | Book names, abbreviations, and English names, grouped by testament. |
| `data/readings.yaml` | Liturgical days with reading references and source URLs. Generated by `download_readings.py`. |
| `data/skeleton.yml` | Full Bible structure with books, chapters, and verse IDs. Generated by `generate_stats_skeleton.py`. |
| `data/stats.yml` | Intended output of `prepare_stats.py`; not currently generated because that script is incomplete. |

## Repository layout

```text
.
├── data/                  # Committed input/generated YAML data
├── docs/                  # Detailed script documentation
├── scripts/               # Executable scripts and shared library code
│   ├── lib/               # Shared models, API client, and data helpers
│   └── tests/             # unittest test suite
├── cache/                 # Local cache (gitignored), including Bible chapter HTML
├── Makefile               # Test runner
└── README.md
```
