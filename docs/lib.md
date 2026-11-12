# scripts/lib

[Back to README](../README.md)

The `scripts/lib/` package contains shared code used by the executable scripts.
These modules are not standalone command-line tools.

## Modules

### `model.py`

Defines the domain model:

- `Fragment` — a Bible verse range, parsed from references such as
  `J 2, 1-12`, `Rdz 41, 55-57; 42, 5-7`, or cross-chapter ranges.
- `LiturgicalDay` — a liturgical day with a name, type (`sunday`, `weekday`, or
  `special`), and optional year (`A`, `B`, `C`, `I`, or `II`).
- `Reading` — a liturgical day with its reading fragments grouped by reading
  type (`first`, `second`, `psalm`, `gospel`).
- `ReadStats` — counters for verse usage statistics.
- `Verse` — a single Bible verse with its readings and statistics.
- `Chapter` — a chapter containing verses and chapter-level statistics.
- `Book` — a book containing chapters and book-level statistics.
- `add_readings(books, readings)` — walks all reading fragments and marks the
  corresponding verses in the book model.

This module is used by `validate_readings.py`, `prepare_stats.py`,
`generate_stats_skeleton.py`, and `parse_gdoc.py`.

### `bible_deon_api.py`

Client for `biblia.deon.pl`.

- `BOOKS_IDS` maps book abbreviations to the source site's numeric book IDs.
- `BibleDeonApi.get_chapters_with_verses(book_abbr)` returns chapter IDs and
  verse lists for a book.
- Chapter HTML is cached in `cache/bible/chapter_<id>.html`.

Used by `generate_stats_skeleton.py`.

### `google_docs.py`

Google Docs and Google Drive access helpers used by `parse_gdoc.py`:

- `GoogleDriveApi(api_key=None, access_token=None)` — holds credentials and
  provides the main Google access API:
  - `is_folder_url(url)` — returns whether a URL points to a Drive folder.
  - `fetch_doc(url)` — fetches one Google Doc and returns a `GoogleDoc`.
  - `fetch_docs_from_folder(url)` — lists and fetches every Google Doc directly
    inside a Drive folder, returning `list[GoogleDoc]`.
- `GoogleDoc` — dataclass with `id`, `name`, and `html`. For a single document,
  `name` comes from the HTML `<title>` with the document ID as fallback; for
  folder documents it comes from the Drive file name.
- `GoogleApiError` — Google API or access error with `status_code`, `reason`,
  `message`, and credential context. `from_response(response)` builds it from an
  HTTP response; `from_message(message)` is used for non-HTTP errors such as a
  Google sign-in page. `with_context(target, has_api_key, has_access_token)`
  attaches request context. `user_message` formats a short credential or
  permission explanation. `is_api_key_error()` detects API-key and Drive-API
  configuration errors.
- `CredentialTarget` — enum identifying whether an error concerns a folder or a
  document.
- Lower-level helpers: `extract_doc_id`, `extract_folder_id`,
  `document_name_from_html`, `list_folder_docs`, and `fetch_drive_export`.

### `books.py`

Loads `data/books.yml` and exposes:

- `books_list_per_testament` — books grouped by testament.
- `all_books_list` — a flat list with a `testament` field added.
- `abbr_2_book_data` — lookup from abbreviation to book data.

Used by `parse_gdoc.py` to build Bible verse links.

### `data_files.py`

Defines the standard relative data paths:

```python
READINGS_FILE = "data/readings.yaml"
SKELETON_FILE = "data/skeleton.yml"
BOOKS_FILE = "data/books.yml"
STATS_FILE = "data/stats.yml"
```

All paths are relative to the current working directory, so scripts should be
run from the repository root.

### `utils.py`

Contains `read_yaml_file(filename)`, a small wrapper around `yaml.safe_load`.

## Tests

Shared behavior is covered by the test files in `scripts/tests/`, especially:

- `fragment_test.py` — Bible reference parsing.
- `liturgical_day_test.py` — liturgical day type and year parsing.
- `reading_test.py` — reading model construction.
- `stats_test.py` — statistics aggregation.

Run all tests from the repository root:

```bash
make tests
```
