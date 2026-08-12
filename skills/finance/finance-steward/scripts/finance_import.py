#!/usr/bin/env python3
"""Stage bank exports into portable JSONL using only Python's standard library."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "finance-steward-import-v1"
PARSER_VERSION = "1.0.0"
SUPPORTED_FORMATS = {"csv", "tsv", "xlsx", "ofx", "qfx", "qbo", "qif", "pdf", "text"}
HEADER_ALIASES = {
    "date": {"date", "transaction date", "trans date", "trans. date", "activity date", "posted date", "post date", "posting date", "clearing date"},
    "posted_date": {"posted date", "post date", "posting date", "clearing date"},
    "description": {"description", "merchant", "name", "payee", "memo", "details", "transaction description", "original description"},
    "amount": {"amount", "amount usd", "transaction amount", "net amount"},
    "debit": {"debit", "withdrawal", "withdrawals", "money out", "outflow", "charge"},
    "credit": {"credit", "deposit", "deposits", "money in", "inflow", "payment"},
    "balance": {"balance", "running balance", "available balance"},
    "currency": {"currency", "currency code"},
    "external_id": {"id", "transaction id", "reference", "reference number", "fitid"},
    "status": {"status", "transaction status"},
}
DEFAULT_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m/%d/%Y", "%m/%d/%y",
    "%m-%d-%Y", "%m-%d-%y", "%d/%m/%Y", "%d/%m/%y", "%b %d, %Y",
    "%B %d, %Y", "%b %d %Y", "%d %b %Y",
]
PARTIAL_DATE_FORMATS = ["%m/%d", "%m-%d", "%b %d", "%B %d"]


class ImportFailure(Exception):
    """A safe, user-actionable import failure."""


@dataclass
class ParseResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def safe_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_header(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"[^\w\s.]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_description(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<!\d)\d(?:[ -]?\d){5,}(?!\d)", "[masked-id]", text)


def canonical_description(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).upper()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", text)).strip()


def load_profile(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ImportFailure("profile is not readable valid JSON") from error
    if not isinstance(profile, dict):
        raise ImportFailure("profile root must be a JSON object")
    return profile


def detect_format(path: Path, requested: str) -> str:
    if requested != "auto":
        if requested not in SUPPORTED_FORMATS:
            raise ImportFailure(f"unsupported format: {requested}")
        return requested
    suffix = path.suffix.lower().lstrip(".")
    if suffix in SUPPORTED_FORMATS:
        return suffix
    head = path.read_bytes()[:8192]
    stripped = head.lstrip()
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "xlsx"
    upper = stripped.upper()
    if b"<OFX" in upper or b"OFXHEADER:" in upper:
        return "ofx"
    if stripped.startswith(b"!Type:"):
        return "qif"
    if b"\t" in head and head.count(b"\t") >= head.count(b","):
        return "tsv"
    if b"," in head or b";" in head:
        return "csv"
    return "text"


def decode_text(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    candidates = ([encoding] if encoding else []) + ["utf-8-sig", "utf-16", "cp1252"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return data.decode(candidate), candidate
        except (LookupError, UnicodeDecodeError):
            continue
    raise ImportFailure("text encoding is unsupported; provide --encoding")


def parse_decimal(value: Any) -> Decimal:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not text:
        raise ValueError("empty amount")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"(?i)\b(?:USD|EUR|GBP|CAD|AUD|CNY|RMB)\b", "", text)
    text = text.replace("$", "").replace("£", "").replace("€", "").replace("¥", "").replace(",", "").strip()
    trailing = re.search(r"(?i)\s*(CR|DR)$", text)
    if trailing:
        negative = trailing.group(1).upper() == "DR"
        text = text[: trailing.start()].strip()
    try:
        amount = Decimal(text)
    except InvalidOperation as error:
        raise ValueError("invalid amount") from error
    return -abs(amount) if negative else amount


def decimal_to_minor(value: Decimal, minor_units: int) -> int:
    scale = Decimal(10) ** minor_units
    return int((value * scale).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def parse_date(value: Any, *, formats: list[str] | None = None, statement_end: dt.date | None = None) -> str:
    if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?", value.strip())):
        number = float(value)
        if 20000 <= number <= 80000:
            return (dt.date(1899, 12, 30) + dt.timedelta(days=int(number))).isoformat()
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).strip())
    for date_format in (formats or []) + DEFAULT_DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            pass
    if statement_end:
        for date_format in PARTIAL_DATE_FORMATS:
            try:
                partial = dt.datetime.strptime(text, date_format)
            except ValueError:
                continue
            year = statement_end.year - (1 if partial.month > statement_end.month + 1 else 0)
            return dt.date(year, partial.month, partial.day).isoformat()
    raise ValueError("invalid date")


def column_aliases(profile: dict[str, Any], field_name: str) -> set[str]:
    configured = profile.get("columns", {}).get(field_name, [])
    if isinstance(configured, str):
        configured = [configured]
    return set(HEADER_ALIASES.get(field_name, set())) | {normalized_header(value) for value in configured}


def map_headers(headers: list[Any], profile: dict[str, Any]) -> dict[str, int]:
    normalized = [normalized_header(header) for header in headers]
    mapping: dict[str, int] = {}
    for field_name in HEADER_ALIASES:
        aliases = column_aliases(profile, field_name)
        for index, header in enumerate(normalized):
            if header in aliases:
                mapping[field_name] = index
                break
    return mapping


def apply_sign(value: Decimal, sign_mode: str) -> Decimal:
    if sign_mode == "as-is":
        return value
    if sign_mode == "invert":
        return -value
    raise ImportFailure(f"unsupported sign mode: {sign_mode}")


def row_value(row: list[Any], mapping: dict[str, int], field_name: str) -> Any:
    index = mapping.get(field_name)
    return row[index] if index is not None and index < len(row) else ""


def record_from_fields(
    *, date_value: Any, description_value: Any, source_locator: str, source_sha256: str,
    account_key: str, currency: str, minor_units: int, sign_mode: str,
    amount_value: Any = "", debit_value: Any = "", credit_value: Any = "",
    balance_value: Any = "", posted_date_value: Any = "", external_id_value: Any = "",
    status_value: Any = "", date_formats: list[str] | None = None,
    statement_end: dt.date | None = None,
) -> dict[str, Any]:
    transaction_date = parse_date(date_value, formats=date_formats, statement_end=statement_end)
    description = normalized_description(description_value)
    if not description:
        raise ValueError("empty description")
    if str(amount_value or "").strip():
        amount = parse_decimal(amount_value)
    elif str(debit_value or "").strip() or str(credit_value or "").strip():
        debit = abs(parse_decimal(debit_value)) if str(debit_value or "").strip() else Decimal(0)
        credit = abs(parse_decimal(credit_value)) if str(credit_value or "").strip() else Decimal(0)
        if debit and credit:
            raise ValueError("both debit and credit are populated")
        amount = credit - debit
    else:
        raise ValueError("empty amount")
    amount_minor = decimal_to_minor(apply_sign(amount, sign_mode), minor_units)
    if amount_minor == 0:
        raise ValueError("zero amount")
    posted_date = parse_date(posted_date_value, formats=date_formats, statement_end=statement_end) if str(posted_date_value or "").strip() else None
    balance_minor = decimal_to_minor(parse_decimal(balance_value), minor_units) if str(balance_value or "").strip() else None
    external_id = normalized_description(external_id_value) or None
    normalized_currency = normalized_description(currency).upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized_currency):
        raise ValueError("invalid currency")
    canonical = "|".join([account_key, external_id or "", transaction_date, str(amount_minor), canonical_description(description)])
    return {
        "schema_version": SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "source_locator": source_locator,
        "transaction_date": transaction_date,
        "posted_date": posted_date,
        "description": description,
        "amount_minor": amount_minor,
        "currency": normalized_currency,
        "balance_minor": balance_minor,
        "external_id": external_id,
        "status": normalized_description(status_value).lower() or None,
        "record_hash": sha256_bytes(f"{source_sha256}|{source_locator}|{canonical}".encode()),
        "dedupe_key": sha256_bytes(canonical.encode()),
    }


def rows_to_records(
    rows: list[list[Any]], *, source_sha256: str, profile: dict[str, Any], account_key: str,
    default_currency: str, minor_units: int, sign_mode: str, statement_end: dt.date | None,
    locator_prefix: str,
) -> ParseResult:
    header_index = None
    mapping: dict[str, int] = {}
    for index, row in enumerate(rows[:30]):
        candidate = map_headers(row, profile)
        if "date" in candidate and "description" in candidate and ({"amount", "debit", "credit"} & candidate.keys()):
            header_index, mapping = index, candidate
            break
    if header_index is None:
        raise ImportFailure("no recognized transaction header row; add a column profile")
    result = ParseResult(metadata={"header_row": header_index + 1})
    for index, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(str(value or "").strip() for value in row):
            continue
        try:
            result.records.append(record_from_fields(
                date_value=row_value(row, mapping, "date"), posted_date_value=row_value(row, mapping, "posted_date"),
                description_value=row_value(row, mapping, "description"), amount_value=row_value(row, mapping, "amount"),
                debit_value=row_value(row, mapping, "debit"), credit_value=row_value(row, mapping, "credit"),
                balance_value=row_value(row, mapping, "balance"), external_id_value=row_value(row, mapping, "external_id"),
                status_value=row_value(row, mapping, "status"), source_locator=f"{locator_prefix}:{index}",
                source_sha256=source_sha256, account_key=account_key,
                currency=row_value(row, mapping, "currency") or profile.get("currency") or default_currency,
                minor_units=minor_units, sign_mode=profile.get("sign_mode", sign_mode),
                date_formats=profile.get("date_formats", []), statement_end=statement_end,
            ))
        except ValueError:
            result.warnings.append(f"unparsed-{locator_prefix}-row:{index}")
    if not result.records:
        raise ImportFailure("no valid transaction rows were detected")
    return result


def parse_delimited(path: Path, *, delimiter: str | None, encoding: str | None, **kwargs: Any) -> ParseResult:
    text, used_encoding = decode_text(path.read_bytes(), encoding)
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:65536], delimiters=",\t;|").delimiter
        except csv.Error:
            delimiter = ","
    result = rows_to_records(list(csv.reader(io.StringIO(text), delimiter=delimiter)), locator_prefix="row", **kwargs)
    result.metadata.update({"encoding": used_encoding, "delimiter": delimiter})
    return result


def xlsx_column_index(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference.upper())
    value = 0
    for char in match.group(0) if match else "A":
        value = value * 26 + ord(char) - 64
    return value - 1


def parse_xlsx(path: Path, **kwargs: Any) -> ParseResult:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise ImportFailure("XLSX container is invalid") from error
    with archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in root]
        sheets = sorted(name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
        if not sheets:
            raise ImportFailure("XLSX has no worksheets")
        root = ET.fromstring(archive.read(sheets[0]))
        rows: list[list[Any]] = []
        for row_node in (node for node in root.iter() if node.tag.endswith("}row")):
            values: dict[int, Any] = {}
            for cell in (node for node in row_node if node.tag.endswith("}c")):
                column = xlsx_column_index(cell.attrib.get("r", "A1"))
                cell_type = cell.attrib.get("t")
                value_node = next((node for node in cell if node.tag.endswith("}v")), None)
                if cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                elif value_node is None:
                    value = ""
                elif cell_type == "s":
                    index = int(value_node.text or 0)
                    value = shared[index] if index < len(shared) else ""
                else:
                    value = value_node.text or ""
                values[column] = value
            if values:
                row = [""] * (max(values) + 1)
                for column, value in values.items():
                    row[column] = value
                rows.append(row)
        result = rows_to_records(rows, locator_prefix=f"{sheets[0]}-row", **kwargs)
        result.metadata["worksheet"] = sheets[0]
        return result


def ofx_tag(block: str, tag: str) -> str:
    match = re.search(rf"(?is)<{re.escape(tag)}>\s*([^<\r\n]+)", block)
    return match.group(1).strip() if match else ""


def parse_ofx(path: Path, *, encoding: str | None, source_sha256: str, profile: dict[str, Any], account_key: str, default_currency: str, minor_units: int, sign_mode: str, **_: Any) -> ParseResult:
    text, used_encoding = decode_text(path.read_bytes(), encoding)
    currency = ofx_tag(text, "CURDEF") or profile.get("currency") or default_currency
    blocks = re.findall(r"(?is)<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>|</BANKTRANLIST>|</CCSTMTRS>))", text)
    result = ParseResult(metadata={"encoding": used_encoding})
    for index, block in enumerate(blocks, start=1):
        date_text = ofx_tag(block, "DTPOSTED")[:8]
        description = " ".join(filter(None, [ofx_tag(block, "NAME"), ofx_tag(block, "MEMO")]))
        try:
            result.records.append(record_from_fields(
                date_value=date_text, posted_date_value=date_text,
                description_value=description or ofx_tag(block, "TRNTYPE"), amount_value=ofx_tag(block, "TRNAMT"),
                external_id_value=ofx_tag(block, "FITID"), status_value="posted", source_locator=f"stmttrn:{index}",
                source_sha256=source_sha256, account_key=account_key, currency=currency, minor_units=minor_units,
                sign_mode=profile.get("sign_mode", sign_mode), date_formats=["%Y%m%d"],
            ))
        except ValueError:
            result.warnings.append(f"unparsed-stmttrn:{index}")
    if not result.records:
        raise ImportFailure("no valid OFX transactions were detected")
    return result


def parse_qif(path: Path, *, encoding: str | None, source_sha256: str, profile: dict[str, Any], account_key: str, default_currency: str, minor_units: int, sign_mode: str, statement_end: dt.date | None, **_: Any) -> ParseResult:
    text, used_encoding = decode_text(path.read_bytes(), encoding)
    result = ParseResult(metadata={"encoding": used_encoding})
    for index, block in enumerate(text.split("^"), start=1):
        fields: dict[str, list[str]] = {}
        for line in block.splitlines():
            if line and not line.startswith("!"):
                fields.setdefault(line[0], []).append(line[1:].strip())
        if "D" not in fields or "T" not in fields:
            continue
        description = " ".join(filter(None, [(fields.get("P") or [""])[0], (fields.get("M") or [""])[0]]))
        try:
            result.records.append(record_from_fields(
                date_value=fields["D"][0].replace("'", "/"), description_value=description or "QIF transaction",
                amount_value=fields["T"][0], external_id_value=(fields.get("N") or [""])[0],
                source_locator=f"record:{index}", source_sha256=source_sha256, account_key=account_key,
                currency=profile.get("currency") or default_currency, minor_units=minor_units,
                sign_mode=profile.get("sign_mode", sign_mode), date_formats=profile.get("date_formats", []),
                statement_end=statement_end,
            ))
        except ValueError:
            result.warnings.append(f"unparsed-record:{index}")
    if not result.records:
        raise ImportFailure("no valid QIF transactions were detected")
    return result


def decode_pdf_string(value: bytes) -> str:
    output = bytearray()
    index = 0
    while index < len(value):
        if value[index] != 92:
            output.append(value[index]); index += 1; continue
        index += 1
        if index >= len(value):
            break
        escaped = value[index]
        replacements = {110: 10, 114: 13, 116: 9, 98: 8, 102: 12}
        if escaped in replacements:
            output.append(replacements[escaped]); index += 1
        elif 48 <= escaped <= 55:
            match = re.match(rb"[0-7]{1,3}", value[index:])
            assert match is not None
            output.append(int(match.group(0), 8)); index += len(match.group(0))
        elif escaped in (10, 13):
            index += 1
            if escaped == 13 and index < len(value) and value[index] == 10:
                index += 1
        else:
            output.append(escaped); index += 1
    data = bytes(output)
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be", errors="replace")
    if len(data) >= 4 and data.count(b"\x00") > len(data) // 4:
        return data.decode("utf-16-be", errors="replace")
    return data.decode("utf-8", errors="replace")


def pdf_text_operand(token: bytes) -> str:
    token = token.strip()
    if token.startswith(b"(") and token.endswith(b")"):
        return decode_pdf_string(token[1:-1])
    if token.startswith(b"<") and token.endswith(b">") and not token.startswith(b"<<"):
        try:
            return decode_pdf_string(bytes.fromhex(re.sub(rb"\s+", b"", token[1:-1]).decode("ascii")))
        except (ValueError, UnicodeDecodeError):
            return ""
    if token.startswith(b"["):
        pieces = re.findall(rb"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]+>", token)
        return "".join(pdf_text_operand(piece) for piece in pieces)
    return ""


def extract_pdf_text(path: Path) -> tuple[str, dict[str, Any]]:
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ImportFailure("file is not a PDF")
    if b"/Encrypt" in data:
        raise ImportFailure("encrypted PDF is unsupported; export an unlocked copy")
    chunks: list[tuple[float, float, int, str]] = []
    sequence = 0
    for stream_match in re.finditer(rb"stream\r?\n", data):
        end = data.find(b"endstream", stream_match.end())
        if end < 0:
            continue
        dictionary = data[max(0, stream_match.start() - 4096) : stream_match.start()]
        stream = data[stream_match.end() : end].rstrip(b"\r\n")
        if b"/FlateDecode" in dictionary:
            try:
                stream = zlib.decompress(stream)
            except zlib.error:
                continue
        for block in re.findall(rb"BT(.*?)ET", stream, flags=re.S):
            x, y = 0.0, float(-sequence)
            tokens = re.compile(
                rb"(-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+Tm)"
                rb"|(\[(?:\\.|[^\]])*\]|\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]+>)\s*(?:Tj|'|\")"
            )
            for match in tokens.finditer(block):
                if match.group(1):
                    numbers = re.findall(rb"-?\d+(?:\.\d+)?", match.group(1))
                    if len(numbers) >= 6:
                        x, y = float(numbers[-2]), float(numbers[-1])
                else:
                    text = normalized_description(pdf_text_operand(match.group(4)))
                    if text:
                        chunks.append((y, x, sequence, text)); x += max(1, len(text)); sequence += 1
    if not chunks:
        raise ImportFailure("PDF text layer could not be decoded by the bundled extractor")
    grouped: dict[tuple[int, int], list[tuple[float, str]]] = {}
    for y, x, sequence, text in chunks:
        grouped.setdefault((sequence // 10000, round(y * 2)), []).append((x, text))
    lines = [" ".join(text for _, text in sorted(grouped[key])) for key in sorted(grouped, key=lambda item: (item[0], -item[1]))]
    text = "\n".join(lines)
    printable_ratio = sum(char.isprintable() or char in "\r\n\t" for char in text) / max(1, len(text))
    if printable_ratio < 0.85:
        raise ImportFailure("PDF text layer quality is too low for deterministic parsing")
    return text, {"extractor": "bundled-pdf-text-v1", "text_line_count": len(lines)}


def parse_profiled_text(
    text: str, *, source_sha256: str, profile: dict[str, Any], account_key: str,
    default_currency: str, minor_units: int, sign_mode: str, statement_end: dt.date | None,
) -> ParseResult:
    if not profile.get("line_pattern"):
        raise ImportFailure("PDF/text input requires a profile with line_pattern")
    try:
        pattern = re.compile(profile["line_pattern"], flags=re.I)
    except re.error as error:
        raise ImportFailure("profile line_pattern is invalid") from error
    result = ParseResult()
    section: dict[str, Any] | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        for marker in profile.get("section_markers", []):
            if re.search(marker["pattern"], line, flags=re.I):
                section = marker
        match = pattern.match(line)
        if not match:
            continue
        fields = match.groupdict()
        date_value = fields.get("date") or (f"{fields.get('month')}/{fields.get('day')}" if fields.get("month") and fields.get("day") else "")
        try:
            result.records.append(record_from_fields(
                date_value=date_value, posted_date_value=fields.get("posted_date", ""),
                description_value=fields.get("description", ""), amount_value=fields.get("amount", ""),
                debit_value=fields.get("debit", ""), credit_value=fields.get("credit", ""),
                balance_value=fields.get("balance", ""), external_id_value=fields.get("external_id", ""),
                source_locator=f"line:{line_number}", source_sha256=source_sha256, account_key=account_key,
                currency=fields.get("currency") or profile.get("currency") or default_currency,
                minor_units=minor_units, sign_mode=(section or {}).get("sign_mode", profile.get("sign_mode", sign_mode)),
                date_formats=profile.get("date_formats", []), statement_end=statement_end,
            ))
        except ValueError:
            result.warnings.append(f"unparsed-matched-line:{line_number}")
    if not result.records:
        raise ImportFailure("profile matched no valid transaction lines")
    return result


def validate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    record_hashes: set[str] = set()
    dedupe_counts: dict[str, int] = {}
    currencies: set[str] = set()
    for index, record in enumerate(records, start=1):
        prefix = f"record:{index}"
        if record.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{prefix}:schema-version")
        try:
            dt.date.fromisoformat(record["transaction_date"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{prefix}:transaction-date")
        if not isinstance(record.get("amount_minor"), int) or record.get("amount_minor") == 0:
            errors.append(f"{prefix}:amount-minor")
        if not normalized_description(record.get("description")):
            errors.append(f"{prefix}:description")
        currency = str(record.get("currency", ""))
        if not re.fullmatch(r"[A-Z]{3}", currency):
            errors.append(f"{prefix}:currency")
        else:
            currencies.add(currency)
        record_hash = str(record.get("record_hash", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", record_hash) or record_hash in record_hashes:
            errors.append(f"{prefix}:record-hash")
        record_hashes.add(record_hash)
        dedupe_key = str(record.get("dedupe_key", ""))
        dedupe_counts[dedupe_key] = dedupe_counts.get(dedupe_key, 0) + 1
    duplicates = sum(1 for count in dedupe_counts.values() if count > 1)
    return {
        "record_count": len(records), "error_count": len(errors),
        "duplicate_dedupe_key_count": duplicates, "currency_count": len(currencies),
        "status": "valid" if not errors and not duplicates else "needs_review", "errors": errors[:20],
    }


def parse_source(args: argparse.Namespace, path: Path, source_sha256: str, profile: dict[str, Any]) -> tuple[str, ParseResult]:
    file_format = detect_format(path, args.format)
    common = {
        "source_sha256": source_sha256, "profile": profile, "account_key": args.account_key,
        "default_currency": args.currency, "minor_units": args.minor_units, "sign_mode": args.sign_mode,
        "statement_end": dt.date.fromisoformat(args.statement_end) if args.statement_end else None,
    }
    if file_format in {"csv", "tsv"}:
        result = parse_delimited(path, delimiter="\t" if file_format == "tsv" else args.delimiter, encoding=args.encoding, **common)
    elif file_format == "xlsx":
        result = parse_xlsx(path, **common)
    elif file_format in {"ofx", "qfx", "qbo"}:
        result = parse_ofx(path, encoding=args.encoding, **common)
    elif file_format == "qif":
        result = parse_qif(path, encoding=args.encoding, **common)
    elif file_format == "pdf":
        text, metadata = extract_pdf_text(path)
        result = parse_profiled_text(text, **common); result.metadata.update(metadata)
    elif file_format == "text":
        text, used_encoding = decode_text(path.read_bytes(), args.encoding)
        result = parse_profiled_text(text, **common); result.metadata["encoding"] = used_encoding
    else:
        raise ImportFailure(f"unsupported format: {file_format}")
    return file_format, result


def write_jsonl_atomic(path: Path, records: Iterable[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)
    return sha256_file(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ImportFailure(f"JSONL line {line_number} is not an object")
                    records.append(value)
    except (OSError, json.JSONDecodeError) as error:
        raise ImportFailure("staging JSONL is unreadable or invalid") from error
    return records


def command_inspect(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        raise ImportFailure("input file does not exist")
    file_format = detect_format(path, args.format)
    safe_json({"format": file_format, "profile_required": file_format in {"pdf", "text"}, "sha256": sha256_file(path), "size_bytes": path.stat().st_size, "status": "inspect_ok"})
    return 0


def command_stage(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not path.is_file():
        raise ImportFailure("input file does not exist")
    if output == path:
        raise ImportFailure("output must not overwrite the source file")
    profile = load_profile(Path(args.profile).expanduser().resolve() if args.profile else None)
    source_sha256 = sha256_file(path)
    file_format, parsed = parse_source(args, path, source_sha256, profile)
    validation = validate_records(parsed.records)
    status = "needs_review" if parsed.warnings or validation["status"] != "valid" else "staged"
    output_sha256 = write_jsonl_atomic(output, parsed.records)
    manifest = {
        "schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "source_sha256": source_sha256,
        "source_format": file_format, "profile_name": profile.get("name"),
        "account_key_hash": sha256_bytes(args.account_key.encode()), "sign_mode": profile.get("sign_mode", args.sign_mode),
        "record_count": len(parsed.records), "warning_count": len(parsed.warnings), "warning_codes": parsed.warnings[:20],
        "validation": validation, "parser_metadata": parsed.metadata, "output_sha256": output_sha256, "status": status,
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    safe_json({"format": file_format, "record_count": len(parsed.records), "warning_count": len(parsed.warnings), "duplicate_dedupe_key_count": validation["duplicate_dedupe_key_count"], "output": str(output), "manifest": str(manifest_path), "status": status})
    return 0 if status == "staged" else 2


def command_validate(args: argparse.Namespace) -> int:
    validation = validate_records(read_jsonl(Path(args.path).expanduser().resolve()))
    safe_json(validation)
    return 0 if validation["status"] == "valid" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage bank exports without external services or workspace tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Detect format without printing transactions.")
    inspect_parser.add_argument("path"); inspect_parser.add_argument("--format", choices=["auto", *sorted(SUPPORTED_FORMATS)], default="auto"); inspect_parser.set_defaults(handler=command_inspect)
    stage_parser = subparsers.add_parser("stage", help="Parse one file into canonical JSONL.")
    stage_parser.add_argument("path"); stage_parser.add_argument("--output", required=True)
    stage_parser.add_argument("--format", choices=["auto", *sorted(SUPPORTED_FORMATS)], default="auto")
    stage_parser.add_argument("--profile", help="JSON profile for custom columns or PDF/text rows.")
    stage_parser.add_argument("--account-key", default="unspecified", help="Opaque local account key used only in dedupe hashing.")
    stage_parser.add_argument("--currency", default="USD"); stage_parser.add_argument("--minor-units", type=int, choices=range(0, 9), default=2)
    stage_parser.add_argument("--sign-mode", choices=["as-is", "invert"], default="as-is")
    stage_parser.add_argument("--statement-end", help="YYYY-MM-DD for rows without a year.")
    stage_parser.add_argument("--delimiter", help="Override CSV delimiter."); stage_parser.add_argument("--encoding")
    stage_parser.set_defaults(handler=command_stage)
    validate_parser = subparsers.add_parser("validate", help="Validate canonical JSONL without printing transactions.")
    validate_parser.add_argument("path"); validate_parser.set_defaults(handler=command_validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (ImportFailure, ValueError) as error:
        safe_json({"status": "failed", "error": str(error)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
