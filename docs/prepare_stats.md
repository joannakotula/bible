# prepare_stats.py

[Back to README](../README.md)

`scripts/prepare_stats.py` is the intended step that combines the liturgical
readings with the Bible skeleton to calculate per-verse statistics.

**Current status: work in progress.** The script loads and maps the input data,
but the statistics calculation and output writing are not finished. It does not
currently create `data/stats.yml`.

## What is implemented

1. Loads `data/readings.yaml`.
2. Loads `data/skeleton.yml`.
3. Converts each reading entry into a `Reading` model.
4. Converts the skeleton into `Book` models.
5. Merges the Old and New Testament books into one dictionary.
6. Prints the number of loaded books.

The call that would add readings to the books is currently commented out:

```python
# add_readings(books=)
```

The script also imports `STATS_FILE` but does not write it yet.

## Usage

Run from the repository root:

```bash
source .venv/bin/activate
python3 scripts/prepare_stats.py
```

The script takes no command-line arguments.

Expected current output includes progress messages such as:

```text
loading readings...
loading skeleton...
mapping readings...
mapping skeleton
73
```

The final number is the count of loaded books.

## Planned behavior

The intended pipeline is:

1. Build the Bible skeleton with `generate_stats_skeleton.py`.
2. Download and validate readings.
3. Use `add_readings` from `scripts/lib/model.py` to mark every verse that
   appears in each reading.
4. Calculate statistics for each book, chapter, and verse.
5. Write the result to `data/stats.yml`.

`add_readings` already exists in `scripts/lib/model.py`; the remaining work is to
connect it to `prepare_stats.py` and write the resulting statistics file.

## Related documentation

- [generate_stats_skeleton](generate_stats_skeleton.md)
- [download_readings](download_readings.md)
- [validate_readings](validate_readings.md)
- [lib](lib.md)
