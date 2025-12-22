"""
Parser module for notebooks and CSV files.
Extracts content and schema information.
PERF: Uses orjson for faster JSON parsing when available.
"""

import csv
import os
import re

# PERF: Use orjson for 3-10x faster JSON parsing (optional dependency)
try:
    import orjson
    _use_orjson = True
except ImportError:
    import json
    _use_orjson = False

from logger import get_logger

from .models import ColumnInfo, DatasetFileSchema, NotebookContent

logger = get_logger(__name__)

# Increase CSV field size limit to handle large text fields
# Use a reasonable limit to prevent DoS or OverflowError on some platforms
try:
    # 10MB limit
    csv.field_size_limit(10 * 1024 * 1024)
except Exception:
    pass

# Precompiled regex patterns for performance
EXCESS_NEWLINES_RE = re.compile(r'\n{3,}')
# Matches base64 image data strings (common in IPython display)
# Matches "data:image/..." followed by at least 100 chars of base64-like characters
BASE64_IMAGE_RE = re.compile(r'(data:image/[^;]+;base64,)[a-zA-Z0-9+/=\n\r]{100,}')


def parse_notebook(ipynb_path: str) -> NotebookContent | None:
    """
    Parse a Jupyter notebook file and extract cells.
    robustly handling different nbformat versions (v3, v4).
    PERF: Uses orjson for faster JSON parsing when available.

    Args:
        ipynb_path: Path to .ipynb file

    Returns:
        NotebookContent object or None if parsing fails
    """
    try:
        with open(ipynb_path, "rb" if _use_orjson else "r",
                  encoding=None if _use_orjson else "utf-8",
                  errors=None if _use_orjson else "replace") as f:
            try:
                content = f.read()
                if _use_orjson:
                    notebook_data = orjson.loads(content)
                else:
                    notebook_data = json.loads(content)
            except (ValueError, TypeError):
                # Catches both json.JSONDecodeError and orjson.JSONDecodeError
                logger.warning(f"Invalid JSON in notebook: {ipynb_path}")
                return None

        markdown_cells = []
        code_cells = []

        # Normalize cells list (Handle v3 'worksheets' and v4 'cells')
        cells = []
        if "cells" in notebook_data:
            cells = notebook_data["cells"]
        elif "worksheets" in notebook_data:
            # v3 structure: root -> worksheets -> list of sheets -> cells
            for sheet in notebook_data.get("worksheets", []):
                cells.extend(sheet.get("cells", []))

        # Determine source key based on version (approximate)
        # v4 uses 'source', v3 uses 'input' for code, 'source' for markdown sometimes
        # We'll check both for each cell if needed.

        for cell in cells:
            cell_type = cell.get("cell_type", "")

            # Extract source content robustly
            source_content = cell.get("source", [])
            if not source_content and "input" in cell:
                 source_content = cell["input"]

            # Join source lines into single string
            if isinstance(source_content, list):
                # Ensure all elements are strings
                content = "".join([str(s) for s in source_content])
            else:
                content = str(source_content)

            # Skip empty cells
            if not content.strip():
                continue

            if cell_type == "markdown":
                markdown_cells.append(content)
            elif cell_type == "code":
                code_cells.append(content)
            elif cell_type == "heading":
                # v3 headings can be treated as markdown
                level = cell.get("level", 1)
                markdown_cells.append(f"{'#' * level} {content}")

        return NotebookContent(markdown=markdown_cells, code=code_cells)

    except Exception as e:
        logger.error(f"Failed to parse notebook {ipynb_path}: {e}")
        return None


def parse_csv_schema(
    csv_path: str, max_sample_rows: int = 10, chunk_size: int = 10
) -> DatasetFileSchema | None:
    """
    Parse a CSV file and extract schema with sample rows.
    Tries multiple encodings and falls back safely to default dialect.

    Args:
        csv_path: Path to CSV file
        max_sample_rows: Maximum number of sample rows to include
        chunk_size: Unused, kept for API compatibility

    Returns:
        DatasetFileSchema object or None if parsing fails
    """
    filename = os.path.basename(csv_path)
    logger.debug(f"Parsing CSV schema: {filename}")

    # Try encodings in order
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

    for encoding in encodings:
        try:
            return _parse_csv_with_encoding(csv_path, filename, max_sample_rows, encoding)
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.warning(f"CSV Parse error for {filename} with {encoding}: {e}")
            # If it's not an encoding error, it might be structural, but we try next encoding just in case
            continue

    logger.warning(f"Failed to parse CSV {filename} with all attempted encodings")
    return None

def _parse_csv_with_encoding(csv_path: str, filename: str, max_sample_rows: int, encoding: str) -> DatasetFileSchema | None:
    """Helper to parse CSV with a specific encoding."""

    with open(csv_path, encoding=encoding, errors='replace') as f:
        # Read a sample to detect dialect and headers
        snippet = f.read(4096)
        if not snippet.strip():
            logger.warning(f"Empty CSV file: {filename}")
            return None

        f.seek(0)

        # Detect dialect (delimiter, quoting, etc.)
        try:
            dialect = csv.Sniffer().sniff(snippet)
            has_header = csv.Sniffer().has_header(snippet)
        except csv.Error:
            # Fall back to defaults
            dialect = csv.excel
            has_header = True

        reader = csv.reader(f, dialect)

        if has_header:
            headers = next(reader, None)
            if not headers:
                logger.warning(f"File {filename} has no headers")
                return None
        else:
            # No header - generate column names
            first_row = next(reader, None)
            if not first_row:
                return None
            headers = [f"col_{i}" for i in range(len(first_row))]
            f.seek(0)
            next(reader)  # Skip first row again after seek

        # Read sample rows
        sample_rows = []
        for _ in range(max_sample_rows):
            try:
                row = next(reader)
                if row:
                    sample_rows.append(row)
            except StopIteration:
                break
            except csv.Error:
                # Malformed row in middle of file
                break

        if not sample_rows:
            # It's possible to have headers but no data, which is valid schema
            pass

        # Infer types from first data row
        def infer_dtype(val: str) -> str:
            if not val:
                return "string"
            # Check integer
            if val.lstrip('-').isdigit():
                return "integer"
            # Check float
            try:
                float(val)
                return "float"
            except ValueError:
                pass
            # Check boolean
            if val.lower() in ('true', 'false'):
                return "boolean"
            return "string"

        columns = []
        first_row = sample_rows[0] if sample_rows else []
        for i, col_name in enumerate(headers):
            val = first_row[i] if i < len(first_row) else ""
            columns.append(ColumnInfo(name=col_name, dtype=infer_dtype(val)))

        return DatasetFileSchema(
            filename=filename, columns=columns, sample_rows=sample_rows
        )


def clean_notebook_content(content: NotebookContent) -> NotebookContent:
    """
    Clean notebook content by removing noise and optimizing for LLM context.

    - Removes empty cells
    - Collapses excessive newlines
    - Strips leading/trailing whitespace
    - Truncates large base64 data strings

    Args:
        content: NotebookContent to clean

    Returns:
        Cleaned NotebookContent
    """

    # Clean Markdown cells
    cleaned_md = []
    for cell in content.markdown:
        # Skip cells that are just whitespace
        if cell.strip():
            # Collapse 3+ newlines into 2
            cleaned = EXCESS_NEWLINES_RE.sub('\n\n', cell)
            cleaned_md.append(cleaned.strip())

    # Clean Code cells
    cleaned_code = []
    for cell in content.code:
        # Skip cells that are just whitespace
        if cell.strip():
            # Truncate base64 strings
            cleaned = BASE64_IMAGE_RE.sub(r'\1<TRUNCATED_BASE64_DATA>', cell)
            cleaned_code.append(cleaned.strip())

    return NotebookContent(
        markdown=cleaned_md,
        code=cleaned_code
    )
