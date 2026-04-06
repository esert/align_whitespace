#!/usr/bin/env python3
"""Align C/C++ declaration, assignment, call, and macro blocks around a cursor line."""

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

CONTROL_PREFIXES = BLOCKED_PREFIXES | {
    "catch",
    "do",
    "else",
    "for",
    "if",
    "switch",
    "while",
}

IDENTIFIER_AT_END_RE = re.compile(r"([A-Za-z_]\w*(?:\s*\[[^\]]*\])*)\s*$")


@dataclass
class DelimitedExpr:
    head: str
    open_char: str
    close_char: str
    items: list[str]
    tail: str


@dataclass
class Declaration:
    prefix: str
    name: str
    terminator: str
    assignment_op: str | None
    rhs: str | None
    rhs_expr: DelimitedExpr | None
    rendered_left: str | None = None
    rendered_rhs: str | None = None


@dataclass
class ParsedLine:
    index: int
    indent: str
    line_ending: str
    comment: str
    continuation: bool
    original_code: str
    declaration: Declaration | None = None
    expr: DelimitedExpr | None = None
    rendered_expr: str | None = None
    rebuild: bool = False
    backslash_padding: int = 0


@dataclass
class Block:
    indexes: list[int]
    is_macro: bool


def leading_whitespace(text: str) -> str:
    return text[: len(text) - len(text.lstrip(" \t"))]


def split_line(text: str) -> tuple[str, str]:
    if text.endswith("\r\n"):
        return text[:-2], "\r\n"
    if text.endswith("\n"):
        return text[:-1], "\n"
    return text, ""


def is_block_line(text: str, indent: str) -> bool:
    if not text.strip():
        return False

    if leading_whitespace(text) != indent:
        return False

    stripped = text.strip()
    if stripped.startswith(("#", "//", "/*", "*")):
        return False

    return True


def line_has_continuation(text: str) -> bool:
    body, _ = split_line(text)
    return body.rstrip().endswith("\\")


def is_identifier_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def next_nonspace_char(text: str, index: int) -> str:
    for next_index in range(index + 1, len(text)):
        char = text[next_index]
        if not char.isspace():
            return char
    return ""


def can_open_angle(text: str, index: int) -> bool:
    if index == 0 or text[index - 1].isspace():
        return False

    prev_char = text[index - 1]
    next_char = next_nonspace_char(text, index)
    if not next_char:
        return False

    if not (is_identifier_char(prev_char) or prev_char in ">:])"):
        return False

    return is_identifier_char(next_char) or next_char in ":<"


def pop_matching_delimiter(stack: list[str], char: str) -> None:
    if not stack:
        return

    expected = {"(": ")", "[": "]", "{": "}", "<": ">"}[stack[-1]]
    if char == expected:
        stack.pop()


def find_comment_start(text: str) -> int | None:
    in_string = ""
    escaped = False

    for index, char in enumerate(text):
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

        if char == "/" and index + 1 < len(text) and text[index + 1] in {"/", "*"}:
            return index

    return None


def split_trailing_comment(text: str) -> tuple[str, str]:
    comment_index = find_comment_start(text)
    if comment_index is None:
        return text.rstrip(), ""
    return text[:comment_index].rstrip(), text[comment_index:].strip()


def split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    in_string = ""
    escaped = False

    for index, char in enumerate(text):
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

        if char in "([{":
            stack.append(char)
            continue

        if char == "<" and can_open_angle(text, index):
            stack.append(char)
            continue

        if char in ")]}":
            pop_matching_delimiter(stack, char)
            continue

        if char == ">" and stack and stack[-1] == "<":
            stack.pop()
            continue

        if char == delimiter and not stack:
            parts.append(text[start:index].strip())
            start = index + 1

    parts.append(text[start:].strip())
    return parts


def has_top_level_comma(text: str) -> bool:
    return len(split_top_level(text, ",")) > 1


ASSIGNMENT_OPERATORS = ("<<=", ">>=", "+=", "-=", "*=", "/=", "%=", "&=", "^=", "|=")


def split_assignment(text: str) -> tuple[str, str, str] | None:
    stack: list[str] = []
    in_string = ""
    escaped = False

    for index, char in enumerate(text):
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

        if char in "([{":
            stack.append(char)
            continue

        if char == "<" and can_open_angle(text, index):
            stack.append(char)
            continue

        if char in ")]}":
            pop_matching_delimiter(stack, char)
            continue

        if char == ">" and stack and stack[-1] == "<":
            stack.pop()
            continue

        if char != "=" or stack:
            continue

        prev_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if next_char == "=":
            continue

        for operator in ASSIGNMENT_OPERATORS:
            start = index - len(operator) + 1
            if start < 0:
                continue
            if text[start : index + 1] != operator:
                continue
            return text[:start], operator, text[index + 1 :]

        if prev_char in "=!<>":
            continue

        return text[:index], "=", text[index + 1 :]

    return None


def get_trailing_terminator(text: str, terminators: set[str]) -> tuple[str, str] | None:
    stripped = text.rstrip()
    if not stripped or stripped[-1] not in terminators:
        return None

    end_index = len(stripped) - 1
    stack: list[str] = []
    in_string = ""
    escaped = False

    for index, char in enumerate(stripped):
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

        if char in "([{":
            stack.append(char)
            continue

        if char == "<" and can_open_angle(stripped, index):
            stack.append(char)
            continue

        if char in ")]}":
            pop_matching_delimiter(stack, char)
            continue

        if char == ">" and stack and stack[-1] == "<":
            stack.pop()
            continue

        if index == end_index and char in terminators and not stack:
            return stripped[:index].rstrip(), char

    return None


def find_matching_close(text: str, open_index: int) -> int | None:
    open_char = text[open_index]
    close_char = {"(": ")", "{": "}", "[": "]"}[open_char]
    stack: list[str] = [open_char]
    in_string = ""
    escaped = False

    for index in range(open_index + 1, len(text)):
        char = text[index]
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

        if char in "([{":
            stack.append(char)
            continue

        if char == "<" and can_open_angle(text, index):
            stack.append(char)
            continue

        if char == ">" and stack and stack[-1] == "<":
            stack.pop()
            continue

        if char in ")]}":
            if not stack:
                continue
            top = stack[-1]
            expected = {"(": ")", "{": "}", "[": "]", "<": ">"}[top]
            if char == expected:
                stack.pop()
                if not stack:
                    return index

    return None


def parse_delimited_expr(text: str) -> DelimitedExpr | None:
    stripped = text.strip()
    if not stripped:
        return None

    stack: list[str] = []
    in_string = ""
    escaped = False

    for index, char in enumerate(stripped):
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

        if char in "([{":
            if stack:
                stack.append(char)
                continue

            close_index = find_matching_close(stripped, index)
            if close_index is None:
                return None

            head = stripped[:index].rstrip()
            tail = stripped[close_index + 1 :].strip()
            if tail not in {"", ",", ";"}:
                return None

            if not head and char != "{":
                return None

            first_word = head.split(None, 1)[0] if head else ""
            if first_word in CONTROL_PREFIXES:
                return None

            inner = stripped[index + 1 : close_index]
            items = [] if not inner.strip() else split_top_level(inner, ",")
            return DelimitedExpr(
                head=head,
                open_char=char,
                close_char={"(": ")", "{": "}", "[": "]"}[char],
                items=items,
                tail=tail,
            )

        if char == "<" and can_open_angle(stripped, index):
            stack.append(char)
            continue

        if char == ">" and stack and stack[-1] == "<":
            stack.pop()

    return None


def parse_declaration(text: str) -> Declaration | None:
    stripped = text.strip()
    if not stripped:
        return None

    terminator_info = get_trailing_terminator(stripped, {",", ";"})
    if terminator_info is None:
        body = stripped
        terminator = ""
    else:
        body, terminator = terminator_info

    assignment = split_assignment(body)
    if assignment is None:
        if not terminator:
            return None
        left_expr = body.rstrip()
        assignment_op = None
        rhs = None
    else:
        left_expr = assignment[0].rstrip()
        assignment_op = assignment[1]
        rhs = assignment[2].strip()
        if not rhs:
            return None

    if not left_expr:
        return None

    if has_top_level_comma(left_expr):
        return None

    if assignment is not None and not any(char.isspace() for char in left_expr):
        return Declaration(
            prefix="",
            name=left_expr,
            terminator=terminator,
            assignment_op=assignment_op,
            rhs=rhs,
            rhs_expr=parse_delimited_expr(rhs),
        )

    if "(" in left_expr or ")" in left_expr:
        return None

    identifier = IDENTIFIER_AT_END_RE.search(left_expr)
    if not identifier:
        return None

    prefix = left_expr[: identifier.start()].rstrip()
    name = left_expr[identifier.start() :].lstrip()

    if assignment is None and not prefix:
        return None

    first_word = prefix.split(None, 1)[0] if prefix else ""
    if first_word in BLOCKED_PREFIXES:
        return None

    return Declaration(
        prefix=prefix,
        name=name,
        terminator=terminator,
        assignment_op=assignment_op,
        rhs=rhs,
        rhs_expr=parse_delimited_expr(rhs) if rhs is not None else None,
    )


def parse_line(index: int, text: str) -> ParsedLine | None:
    full_body, line_ending = split_line(text)
    indent = leading_whitespace(full_body)
    body = full_body[len(indent) :]
    if not body.strip():
        return None

    stripped = body.strip()
    if stripped.startswith(("//", "/*", "*")):
        return None

    continuation = body.rstrip().endswith("\\")
    if continuation:
        body = body.rstrip()
        body = body[:-1].rstrip()

    code, comment = split_trailing_comment(body)
    if not code and not comment:
        return None

    parsed = ParsedLine(
        index=index,
        indent=indent,
        line_ending=line_ending,
        comment=comment,
        continuation=continuation,
        original_code=code,
    )

    parsed.declaration = parse_declaration(code)
    if parsed.declaration is None:
        parsed.expr = parse_delimited_expr(code)

    return parsed


def collect_macro_block(lines: list[str], cursor_index: int) -> list[int]:
    if cursor_index < 0 or cursor_index >= len(lines):
        return []

    start = cursor_index
    while start > 0 and line_has_continuation(lines[start - 1]):
        start -= 1

    if not lines[start].lstrip().startswith("#define"):
        return []

    end = start
    while end + 1 < len(lines) and line_has_continuation(lines[end]):
        end += 1

    if end == start:
        return []

    return list(range(start, end + 1))


def collect_normal_block(lines: list[str], cursor_index: int) -> list[int]:
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


def collect_block(lines: list[str], cursor_index: int) -> Block:
    macro_indexes = collect_macro_block(lines, cursor_index)
    if macro_indexes:
        return Block(indexes=macro_indexes, is_macro=True)

    return Block(indexes=collect_normal_block(lines, cursor_index), is_macro=False)


def format_default_left(declaration: Declaration) -> str:
    if declaration.prefix:
        return f"{declaration.prefix} {declaration.name}"
    return declaration.name


def build_declaration_code(declaration: Declaration) -> str:
    left = declaration.rendered_left or format_default_left(declaration)
    if declaration.rhs is None:
        return f"{left}{declaration.terminator}"

    rhs = declaration.rendered_rhs or declaration.rhs
    return f"{left} {declaration.assignment_op} {rhs}{declaration.terminator}"


def build_base_code(parsed: ParsedLine) -> str:
    if parsed.declaration is not None:
        return build_declaration_code(parsed.declaration)
    if parsed.rendered_expr is not None:
        return parsed.rendered_expr
    return parsed.original_code


def render_line(parsed: ParsedLine) -> str:
    text = f"{parsed.indent}{build_base_code(parsed)}"
    if parsed.comment:
        text += f" {parsed.comment}"
    if parsed.continuation:
        text += " " * parsed.backslash_padding
        text += "\\"
    return text + parsed.line_ending


def alignment_family(parsed: ParsedLine | None) -> str | None:
    if parsed is None:
        return None

    declaration = parsed.declaration
    if declaration is not None:
        if declaration.assignment_op is not None and not declaration.prefix:
            return "assignment"
        return "default"

    if parsed.expr is not None:
        return "default"

    return None


def collect_active_run(
    parsed_lines: list[ParsedLine | None],
    block_indexes: list[int],
    cursor_index: int,
) -> list[ParsedLine]:
    if cursor_index not in block_indexes:
        return []

    cursor_pos = block_indexes.index(cursor_index)
    family = alignment_family(parsed_lines[cursor_pos])
    if family is None:
        return []

    start = cursor_pos
    while start > 0 and alignment_family(parsed_lines[start - 1]) == family:
        start -= 1

    end = cursor_pos
    while end + 1 < len(parsed_lines) and alignment_family(parsed_lines[end + 1]) == family:
        end += 1

    return [line for line in parsed_lines[start : end + 1] if line is not None]


def align_declarations(lines: list[ParsedLine]) -> None:
    declaration_lines = [line for line in lines if line.declaration is not None]
    if len(declaration_lines) < 2:
        return

    max_prefix = max(len(line.declaration.prefix) for line in declaration_lines)
    for line in declaration_lines:
        declaration = line.declaration
        if max_prefix == 0 or not declaration.prefix:
            declaration.rendered_left = declaration.name
        else:
            declaration.rendered_left = f"{declaration.prefix.ljust(max_prefix)} {declaration.name}"
        line.rebuild = True

    assignment_lines = [line for line in declaration_lines if line.declaration.rhs is not None]
    if not assignment_lines:
        return

    max_left = max(len(line.declaration.rendered_left or format_default_left(line.declaration)) for line in assignment_lines)
    max_eq_index = max((line.declaration.assignment_op or "=").index("=") for line in assignment_lines)
    for line in assignment_lines:
        declaration = line.declaration
        eq_index = (declaration.assignment_op or "=").index("=")
        left_width = max_left + max_eq_index - eq_index
        declaration.rendered_left = (declaration.rendered_left or format_default_left(declaration)).ljust(left_width)


def expr_group_key(expr: DelimitedExpr) -> tuple[str, str, str, str]:
    return (expr.head, expr.open_char, expr.close_char, expr.tail)


def render_delimited_expr(expr: DelimitedExpr, widths: list[int], pad_last_item: bool) -> str:
    text = f"{expr.head}{expr.open_char}"
    for index, item in enumerate(expr.items):
        if index > 0:
            previous_item = expr.items[index - 1]
            previous_width = widths[index - 1]
            text += "," + (" " * (1 + previous_width - len(previous_item)))
        text += item

    if expr.items and pad_last_item:
        last_index = len(expr.items) - 1
        text += " " * (widths[last_index] - len(expr.items[last_index]))

    return f"{text}{expr.close_char}{expr.tail}"


def align_delimited_exprs(lines: list[ParsedLine]) -> None:
    groups: dict[tuple[str, str, str, str], list[tuple[ParsedLine, DelimitedExpr, str]]] = {}

    for line in lines:
        if line.declaration is not None and line.declaration.rhs_expr is not None:
            key = expr_group_key(line.declaration.rhs_expr)
            groups.setdefault(key, []).append((line, line.declaration.rhs_expr, "rhs"))
        if line.expr is not None:
            key = expr_group_key(line.expr)
            groups.setdefault(key, []).append((line, line.expr, "expr"))

    for group in groups.values():
        if len(group) < 2:
            continue

        max_items = max(len(expr.items) for _, expr, _ in group)
        if max_items < 2:
            continue

        widths = [
            max(len(expr.items[column]) for _, expr, _ in group if len(expr.items) > column)
            for column in range(max_items)
        ]
        pad_last_item = not any(line.continuation for line, _, _ in group)

        for line, expr, kind in group:
            rendered = render_delimited_expr(expr, widths, pad_last_item)
            if kind == "rhs":
                line.declaration.rendered_rhs = rendered
            else:
                line.rendered_expr = rendered
            line.rebuild = True


def align_macro_backslashes(lines: list[ParsedLine]) -> None:
    if len(lines) < 2 or not any(line.continuation for line in lines):
        return

    visible_lengths = [len(f"{line.indent}{build_base_code(line)}" + (f" {line.comment}" if line.comment else "")) for line in lines]
    max_length = max(visible_lengths)

    for line, visible_length in zip(lines, visible_lengths):
        if not line.continuation:
            continue
        line.backslash_padding = max_length - visible_length
        line.rebuild = True


def align_block(lines: list[str], cursor_line_number: int) -> bool:
    cursor_index = cursor_line_number - 1
    block = collect_block(lines, cursor_index)
    if not block.indexes:
        return False

    parsed_lines = [parse_line(index, lines[index]) for index in block.indexes]
    active_lines = collect_active_run(parsed_lines, block.indexes, cursor_index)
    if len(active_lines) < 2:
        return False

    align_declarations(active_lines)
    align_delimited_exprs(active_lines)
    if block.is_macro:
        align_macro_backslashes(active_lines)

    changed = False
    for line in active_lines:
        if not line.rebuild:
            continue
        new_text = render_line(line)
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
