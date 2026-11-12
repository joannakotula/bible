# generate_stats_skeleton.py

[Back to README](../README.md)

`scripts/generate_stats_skeleton.py` builds the full Bible structure used for
verse statistics and writes it to `data/skeleton.yml`.

The skeleton contains every book, chapter, and verse number, but not the verse
text or the reading statistics.

## What it does

1. Reads the book list from `data/books.yml`.
2. For each book, requests the chapter list from `biblia.deon.pl`.
3. Downloads each chapter page and extracts verse IDs.
4. Builds a `Book` model with all chapters and verses.
5. Writes the combined structure for the Old and New Testaments to
   `data/skeleton.yml`.

Chapter HTML is cached in `cache/bible/`. If a cached file exists, the script
reuses it instead of downloading the chapter again.

## Usage

Run from the repository root:

```bash
source .venv/bin/activate
python3 scripts/generate_stats_skeleton.py
```

The script takes no command-line arguments.

## Output

`data/skeleton.yml` has this shape:

```yaml
Old Testament:
  Rdz:
    full_name: Księga Rodzaju
    chapters:
      '1':
        verses:
          - number: '1'
          - number: '2'
New Testament:
  Mt:
    full_name: Ewangelia według św. Mateusza
    chapters:
      '1':
        verses:
          - number: '1'
```

The exact verse numbers depend on the source site.

## Important notes

- The script overwrites `data/skeleton.yml`.
- It requires network access to `biblia.deon.pl`.
- The first run can take a long time because it downloads every chapter.
- Delete `cache/bible/` to force fresh chapter downloads.
- `scripts/lib/bible_deon_api.py` contains a `BOOKS_IDS` map from book
  abbreviation to the source site's numeric book ID. If you add a book to
  `data/books.yml`, add the corresponding ID there too.
- If the source site is unavailable or changes its HTML structure, verse
  extraction may fail.

## Related files

- `data/books.yml` — input book list.
- `data/skeleton.yml` — generated output.
- `scripts/lib/bible_deon_api.py` — API client and chapter cache.
- `scripts/lib/model.py` — book, chapter, and verse models.

See [lib documentation](lib.md) and
[prepare_stats documentation](prepare_stats.md).
