"""
TOON (Token-Oriented Object Notation) Encoder/Decoder.

TOON is a compact, LLM-friendly data format that saves 30-60% tokens compared to JSON.
Based on the TOON Plus format specification.

Format example:
    users{name,age,active}
    Ana,null,false
    Bruno,34,true

Compared to JSON:
    [{"name": "Ana", "age": null, "active": false}, {"name": "Bruno", "age": 34, "active": true}]
"""

import json
import re
from typing import Any


class ToonEncoder:
    """
    Encoder for converting Python data structures to TOON format.

    TOON format is optimized for:
    - Token efficiency (30-60% fewer tokens than JSON)
    - Human readability
    - LLM context optimization
    """

    @staticmethod
    def encode_value(v: Any) -> str:
        """
        Encode a Python value to TOON string representation.

        Args:
            v: Any Python value (None, bool, int, float, str, list, dict)

        Returns:
            TOON-formatted string representation
        """
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            return f"[{', '.join(map(ToonEncoder.encode_value, v))}]"
        if isinstance(v, dict):
            inner = ", ".join(
                f"{k}: {ToonEncoder.encode_value(vv)}" for k, vv in v.items()
            )
            return "{" + inner + "}"

        if isinstance(v, str):
            s = str(v)
            # Numbers that are strings need quotes
            if re.match(r"^-?\d", s):
                return '"' + s + '"'
            # Special characters need quotes
            if any(c in s for c in [",", "[", "]", "{", "}", "\n", "\r", '"']):
                return '"' + s.replace('"', '\\"') + '"'
            # Boolean-like strings need quotes
            if s.lower() in ("true", "false", "null", "none"):
                return '"' + s + '"'
            return s

        # Fallback
        return '"' + str(v).replace('"', '\\"') + '"'

    @classmethod
    def _encode_list_block(cls, name: str | None, items: list[Any]) -> str:
        """Encode a list of items as a TOON block."""
        if not items:
            return f"{name}{{}}" if name else "{}"

        # If items aren't dicts, encode as inline array
        if not isinstance(items[0], dict):
            val = f"[{', '.join(map(cls.encode_value, items))}]"
            return f"{name}{val}" if name else val

        keys = list(items[0].keys())
        header = f"{name}{{{','.join(keys)}}}" if name else "{" + ",".join(keys) + "}"
        rows = [
            ",".join(map(cls.encode_value, (it.get(k) for k in keys))) for it in items
        ]
        return header + "\n" + "\n".join(rows)

    @classmethod
    def encode(cls, data: dict | list) -> str:
        """
        Encode Python data structure to TOON format.

        Args:
            data: Dictionary or List to encode

        Returns:
            TOON-formatted string
        """
        if isinstance(data, list):
            return cls._encode_list_block(None, data)

        if isinstance(data, dict):
            # Check if dict has complex values
            has_complex_values = False
            for v in data.values():
                if isinstance(v, dict):
                    has_complex_values = True
                    break
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    has_complex_values = True
                    break

            # Simple dict: encode inline
            if not has_complex_values:
                keys = list(data.keys())
                header = "{" + ",".join(keys) + "}"
                row = ",".join(cls.encode_value(data[k]) for k in keys)
                return header + "\n" + row

            # Complex dict: encode as blocks
            blocks = []
            for name, value in data.items():
                if isinstance(value, list):
                    blocks.append(cls._encode_list_block(name, value))
                    continue

                if isinstance(value, dict):
                    keys = list(value.keys())
                    row = ",".join(cls.encode_value(value[k]) for k in keys)
                    blocks.append(f"{name}{{{','.join(keys)}}}\n{row}")
                    continue

                # Primitive value
                blocks.append(f"{name}: {cls.encode_value(value)}")

            return "\n\n".join(blocks)

        raise TypeError("Input must be dict or list.")


class ToonDecoder:
    """
    Decoder for converting TOON format to Python data structures.
    """

    @staticmethod
    def _split_top_level_commas(text: str):
        """Split text by commas, respecting quotes and brackets."""
        stack = []
        in_quotes = False
        esc = False
        start = 0

        for i, ch in enumerate(text):
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_quotes = not in_quotes
                continue
            if not in_quotes:
                if ch in "[{":
                    stack.append(ch)
                elif ch in "]}":
                    if stack:
                        stack.pop()
                elif ch == "," and not stack:
                    yield text[start:i].strip()
                    start = i + 1

        if start < len(text):
            yield text[start:].strip()

    @staticmethod
    def parse_value(tok: str) -> Any:
        """Parse a TOON token to a Python value."""
        tok = tok.strip()
        if not tok:
            return None

        low = tok.lower()
        if low in ("null", "none"):
            return None
        if low == "true":
            return True
        if low == "false":
            return False

        # Quoted string
        if tok.startswith('"') and tok.endswith('"'):
            return tok[1:-1].replace('\\"', '"')

        # Lists
        if tok.startswith("[") and tok.endswith("]"):
            inner = tok[1:-1].strip()
            if not inner:
                return []
            return list(
                map(ToonDecoder.parse_value, ToonDecoder._split_top_level_commas(inner))
            )

        # Objects
        if tok.startswith("{") and tok.endswith("}"):
            inner = tok[1:-1].strip()
            if not inner:
                return {}
            obj = {}
            for p in ToonDecoder._split_top_level_commas(inner):
                if ":" in p:
                    k, v = p.split(":", 1)
                    obj[k.strip().strip('"')] = ToonDecoder.parse_value(v.strip())
            return obj

        # Numbers
        if re.fullmatch(r"-?\d+", tok):
            return int(tok)
        if re.fullmatch(r"-?\d+\.\d+", tok):
            return float(tok)

        return tok

    @classmethod
    def decode(cls, text: str) -> dict | list | Any:
        """
        Decode TOON format to Python data structure.

        Args:
            text: TOON-formatted string

        Returns:
            Python data structure (dict, list, or primitive)
        """
        text = text.strip()

        # Pure list
        if text.startswith("[") and text.endswith("]"):
            return cls.parse_value(text)

        header_re = re.compile(r"^([A-Za-z0-9_]+)?\{([^}]+)\}$", re.MULTILINE)
        matches = list(header_re.finditer(text))

        if not matches:
            return cls.parse_value(text)

        # Single block
        if len(matches) == 1 and matches[0].group(1) is None:
            m = matches[0]
            keys = [k.strip() for k in m.group(2).split(",")]
            body = text[m.end() :].strip()
            lines = [l.strip() for l in body.splitlines() if l.strip()]

            if len(lines) == 1:
                vals = list(cls._split_top_level_commas(lines[0]))
                return dict(zip(keys, map(cls.parse_value, vals)))
            return [
                dict(zip(keys, map(cls.parse_value, cls._split_top_level_commas(ln))))
                for ln in lines
            ]

        # Multiple blocks
        result = {}
        for i, m in enumerate(matches):
            name = m.group(1)
            keys = [k.strip() for k in m.group(2).split(",")]
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            lines = [l.strip() for l in body.splitlines() if l.strip()]

            if len(lines) == 1:
                vals = list(cls._split_top_level_commas(lines[0]))
                result[name] = dict(zip(keys, map(cls.parse_value, vals)))
            else:
                result[name] = [
                    dict(
                        zip(keys, map(cls.parse_value, cls._split_top_level_commas(ln)))
                    )
                    for ln in lines
                ]

        return result


def encode_to_toon(data: dict | list) -> str:
    """
    Convenience function to encode data to TOON format.

    Args:
        data: Python dict or list to encode

    Returns:
        TOON-formatted string
    """
    return ToonEncoder.encode(data)


def decode_from_toon(text: str) -> dict | list | Any:
    """
    Convenience function to decode TOON format to Python data.

    Args:
        text: TOON-formatted string

    Returns:
        Python data structure
    """
    return ToonDecoder.decode(text)


def json_to_toon(json_str: str) -> str:
    """
    Convert JSON string to TOON format.

    Args:
        json_str: JSON-formatted string

    Returns:
        TOON-formatted string
    """
    data = json.loads(json_str)
    return encode_to_toon(data)


def toon_to_json(toon_str: str, indent: int | None = None) -> str:
    """
    Convert TOON string to JSON string.

    Args:
        toon_str: TOON-formatted string
        indent: JSON indentation level

    Returns:
        JSON-formatted string
    """
    data = decode_from_toon(toon_str)
    return json.dumps(data, indent=indent, ensure_ascii=False)


def validate_toon(text: str) -> bool:
    """
    Validate TOON formatted string against the specification.

    Checks:
    1. Headers follow section{key,key} format
    2. Data rows match header column counts
    3. Structural integrity of blocks

    Args:
        text: TOON formatted string

    Returns:
        True if valid, raises ValueError otherwise.
    """
    text = text.strip()
    if not text:
        return True # Empty is valid-ish

    # Check for basic TOON structure (headers)
    header_pattern = re.compile(r"^([a-z_]+)\{([^}]+)\}$", re.MULTILINE)

    lines = text.splitlines()
    current_section = None
    expected_cols = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            current_section = None
            continue

        header_match = header_pattern.match(line)
        if header_match:
            current_section = header_match.group(1)
            keys = header_match.group(2).split(',')
            expected_cols = len(keys)
            continue

        if current_section:
            # Data row validation
            # This is a basic check; robust CSV split needed for production
            # We use the internal decoder logic to counts top-level commas
            cols = list(ToonDecoder._split_top_level_commas(line))
            if len(cols) != expected_cols:
                raise ValueError(f"Section '{current_section}': Row {i+1} has {len(cols)} columns, expected {expected_cols}. Content: {line[:50]}...")

    return True

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="TOON Format Validator & Converter")
    parser.add_argument("file", help="Input file path")
    parser.add_argument("--validate", action="store_true", help="Validate TOON format")
    parser.add_argument("--to-json", action="store_true", help="Convert TOON to JSON")

    args = parser.parse_args()

    try:
        with open(args.file, encoding='utf-8') as f:
            content = f.read()

        if args.validate:
            try:
                if validate_toon(content):
                    print("✅ Valid TOON format")
                    sys.exit(0)
            except ValueError as e:
                print(f"❌ Invalid TOON format: {e}")
                sys.exit(1)

        if args.to_json:
            try:
                print(toon_to_json(content, indent=2))
            except Exception as e:
                print(f"Error converting to JSON: {e}", file=sys.stderr)
                sys.exit(1)

    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
