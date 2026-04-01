#!/usr/bin/env python3
"""Align a simple C/C++ declaration or assignment block around a cursor line."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass


BLOCKED_PREFIXES = {
    "break",
    "co_return",
    "continue",
    "delete",
    "goto",
    "return",
    "throw",
}

IDENTIFIER_AT_END_RE = re.compile(r"([A-Za-z_]\w*(?:\s*\[[^\]]*\])*)\s*$")
SINGLE_EQUALS_RE = re.compile(r"(?<![=!<>+\-*/%&|^])=(?![=])")


@dataclass
class ParsedLine:
    index: int
    indent: str
    prefix: str
    name: str
    left: str
    suffix: str
    has_assignment: bool


def leading_whitespace(text: str) -> str:
    return text[: len(text) - len(text.lstrip(" \t"))]


def is_block_line(text: str, indent: str) -> bool:
    if not text.strip():
        return False

    if leading_whitespace(text) != indent:
        return False

    stripped = text.strip()
    if stripped.startswith(("#", "//", "/*", "*")):
        return False

    return True


def has_top_level_comma(text: str) -> bool:
    depth = 0
    in_string = ""
    escaped = False

    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = ""
            continue

        if char in {'"', "'"}:
            in_string = char
            continue

        if char in "([{<":
            depth += 1
            continue

        if char in ")]}>":
            depth = max(0, depth - 1)
            continue

        if char == "," and depth == 0:
            return True

    return False


def split_assignment(text: str) -> tuple[str, str] | None:
    match = SINGLE_EQUALS_RE.search(text)
    if not match:
        return None
    return text[: match.start()], text[match.end() :]


def parse_line(index: int, text: str, indent: str) -> ParsedLine | None:
    if not is_block_line(text, indent):
        return None

    line_ending = ""
    if text.endswith("\r\n"):
        line_ending = "\r\n"
        body = text[len(indent) : -2]
    elif text.endswith("\n"):
        line_ending = "\n"
        body = text[len(indent) : -1]
    else:
        body = text[len(indent) :]

    assignment = split_assignment(body)

    if assignment is None:
        semicolon_index = body.find(";")
        if semicolon_index < 0:
            return None
        left_expr = body[:semicolon_index].rstrip()
        suffix = body[semicolon_index:] + line_ending
        has_assignment = False
    else:
        left_expr = assignment[0].rstrip()
        assignment_tail = assignment[1].strip()
        suffix = f" = {assignment_tail}{line_ending}"
        has_assignment = True

    if not left_expr:
        return None

    if has_top_level_comma(left_expr):
        return None

    if "(" in left_expr or ")" in left_expr:
        return None

    identifier = IDENTIFIER_AT_END_RE.search(left_expr)
    if not identifier:
        return None

    prefix = left_expr[: identifier.start()].rstrip()
    name = left_expr[identifier.start() :].lstrip()

    if not has_assignment and not prefix:
        return None

    first_word = prefix.split(None, 1)[0] if prefix else ""
    if first_word in BLOCKED_PREFIXES:
        return None

    return ParsedLine(
        index=index,
        indent=indent,
        prefix=prefix,
        name=name,
        left="",
        suffix=suffix,
        has_assignment=has_assignment,
    )


def collect_block(lines: list[str], cursor_index: int) -> list[int]:
    if cursor_index < 0 or cursor_index >= len(lines):
        return []

    anchor = lines[cursor_index]
    if not anchor.strip():
        return []

    indent = leading_whitespace(anchor)
    if not is_block_line(anchor, indent):
        return []

    start = cursor_index
    while start > 0 and is_block_line(lines[start - 1], indent):
        start -= 1

    end = cursor_index
    while end + 1 < len(lines) and is_block_line(lines[end + 1], indent):
        end += 1

    return list(range(start, end + 1))


def align_block(lines: list[str], cursor_line_number: int) -> bool:
    cursor_index = cursor_line_number - 1
    block_indexes = collect_block(lines, cursor_index)
    if not block_indexes:
        return False

    indent = leading_whitespace(lines[cursor_index])
    parsed = [parse_line(index, lines[index], indent) for index in block_indexes]
    parsed_lines = [line for line in parsed if line is not None]

    if len(parsed_lines) < 2:
        return False

    max_prefix = max(len(line.prefix) for line in parsed_lines)
    for line in parsed_lines:
        if max_prefix == 0:
            line.left = line.name
        elif line.prefix:
            line.left = f"{line.prefix.ljust(max_prefix)} {line.name}"
        else:
            line.left = f"{' ' * (max_prefix + 1)}{line.name}"

    if any(line.has_assignment for line in parsed_lines):
        max_left = max(len(line.left) for line in parsed_lines if line.has_assignment)
    else:
        max_left = 0

    changed = False
    for line in parsed_lines:
        left = line.left
        if line.has_assignment:
            left = left.ljust(max_left)
        new_text = f"{line.indent}{left}{line.suffix}"
        if new_text != lines[line.index]:
            lines[line.index] = new_text
            changed = True

    return changed


def main() -> int:
    if len(sys.argv) != 2:
        return 2

    try:
        cursor_line_number = int(sys.argv[1])
    except ValueError:
        return 2

    original = sys.stdin.read()
    lines = original.splitlines(keepends=True)

    if original and not lines:
        lines = [original]

    if not align_block(lines, cursor_line_number):
        sys.stdout.write(original)
        return 0

    sys.stdout.write("".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
