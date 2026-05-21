# Task 6 — `builder/download.py` edge cases

**Target file:** `src/pyproj/builder/download.py`  
**Test file:** `tests/test_12_download.py` (extend existing)  
**Coverage before:** 77%

## Currently covered

`test_12_download.py` already tests the happy path (download a real file with a
valid checksum). The gaps are all in the error and branch paths.

## Missing branches

### Missing `url` (line 48) and missing `checksum` (line 56)

```python
# no url key → ValidationError
options = {}

# no checksum key → ValidationError  
options = {'url': 'https://example.com/file.tar.gz'}
```

### Bad checksum algorithm (lines 85–87)

```python
options = {
  'url': '...',
  'checksum': 'nosuchalg=abc123',
}
# → ValidationError: "Checksum algorithm must be one of ..."
```

These three can be tested without any network access by passing the options dict to
the `download` entry-point function directly (with a mock or stub for the rest of the
builder args).

### Checksum mismatch (lines 134–135)

Download succeeds but the digest doesn't match the declared checksum. Either:
- Mock `requests.get` to return known content, provide a wrong checksum.
- Or use the existing test fixture file with a deliberately wrong checksum string.

The existing download test already mocks requests; extend it with a bad-checksum case.

### `extract=True` (lines 148–168)

When `extract` is truthy the downloaded file is treated as a tar archive and extracted
into `build_dir`. The test needs:
1. A small real (or synthesized) `.tar.gz` file accessible via the mock
2. `options = {'url': '...', 'checksum': '...', 'extract': True}`
3. Verify files appear in `build_dir` after the call

Since the existing test infrastructure already serves a local file via a fixture,
extending it with a `.tar.gz` payload is straightforward.

### `executable=True` (lines 170–172)

After download, sets the execute bit on the output file:
```python
options = {'url': '...', 'checksum': '...', 'executable': True}
# verify out_file.stat().st_mode & stat.S_IXUSR
```

Skip or mark `pragma: no cover` on Windows where `S_IXUSR` has no effect.

### `_cached_download` with URL that has no path segment (lines 188–190)

```python
# url like 'https://example.com' (no trailing slash + filename)
# the `if name != _url` branch would be False
```

This is an internal helper; test directly if it is exported, or test indirectly
by passing such a URL through the download builder with mocked network.

### Zero-size download (line 116–117)

Mock `requests.get` to return an empty iterator (no chunks):
```python
# → ValidationError: "Downloaded file had zero size: ..."
```

## Acceptance criteria

- Missing `url` / missing `checksum` raise `ValidationError`
- Bad checksum algorithm raises `ValidationError`
- Checksum mismatch raises `ValidationError` and cleans up temp file
- `extract=True` unpacks archive into `build_dir`
- `executable=True` sets execute bit (skip on Windows)
- Zero-size download raises `ValidationError`
- `builder/download.py` coverage moves from 77% → 92%+
