from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedCsv:
    headers: list[str]
    rows: list[list[str]]


def _parse_csv_line(line: str) -> list[str]:
    values: list[str] = []
    current = ""
    in_quotes = False
    index = 0

    while index < len(line):
        char = line[index]

        if char == '"':
            if in_quotes and index + 1 < len(line) and line[index + 1] == '"':
                current += '"'
                index += 2
                continue
            in_quotes = not in_quotes
            index += 1
            continue

        if char == "," and not in_quotes:
            values.append(current.strip())
            current = ""
            index += 1
            continue

        current += char
        index += 1

    values.append(current.strip())
    return values


def parse_csv(content: str) -> ParsedCsv:
    lines = [
        line.strip()
        for line in content.replace("\ufeff", "").splitlines()
        if line.strip()
    ]

    if not lines:
        return ParsedCsv(headers=[], rows=[])

    headers = [
        header.replace('"', "").strip()
        for header in _parse_csv_line(lines[0])
    ]
    rows = [_parse_csv_line(line) for line in lines[1:]]

    return ParsedCsv(headers=headers, rows=rows)


def normalize_header(header: str) -> str:
    normalized = "".join(
        "_" if not char.isalnum() else char.lower() for char in header
    )
    return normalized.strip("_")


def row_to_record(headers: list[str], row: list[str]) -> dict[str, str]:
    record: dict[str, str] = {}

    for index, header in enumerate(headers):
        value = row[index] if index < len(row) else ""
        record[normalize_header(header)] = value.replace('"', "").strip()

    return record
