# Align Whitespace

Align simple C/C++ declaration and assignment blocks around the active cursor line.

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

## Command

- `Align Whitespace: C/C++ Block`

## Default keybinding

- `F1` for `*.cpp`, `*.cc`, `*.cxx`, `*.h`, `*.hpp`

## Notes

- The alignment logic is implemented in `python/align_cpp_block.py`.
- The extension shim in `extension.js` only registers the VS Code command and invokes Python.
- The default Python command is `python3`. You can change it with the `alignWhitespace.pythonCommand` setting.
