"""Turns generic tabular "sheets" (table_name/tab_name/headers/rows) into a
downloadable zip file, for the Component Analyzer's own CSV/XLSX export
(POST /api/export_component_analyzer -- see api.py). This module has no
opinion on what the data actually means (X4 stats, component names, whatever)
-- the frontend already flattened/resolved every value into plain strings
before this ever runs (see app.js's gatherComponentAnalyzerExportSheets()),
same "just a generic blob mover" spirit as share_storage.py.

Two very different destinations share one input shape:
  - CSV: one .csv file per sheet, named "<table_name>__<tab_name>.csv", all
    flattened into one zip (no per-table grouping -- a single CSV file can't
    hold multiple tabs the way a workbook can).
  - XLSX: one .xlsx *workbook* per distinct table_name, with one *sheet* per
    tab_name inside it, all zipped together -- mirrors the Component
    Analyzer's own table/tab nesting exactly, unlike the CSV case above.

Both dedupe names that collide after sanitization (two tables/tabs sharing a
display name is entirely possible -- table/stat-set names are free text)
by appending " (2)", " (3)", ... to the second and later occurrence, and
sanitize away characters that aren't safe in a filename (CSV/zip entries)
or, more strictly, in an Excel sheet name (also bans brackets and caps out
at 31 characters, Excel's own hard limit).
"""

import csv
import io
import re
import zipfile

from openpyxl import Workbook

# Characters invalid in a Windows/zip-entry filename, replaced with "_".
_FILENAME_UNSAFE_RE = re.compile(r'[\\/:*?"<>|]')
# Excel sheet names additionally forbid brackets (beyond the filename set
# above); the 31-character cap is Excel's own hard limit, not a style choice.
_SHEET_NAME_UNSAFE_RE = re.compile(r"[\\/:*?\[\]]")
_SHEET_NAME_MAX_LENGTH = 31


def sanitize_filename_component(name: str) -> str:
    cleaned = _FILENAME_UNSAFE_RE.sub("_", name.strip())
    return cleaned or "untitled"


def sanitize_sheet_name(name: str) -> str:
    cleaned = _SHEET_NAME_UNSAFE_RE.sub("_", name.strip())[:_SHEET_NAME_MAX_LENGTH]
    return cleaned or "untitled"


def dedupe_names(names: list[str]) -> list[str]:
    """Appends " (2)", " (3)", ... to the 2nd+ occurrence of an exact
    duplicate, preserving input order. Always run *after* sanitization/
    truncation in both builders below, since either step can itself
    introduce a new collision that wasn't there in the original display
    names (e.g. two tab names differing only after character 31).
    """
    seen: dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return result


def build_csv_zip(sheets: list[dict]) -> bytes:
    """One <table_name>__<tab_name>.csv per sheet, all in one zip. `sheets`
    is a list of {table_name, tab_name, headers, rows} dicts (row values
    already stringified by the frontend -- see this module's own docstring).
    """
    filenames = dedupe_names(
        [
            f"{sanitize_filename_component(sheet['table_name'])}__{sanitize_filename_component(sheet['tab_name'])}.csv"
            for sheet in sheets
        ]
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, sheet in zip(filenames, sheets):
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(sheet["headers"])
            writer.writerows(sheet["rows"])
            zf.writestr(filename, csv_buffer.getvalue())
    return buffer.getvalue()


def build_xlsx_zip(sheets: list[dict]) -> bytes:
    """One <table_name>.xlsx workbook per distinct table_name, one sheet per
    tab_name inside it, all in one zip.
    """
    tables: dict[str, list[dict]] = {}
    for sheet in sheets:
        tables.setdefault(sheet["table_name"], []).append(sheet)

    table_filenames = dedupe_names([f"{sanitize_filename_component(name)}.xlsx" for name in tables])

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, table_sheets in zip(table_filenames, tables.values()):
            workbook = Workbook()
            workbook.remove(workbook.active)  # default blank sheet, replaced below
            sheet_names = dedupe_names([sanitize_sheet_name(sheet["tab_name"]) for sheet in table_sheets])
            for sheet_name, sheet in zip(sheet_names, table_sheets):
                worksheet = workbook.create_sheet(sheet_name)
                worksheet.append(sheet["headers"])
                for row in sheet["rows"]:
                    worksheet.append(row)
            xlsx_buffer = io.BytesIO()
            workbook.save(xlsx_buffer)
            zf.writestr(filename, xlsx_buffer.getvalue())
    return buffer.getvalue()
