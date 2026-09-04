# partis-pyproj — meta-data text validation

Genre: design-doc. Scope: how author-supplied text reaches PKG-INFO / METADATA, and the
trajectory from silently normalizing it to rejecting it.

Status: goal adopted, implementation deferred. The preconditions in §4 gate the change.
Nothing in §3 is implemented.

---

## 1. Current behavior

`norm_printable` (`src/pyproj/pep.py`) strips leading and trailing whitespace and removes
every character in the sets defined by `src/pyproj/_nonprintable.py`:

| Set | Members |
|---|---|
| `STRIP_CATEGORIES` | Cc, Cs, Co, Zl, Zp |
| `NONCHARACTERS` | U+FDD0–FDEF, and U+*FFFE/U+*FFFF in all 17 planes |
| `STRIP_FORMAT` | U+202A–202E, U+2066–2069, U+FEFF |

`\t` and `\n` are exempt (`KEEP`). Cn (unassigned) is deliberately not stripped; the
reasoning is recorded in `_nonprintable.py` and in the v0.4.0 entry of `releases.md`.

Removal is silent. There is no diagnostic, and no record in the built artifact that
anything was removed.

## 2. Problem

Silent removal is itself a source of disagreement between the packaged meta-data and what
the author sees. An author who writes a description containing U+202E sees one string in
their editor and ships a different one; nothing in the build output indicates a
substitution occurred. This is the same class of defect that stripping the directional
controls was intended to prevent, relocated from the consumer to the author.

For the constrained identifier fields (§3, population B) stripping additionally masks
validation: `norm_dist_name("foo<U+202E>bar")` strips to `foobar`, which then satisfies the
distribution-name regex. The invalid input is accepted as a different, valid one.

## 3. Target

`norm_printable`, or a validation step separated from it, raises `PEPValidationError`
when the input contains a character in the strip sets, instead of removing it.

The error message must render each offending character as a printable sentinel (e.g.
`<U+202E>`) together with enough surrounding context to locate it. Two reasons, both
required:

- **Locatability.** For readme and license file content the `validating(key=...)` context
  identifies only the field, not a position within a file that may be thousands of lines.
  A line number and a sentinel-substituted excerpt are needed.
- **The error message is itself a rendering surface.** An error that echoes the raw
  character re-enables the spoof in the author's terminal. Sentinel substitution is a
  correctness requirement of the diagnostic, not a convenience.

### Call sites

28 call sites: 17 in `pep.py`, 7 in `pptoml.py` (schema registrations, each covering many
values), 4 in `pkginfo.py`. They divide into three populations that do not want the same
treatment:

- **A — author free text from `pyproject.toml`.** `description`, `readme.text`,
  `license.text`, author/maintainer name and email, keywords, URL labels, classifiers.
  Raising is the intent of this document.
- **B — constrained identifiers.** Distribution name, version, extra, build tag,
  entry-point group/name/ref, requirements, `requires-python`. Each is already
  regex-`fullmatch`ed or parsed by `packaging` immediately after normalization. Raising is
  strictly better here (see §2) and the false-positive rate is assessed as near zero,
  since these fields are ASCII identifiers in practice. That assessment is inferred from
  the field grammars, not measured against a corpus.
- **C — tool-generated values.** `py_tag`, `abi_tag`, `plat_tag` reach `norm_dist_compat`
  from `dist_binary.py` derived from `sys_tags()`. A raise would not fire. The call sites
  indicate author-input validation applied to machine-generated strings; unrelated to this
  change, but they are why a blanket edit of all 28 sites is not the correct shape.

## 4. Preconditions

Raising is not safe while file artifacts can reach `norm_printable`. Measured against the
current pattern, a readme saved by a Windows editor — UTF-8 BOM, CRLF line endings —
matches at U+000D and U+FEFF. Under a raise, every such file fails the build on its first
line. Neither character is authored content.

1. **Normalize at the file-read boundary.** `read_meta_file` (`pkginfo.py`) decodes with
   `utf-8`. It should decode with `utf-8-sig` and normalize `\r\n` and bare `\r` to `\n`,
   so the BOM and CR never reach `norm_printable`. Not implemented.

   Note that the current stripping of `\r` performs this newline normalization as a side
   effect. Replacing it with a raise removes that behavior; the explicit normalization
   must land first, not alongside.

2. **Decide the treatment of Co.** Private use is in the strip set. The recorded position
   (`_nonprintable.py`) is that PUA characters have no meaning outside a private agreement
   on the font, which the core meta-data specification does not establish, and so are not
   interchangeable. Under a raise this becomes a hard build failure for a project whose
   readme uses Nerd Font or Powerline glyphs, with no escape hatch. Whether that outcome
   is intended is open. The claim that Nerd Fonts occupy U+E000–F8FF is general knowledge,
   not verified in this repository.

3. **Separate validation from normalization.** `norm_printable` also performs
   `str.strip()`, and `test_valid_dist_name` depends on it (`'\txyz\n'` is a valid name).
   A function that both raises and normalizes is misnamed and mixes two concerns.

## 5. Completed

- **`errors='strict'` on meta-data file reads** (`read_meta_file`, `pkginfo.py`).
  Previously `errors='replace'`, which substituted U+FFFD for undecodable bytes. U+FFFD is
  category So, so it was neither stripped nor otherwise reported: a mis-encoded readme
  shipped with replacement characters and no diagnostic. This was a larger instance of the
  §2 defect than the directional-control case and was independent of the raise question.
  Covered by `tests/test_07_pkginfo.py::test_not_utf8`.

## 6. Compatibility

This is a build back-end. A project that builds under the current release and contains any
character in the strip sets will fail to build after the change. No opt-out is designed.
The number of affected external projects is unknown and has not been estimated.

## 7. Open questions

- Precondition 2: is a hard build failure the intended outcome for PUA characters in a
  readme?
- Does the change need an escape hatch (a `[tool.pyproj]` key permitting the current
  strip-and-continue behavior), or is the failure always the correct outcome?
- Should population B raise on a distinct error class from population A? The B failures
  indicate a malformed identifier; the A failures indicate unexpected content in prose.
- Does population C keep calling `norm_printable` at all?
