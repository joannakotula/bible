# validate_readings.py

[Back to README](../README.md)

`scripts/validate_readings.py` checks `data/readings.yaml` for known parsing
problems before the data is used to calculate statistics.

It performs two kinds of checks:

1. **Expected content checks** — selected liturgical days must contain the
   readings hardcoded in the script.
2. **Completeness checks** — Sundays and special days must contain at least four
   reading fragments.

## Usage

Run from the repository root:

```bash
source .venv/bin/activate
python3 scripts/validate_readings.py
```

The script takes no command-line arguments.

## Example output

```text
INFO: loading readings...
INFO: Checking days have expected readings: OK
INFO: mapping readings...
INFO: Checking all Sundays and Fests have at least 4 readings: OK
```

If a check fails, warnings are printed to standard error and the script exits
with status 1.

## What is checked

### Expected readings

The `check_expected_content` function contains a map of liturgical days and the
reading references they should have. For example:

```python
"IV Niedziela Zwykła rok B": {
    "readings": {
        "first": "Pwt 18, 15-20",
        "gospel": "Mk 1, 21-28",
        "psalm": "Ps 95 (94), 1-2. 6-7c. 7d-9 (R.: por. 7d-8a)",
        "second": "1 Kor 7, 32-35",
    }
}
```

If a day exists in `readings.yaml` but a reading is missing or has a different
value, the script prints a warning and fails validation.

Missing expected days are reported as warnings, but they do not currently cause
the script to exit with an error. Update the expected map in the script when new
regression cases are found.

### Sundays and special days

Every reading whose liturgical day type is `sunday` or `special` must have at
least four fragments. This catches pages where only part of the readings was
parsed.

The day type and year are inferred by `scripts/lib/model.py` from the liturgical
day name.

## When to run it

Run it after refreshing the readings:

```bash
python3 scripts/download_readings.py
python3 scripts/validate_readings.py
```

See [download_readings documentation](download_readings.md) and
[lib documentation](lib.md).
