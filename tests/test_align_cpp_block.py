from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from align_cpp_block import align_block


def format_text(source: str, cursor_line: int) -> tuple[str, bool]:
    lines = source.splitlines(keepends=True)
    changed = align_block(lines, cursor_line)
    return "".join(lines), changed


def assert_format(source: str, cursor_line: int, expected: str, changed: bool = True) -> None:
    actual, was_changed = format_text(dedent(source), cursor_line)
    assert actual == dedent(expected)
    assert was_changed is changed


def test_aligns_simple_declarations() -> None:
    assert_format(
        """\
        int a;
        float b;
        """,
        1,
        """\
        int   a;
        float b;
        """,
    )


def test_aligns_function_parameters() -> None:
    assert_format(
        """\
        int lerp(
            int a,
            int b,
            float r,
        );
        """,
        2,
        """\
        int lerp(
            int   a,
            int   b,
            float r,
        );
        """,
    )


def test_aligns_defaulted_function_parameters() -> None:
    assert_format(
        """\
        void foo(
            int a = 1,
            long bb = 22,
        );
        """,
        2,
        """\
        void foo(
            int  a  = 1,
            long bb = 22,
        );
        """,
    )


def test_aligns_assignments_and_inner_call_arguments() -> None:
    assert_format(
        """\
        int x = lerp(1, 2, 0.5f);
        float xx = lerp(11, 22, 1);
        """,
        1,
        """\
        int   x  = lerp(1,  2,  0.5f);
        float xx = lerp(11, 22, 1   );
        """,
    )


def test_aligns_template_scoped_assignment_targets() -> None:
    assert_format(
        """\
        Array<T>::data = _capacity ? _allocator->alloc<T>(_capacity) : 0;
        Array<T>::count = 0;
        capacity  = _capacity;
        allocator = _allocator;
        """,
        1,
        """\
        Array<T>::data  = _capacity ? _allocator->alloc<T>(_capacity) : 0;
        Array<T>::count = 0;
        capacity        = _capacity;
        allocator       = _allocator;
        """,
    )


def test_aligns_template_scoped_assignment_targets_from_later_cursor_line() -> None:
    assert_format(
        """\
        Array<T>::data = _capacity ? _allocator->alloc<T>(_capacity) : 0;
        Array<T>::count = 0;
        capacity  = _capacity;
        allocator = _allocator;
        """,
        4,
        """\
        Array<T>::data  = _capacity ? _allocator->alloc<T>(_capacity) : 0;
        Array<T>::count = 0;
        capacity        = _capacity;
        allocator       = _allocator;
        """,
    )


def test_aligns_template_scoped_assignment_targets_inside_scope() -> None:
    assert_format(
        """\
        void init(Allocator* _allocator, usize _capacity = 0)
        {
            Array<T>::data = _capacity ? _allocator->alloc<T>(_capacity) : 0;
            Array<T>::count = 0;
            capacity  = _capacity;
            allocator = _allocator;
        }
        """,
        3,
        """\
        void init(Allocator* _allocator, usize _capacity = 0)
        {
            Array<T>::data  = _capacity ? _allocator->alloc<T>(_capacity) : 0;
            Array<T>::count = 0;
            capacity        = _capacity;
            allocator       = _allocator;
        }
        """,
    )


def test_aligns_only_parseable_rows_inside_a_scope() -> None:
    assert_format(
        """\
        for (int i = 0; i < 10; i++) {
          int a = i;
          float bb = i * 0.5f;
          dump(a, bb);
        }
        """,
        2,
        """\
        for (int i = 0; i < 10; i++) {
          int   a  = i;
          float bb = i * 0.5f;
          dump(a, bb);
        }
        """,
    )


def test_aligns_scope_block_even_when_cursor_is_on_the_call_line() -> None:
    assert_format(
        """\
        for (int i = 0; i < 10; i++) {
          int a = i;
          float bb = i * 0.5f;
          dump(a, bb);
        }
        """,
        4,
        """\
        for (int i = 0; i < 10; i++) {
          int   a  = i;
          float bb = i * 0.5f;
          dump(a, bb);
        }
        """,
    )


def test_does_not_align_across_inactive_rows_from_earlier_active_line() -> None:
    assert_format(
        """\
        int a = 1;
        foo++;
        float bb = 3;
        """,
        1,
        """\
        int a = 1;
        foo++;
        float bb = 3;
        """,
        changed=False,
    )


def test_aligns_only_the_contiguous_active_run_after_an_inactive_row() -> None:
    assert_format(
        """\
        int a = 1;
        foo++;
        float bb = 3;
        char cccc = 4;
        """,
        3,
        """\
        int a = 1;
        foo++;
        float bb   = 3;
        char  cccc = 4;
        """,
    )


def test_aligns_only_the_contiguous_active_run_from_later_active_line() -> None:
    assert_format(
        """\
        int a = 1;
        foo++;
        float bb = 3;
        char cccc = 4;
        """,
        4,
        """\
        int a = 1;
        foo++;
        float bb   = 3;
        char  cccc = 4;
        """,
    )


def test_cursor_on_inactive_row_does_nothing() -> None:
    assert_format(
        """\
        int a = 1;
        foo++;
        float bb = 3;
        char cccc = 4;
        """,
        2,
        """\
        int a = 1;
        foo++;
        float bb = 3;
        char cccc = 4;
        """,
        changed=False,
    )


def test_aligns_assignment_rows_with_compound_operators() -> None:
    assert_format(
        """\
        value += 1;
        longestName = 22;
        """,
        1,
        """\
        value       += 1;
        longestName  = 22;
        """,
    )


def test_assignment_rows_are_active_together() -> None:
    assert_format(
        """\
        value += 1;
        longestName = 22;
        third -= 333;
        """,
        3,
        """\
        value       += 1;
        longestName  = 22;
        third       -= 333;
        """,
    )


def test_assignment_rows_do_not_align_with_declaration_rows() -> None:
    assert_format(
        """\
        int a = 1;
        long bb = 22;
        value += 3;
        longestName = 44;
        """,
        3,
        """\
        int a = 1;
        long bb = 22;
        value       += 3;
        longestName  = 44;
        """,
    )


def test_declaration_rows_do_not_cross_assignment_rows() -> None:
    assert_format(
        """\
        int a = 1;
        value += 3;
        long bb = 22;
        char ccc = 4;
        """,
        1,
        """\
        int a = 1;
        value += 3;
        long bb = 22;
        char ccc = 4;
        """,
        changed=False,
    )


def test_declarations_and_declaration_assignments_are_active_together() -> None:
    assert_format(
        """\
        int a;
        long bb = 22;
        """,
        1,
        """\
        int  a;
        long bb = 22;
        """,
    )


def test_aligns_macro_block_from_body_cursor() -> None:
    assert_format(
        """\
        #define FOO(X) \\
            X(a, 1, 2) \\
            X(aa, 11, 22) \\
            X(aaa, 111, 222)
        """,
        2,
        """\
        #define FOO(X)      \\
            X(a,   1,   2)  \\
            X(aa,  11,  22) \\
            X(aaa, 111, 222)
        """,
    )


def test_aligns_macro_block_from_final_line_cursor() -> None:
    assert_format(
        """\
        #define FOO(X) \\
            X(a, 1, 2) \\
            X(aa, 11, 22) \\
            X(aaa, 111, 222)
        """,
        4,
        """\
        #define FOO(X)      \\
            X(a,   1,   2)  \\
            X(aa,  11,  22) \\
            X(aaa, 111, 222)
        """,
    )


def test_aligns_mixed_arity_only_through_shared_columns() -> None:
    assert_format(
        """\
        X(a, 1)
        X(aa, 11, 22)
        X(aaa, 111, 222, 333)
        """,
        1,
        """\
        X(a,   1  )
        X(aa,  11,  22 )
        X(aaa, 111, 222, 333)
        """,
    )


def test_preserves_nested_commas_inside_templates_and_initializers() -> None:
    assert_format(
        """\
        auto a = foo(std::pair<int, int>{1, 2}, 3);
        auto b = foo(std::pair<long, long>{10, 20}, 40);
        """,
        1,
        """\
        auto a = foo(std::pair<int, int>{1, 2},     3 );
        auto b = foo(std::pair<long, long>{10, 20}, 40);
        """,
    )


def test_preserves_inline_comments() -> None:
    assert_format(
        """\
        auto a = foo(1, 2); // short
        auto bb = foo(11, 22); // longer
        """,
        1,
        """\
        auto a  = foo(1,  2 ); // short
        auto bb = foo(11, 22); // longer
        """,
    )


def test_blank_line_breaks_the_block() -> None:
    assert_format(
        """\
        int a;
        float b;

        long cc;
        char d;
        """,
        1,
        """\
        int   a;
        float b;

        long cc;
        char d;
        """,
    )


def test_comment_line_breaks_the_block() -> None:
    assert_format(
        """\
        int a = 1;
        // note
        float bb = 2;
        char ccc = 3;
        """,
        3,
        """\
        int a = 1;
        // note
        float bb  = 2;
        char  ccc = 3;
        """,
    )


def test_blocked_control_flow_lines_are_left_unchanged() -> None:
    assert_format(
        """\
        return a;
        return bb;
        """,
        1,
        """\
        return a;
        return bb;
        """,
        changed=False,
    )
