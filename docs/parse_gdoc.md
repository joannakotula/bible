# parse_gdoc.py

[Back to README](../README.md)

`scripts/parse_gdoc.py` downloads a Google Doc, or every Google Doc directly
inside a Google Drive folder, and converts selected sections into wiki syntax or
a readable Python dictionary.

It is intended for articles written in a specific Google Docs structure:

- `Streszczenie` (summary)
- `Źródła` (sources)
- `Wzmianki` (Bible verse mentions)
- `Komentarze` (quotes extracted from the sources section)

The script does not support local files or local directories. Input must be a
Google Docs or Google Drive URL.

## Requirements

Install the shared dependencies from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

Run the script from the repository root.

## Basic usage

```bash
python3 scripts/parse_gdoc.py "<GOOGLE_DOC_OR_DRIVE_URL>"
```

By default the result is written to standard output in wiki format.

Write the result to a file:

```bash
python3 scripts/parse_gdoc.py \
  "https://docs.google.com/document/d/<ID>/edit" \
  --out notes_out/article.txt
```

Write the result to a directory. The filename is derived from the document
title:

```bash
mkdir -p notes_out
python3 scripts/parse_gdoc.py \
  "https://docs.google.com/document/d/<ID>/edit" \
  --out notes_out
# creates notes_out/<title-slug>.txt
```

## CLI options

| Option | Description |
| --- | --- |
| `gdoc_link` | Google Docs URL, Google Drive file URL, or Google Drive folder URL. Required. |
| `--out`, `--output`, `-o` | Output file, existing output directory, or `-` for stdout. If omitted, output goes to stdout. |
| `--api-key` | Google API key. Defaults to the `GOOGLE_API_KEY` environment variable. |
| `--access-token` | Google OAuth access token. Defaults to the `GOOGLE_ACCESS_TOKEN` environment variable. |
| `--format`, `-f` | Output format: `wiki` or `pretty`. Default: `wiki`. |
| `--sections` | Sections to render: `summary`, `quotes`, `mentions`, `sources`. Default: all sections. |

Examples:

```bash
# Only summary and mentions, as wiki text
python3 scripts/parse_gdoc.py "<URL>" --sections summary mentions

# All sections as a Python pretty-printed dictionary
python3 scripts/parse_gdoc.py "<URL>" --format pretty

# Explicit output file
python3 scripts/parse_gdoc.py "<URL>" --out notes_out/result.txt
```

## Document sections

Section names are matched from the document's H1 headings, case-insensitively.

| H1 in the document | CLI section name | Output |
| --- | --- | --- |
| `Streszczenie` | `summary` | Plain text and parsed Bible verse templates. |
| `Źródła` | `sources` | `Source` wiki templates. |
| `Komentarze` | `quotes` | `Quote` wiki templates extracted from `Źródła`. |
| `Wzmianki` | `mentions` | `BibleVerse` wiki templates. |

### `Źródła` / sources

Each H2 heading starts a new source. Within a source:

- The title is the H2 text.
- A leading `(xx)` in the title sets the language; the default is `pl`.
- The first line starting with `http://`, `https://`, or `www.` is the URL.
- Lines before the URL are treated as the source description.
- Blocks after a line starting with `--` or `–` are quotes.
- YouTube and `youtu.be` URLs are classified as `film`; other URLs as `artykuł`.

### `Wzmianki` / mentions

- A mention may span multiple lines; continuation lines are appended to the
  current verse.
- Blank lines and separator lines starting with `--` or `–` split mentions into
  separate blocks.
- Consecutive verse references are merged when they belong to the same book and
  chapter and the next reference starts at the previous reference's last verse
  plus one. For example, `J 2, 1` followed by `J 2, 2` becomes `J 2, 1-2`.
- Merging does not cross blank lines or hard separators.

### `Streszczenie` / summary

- Bullets such as `•`, `-`, `*`, and numbered items are stripped.
- Bible verse references are converted into `BibleVerse` entries.
- Prose lines break consecutive-verse merging.
- Blank lines break merging but are not emitted.
- Hard separator lines are preserved as empty entries.

## Output formats

### `wiki`

Produces wiki templates such as:

```text
== Wzmianki ==

{{Cytat biblijny
    |tekst=...
    |werset=J 2, 1
    |link_sekcji=Ewangelia wg św. Jana#J 2|}}
```

### `pretty`

Prints a Python `pprint` representation of the parsed sections. This is useful
for inspecting the parsed structure, not for publishing.

## Output naming

- If `--out` is omitted or `-`, output is written to stdout.
- If `--out` is an existing directory, the script writes `<slug>.txt`.
- For a single document, the slug comes from the HTML `<title>`; if unavailable,
  the document ID is used.
- For a Drive folder, the slug comes from each Drive file name; if unavailable,
  the file ID is used.
- If `--out` is any other path, it is treated as an output file.

Slugs transliterate Polish characters and replace runs of whitespace,
underscores, and hyphens with a single hyphen.

## Use case: parse a single public Google Doc

Public documents usually do not need credentials:

```bash
python3 scripts/parse_gdoc.py \
  "https://docs.google.com/document/d/<ID>/edit" \
  --out notes_out/article.txt
```

With an API key, the script first tries the public Google Docs HTML export URL
and then the Google Drive export API if that fails. With an OAuth access token,
it uses the Google Drive export API directly.

## Use case: parse a private Google Doc

Private documents require an OAuth access token. An API key alone is not enough
to grant access to private files.

```bash
export GOOGLE_ACCESS_TOKEN="ya29.your-access-token"
python3 scripts/parse_gdoc.py \
  "https://docs.google.com/document/d/<ID>/edit" \
  --out notes_out/private-article.txt
```

The token must have permission to read the document, for example the Drive scope
`https://www.googleapis.com/auth/drive.readonly`.

## Use case: parse a Google Drive folder with an API key

Folder URLs look like this:

```text
https://drive.google.com/drive/folders/<FOLDER_ID>
```

For a **public folder**, use a Google API key:

```bash
export GOOGLE_API_KEY="your-google-api-key"
mkdir -p notes_out/folder
python3 scripts/parse_gdoc.py \
  "https://drive.google.com/drive/folders/<FOLDER_ID>" \
  --out notes_out/folder
```

The folder must be shared so that anyone with the link can view it. An API key
does not grant access to private folders; it only identifies the API project.

The script:

1. Lists Google Docs directly inside the folder using Google Drive API v3.
2. Ignores files that are not Google Docs.
3. Exports each document as HTML.
4. Parses it using the selected `--sections` and `--format`.
5. Writes one `<drive-file-name-slug>.txt` file per document.

Folder limitations:

- `--out` must be an existing directory. Passing a file path exits with code 2.
- Only direct children are processed. Nested subfolders are not traversed.
- If no Google Docs are found, the script exits with an error.
- If two Drive files produce the same slug, the later file overwrites the
  earlier one.
- One document that fails to download or parse aborts the whole folder run.

### How to obtain a Google API key

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing project.
3. Go to **APIs & Services > Library**.
4. Search for **Google Drive API** and enable it.
5. Go to **APIs & Services > Credentials**.
6. Select **Create credentials > API key**.
7. Copy the generated key.
8. Optionally restrict the key to the Google Drive API and to your expected
   usage, then save the changes.

Set the key in your environment:

```bash
export GOOGLE_API_KEY="your-google-api-key"
```

Or pass it explicitly:

```bash
python3 scripts/parse_gdoc.py "<FOLDER_URL>" --out notes_out/folder --api-key "your-google-api-key"
```

Do not commit API keys or access tokens to the repository.

### How to obtain an OAuth access token for a private folder

Use an OAuth 2.0 flow with the Drive scope
`https://www.googleapis.com/auth/drive.readonly`. For a quick manual test, the
[OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) can be
used to authorize the Drive API v3 and copy the resulting access token.

```bash
export GOOGLE_ACCESS_TOKEN="ya29.your-access-token"
python3 scripts/parse_gdoc.py "<FOLDER_URL>" --out notes_out/private-folder
```

Access tokens expire. Obtain a new token when the old one stops working.

## Troubleshooting

### Credential and permission errors

Credential requirements are reported directly:

- Folder URL with no credentials: the script asks for `GOOGLE_API_KEY` /
  `--api-key` for a public folder or `GOOGLE_ACCESS_TOKEN` / `--access-token`
  for a private folder.
- API key used for a private folder: the folder requires an access token.
- Missing, expired, or invalid access token: the access token is reported as
  missing, expired, or invalid.
- Private document with no credentials: the document requires an access token.
- Google sign-in page returned instead of a document: the document is private or
  not shared publicly and requires an access token.
- Invalid API key or disabled Drive API: the API key was rejected or the Drive
  API is not enabled.

For any of these:

- Confirm the document or folder is shared with the account or publicly.
- For folders, confirm **Google Drive API** is enabled in the Google Cloud
  project that owns the API key.
- For private files and folders, confirm the OAuth token has Drive read
  permission.
- OAuth access tokens expire; generate a new one.

### `No Google Docs found in folder`

- The folder is empty.
- The folder contains only subfolders or non-Google-Docs files.
- The folder is not shared with the account or publicly.
- The API key or access token does not have access.

### A section is missing from the output

The H1 heading must match one of the expected Polish names. Check for extra
spaces, different wording, or a heading level other than H1.

### Local paths do not work

This is intentional. Use Google Docs or Google Drive URLs instead.

## Tests

From the repository root:

```bash
make tests
```

The `parse_gdoc` tests cover verse merging, separator handling, section parsing,
URL ID extraction, `GoogleDriveApi` document/folder fetching, Drive folder
pagination, slugging, output naming, Google error formatting, login-page
detection, and credential errors.
