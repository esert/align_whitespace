# Align Whitespace

Align C/C++ declaration, assignment, parameter, call, and macro blocks around the active cursor line.

Examples:

```cpp
int a;
float b;
```

becomes:

```cpp
int   a;
float b;
```

```cpp
MyStruct foobar = {1, 2, 3};
YourStruct bax = {};
HisStruct baz = {5};
```

becomes:

```cpp
MyStruct   foobar = {1, 2, 3};
YourStruct bax    = {};
HisStruct  baz    = {5};
```

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
value += 1;
longestName = 22;
third -= 333;
```

becomes:

```cpp
value       += 1;
longestName  = 22;
third       -= 333;
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

## Command

- `Align Whitespace: C/C++ Block`

## Default keybinding

- `F1` for `*.cpp`, `*.cc`, `*.cxx`, `*.h`, `*.hpp`

## Notes

- For normal same-indent blocks, alignment is limited to the contiguous active run containing the cursor.
- Inactive rows break the active run. If the cursor is on an inactive row, nothing happens.
- Assignment-only rows like `value += 1;` align together and are kept separate from declaration-style rows like `int x = 1;`.
- Compound assignment operators align on the `=` character, so `+=`, `-=`, `|=`, etc. share the same operator column as `=`.
- The alignment logic is implemented in `python/align_cpp_block.py`.
- The extension shim in `extension.js` only registers the VS Code command and invokes Python.
- The default Python command is `python3`. You can change it with the `alignWhitespace.pythonCommand` setting.
