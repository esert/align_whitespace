# Align Whitespace Agent Notes

## Purpose

This repository is a small VS Code extension for aligning whitespace in C/C++ code around the active cursor line.

The extension entrypoint is JavaScript, but the alignment logic lives in Python. Most real work happens in `python/align_cpp_block.py`.

## File Map

- `extension.js`: VS Code command registration and Python subprocess shim.
- `python/align_cpp_block.py`: Formatter core.
- `tests/test_align_cpp_block.py`: Pytest coverage for formatter behavior.
- `README.md`: User-facing examples and usage notes.

## Current Formatter Scope

The formatter started as a simple declaration/assignment aligner and has been expanded to handle:

- declaration blocks like `int a;` / `float bb;`
- assignment blocks like `int a = 1;`
- function parameter rows like `int a,` / `float bb,`
- call-like rows with inner argument-column alignment
- macro continuation blocks for `#define ... \`

Examples of current supported behavior:

```cpp
int lerp(
    int a,
    int b,
    float r,
);
```

becomes:

```cpp
int lerp(
    int   a,
    int   b,
    float r,
);
```

```cpp
int x = lerp(1, 2, 0.5f);
float xx = lerp(11, 22, 1);
```

becomes:

```cpp
int   x  = lerp(1,  2,  0.5f);
float xx = lerp(11, 22, 1   );
```

```cpp
#define FOO(X) \
    X(a, 1, 2) \
    X(aa, 11, 22) \
    X(aaa, 111, 222)
```

becomes:

```cpp
#define FOO(X)      \
    X(a,   1,   2)  \
    X(aa,  11,  22) \
    X(aaa, 111, 222)
```

## Important Behavior Details

- Blocks are still collected by contiguous same-indent lines, except macro blocks, which are collected by `#define` plus `\` continuations.
- Mixed arity in delimited expressions is aligned only through shared prefix columns.
- Delimited-expression columns are left-aligned, not numeric-right-aligned.
- Nested commas inside strings, templates, nested calls, and braced initializers should not split outer columns.
- Partial changes are expected: in a mixed block, parseable lines may be reformatted while non-parseable neighbors remain unchanged.
- Blank lines and comment-only lines break normal blocks.
- Control-flow lines like `return`, `if (...)`, `for (...)`, etc. should not be treated as declaration rows.

## Tests

Run:

```sh
pytest -q
```

Current tests cover:

- simple declarations
- function parameters
- defaulted parameters
- assignments plus inner call argument alignment
- partial alignment inside scopes
- cursor on different lines within the same block
- mixed parseable/unparseable rows
- macro continuation alignment
- mixed arity call/macro rows
- nested template/initializer commas
- inline comments
- blank-line and comment-line block boundaries
- blocked control-flow rows

## Notes For Future Work

- If you give the user code pointers, also inline the relevant code snippet in the response, not just the file link.
- Use `apply_patch` for manual file edits.
- The repo currently has generated `python/__pycache__/` artifacts after running tests unless they are cleaned up separately.
