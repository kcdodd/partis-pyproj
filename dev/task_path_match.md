# Task 2 — `path/match.py` edge cases

**Target file:** `src/pyproj/path/match.py`  
**Test file:** `tests/test_02_path.py` (extend existing) or new `test_02c_path_match.py`  
**Coverage before:** 80%

## Missing branches

### `PathMatcher.__init__` (line 129)

`start` coercion when passed as a plain string rather than a `PurePath`:

```python
m = PathMatcher('foo/bar', start='some/dir')
assert m.start == PurePath('some/dir')
```

### `PathMatcher.__repr__` (lines 152–163)

The `__repr__` is never called by existing tests. Cover all flag combos:

```python
repr(PathMatcher('foo'))                              # bare
repr(PathMatcher('!foo'))                             # negate=True
repr(PathMatcher('foo/', start=PurePath('a/b')))      # dironly + start
```

### `PathMatcher.match` with `path is None` (line 179)

```python
assert PathMatcher('foo').match(None) is False
```

### `PathMatcher.match` with path as a string (line 182)

```python
assert PathMatcher('foo').match('foo') is True
assert PathMatcher('foo').match('bar') is False
```

### `PathMatcher.match` with `self.start` set (lines 185–186)

The `start is not None` branch — path must be a sub-path of start to match:

```python
m = PathMatcher('bar', start=PurePath('a'))
assert m.match(PurePath('a/bar')) is True
assert m.match(PurePath('b/bar')) is False   # not under start → False
```

### `PathMatcher.nt` helper (line 199)

```python
m = PathMatcher('foo/bar')
assert m.nt('foo\\bar') is True   # forces Windows PureWindowsPath interpretation
```

### `PathFilter.__init__` with single string or `PathMatcher` (line 239)

The `isinstance(patterns, (str, PathMatcher))` wrapping branch:

```python
pf = PathFilter('*.py')           # single string, not a list
pf = PathFilter(PathMatcher('*.py'))
```

### `PathFilter.filter` with `dnames=None` (line 292)

When `dnames` is not given, names ending with `os.sep` are treated as directories:

```python
pf = PathFilter(['*.py'])
result = pf.filter(PurePath('src'), fnames=['mod.py', 'sub/'])
# 'sub/' should be treated as a dname, not a fname
```

### `PathFilter._filter` with `pattern.start` set (line 332)

When a `PathMatcher` inside the filter has its own `start` attribute, paths
get double-relativized. Construct a filter where the inner matcher has `start`:

```python
inner = PathMatcher('bar', start=PurePath('sub'))
pf = PathFilter([inner], start=PurePath('root'))
# path 'root/sub/bar' should match
```

### `PathFilter.__repr__` (line 352) and `contains` (lines 356–358)

```python
repr(PathFilter(['*.py'], start=PurePath('src')))

from partis.pyproj.path.match import contains
assert contains(PurePath('a/b'), PurePath('a/b/c')) is True
assert contains(PurePath('a/b'), PurePath('x/y'))   is False
```

## Acceptance criteria

- All branches above covered
- `path/match.py` coverage moves from 80% → 95%+
