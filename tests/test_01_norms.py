import sys
import io
import pathlib
import unicodedata
from pytest import (
  raises)
from packaging.markers import default_environment

from email.parser import Parser
from email.policy import compat32

from partis.pyproj import (
  marker_evaluated,
  scalar,
  scalar_list,
  empty_str,
  nonempty_str,
  str_list,
  nonempty_str_list,
  norm_bool,
  CompatibilityTags,
  ValidationError,
  PEPValidationError,
  valid_type,
  valid_keys,
  as_list,
  mapget,
  norm_printable,
  valid_dist_name,
  norm_dist_name,
  norm_dist_filename,
  join_dist_filename,
  norm_dist_version,
  norm_dist_author,
  norm_dist_classifier,
  norm_dist_keyword,
  norm_dist_url,
  norm_dist_extra,
  norm_dist_build,
  dist_build,
  norm_dist_compat,
  join_dist_compat,
  compress_dist_compat,
  norm_data,
  norm_py_identifier,
  norm_entry_point_group,
  norm_entry_point_name,
  norm_entry_point_ref,
  norm_path,
  norm_path_to_os,
  norm_mode,
  norm_zip_external_attr,
  b64_nopad,
  hash_sha256,
  email_encode_items,
  TimeEncode )

from partis.pyproj._nonprintable import (
  NONCHARACTERS,
  STRIP_CATEGORIES,
  nonprintable,
  _strip_char )

#===============================================================================
def test_marker():
  env = default_environment()

  assert marker_evaluated(True)
  assert not marker_evaluated(False)
  assert marker_evaluated(f"python_version == '{env['python_version']}'")

#===============================================================================
def test_time_encode():
  e = TimeEncode()

  assert e.max == '9zzz'
  assert e.encode(0) == '0000'
  assert e.encode(60) == '0001'
  assert e.encode(int(e.max, 36)*e.resolution) == e.max
  assert e.encode((int(e.max, 36) + 1)*e.resolution) == '0000'

#===============================================================================
def test_scalars():
  #.............................................................................
  xs = [False, 0, 0.0, '000', True, 1, 1.0, '111', '']

  for x in xs:
    assert scalar(x) is x

  assert scalar_list(xs) == xs

  ys = [ [], [1,2,3], {}, {1:1}, set() ]

  for y in ys:
    with raises( ValidationError ):
      scalar(y)

  with raises( ValidationError ):
    scalar_list(ys)

  #.............................................................................
  ts = [1, 1.0, True, 'true', 'True', 'yes', 'y', 'enable', 'enabled']
  fs = [0, 0.0, False, 'false', 'False', 'no', 'n', 'disable', 'disabled']

  assert all( norm_bool(t) for t in ts)
  assert not any( norm_bool(f) for f in fs )

  with raises( ValidationError ):
    norm_bool(11)

  with raises( ValidationError ):
    norm_bool(1.1)

  with raises( ValidationError ):
    norm_bool('')

  with raises( ValidationError ):
    norm_bool('1')

  #.............................................................................
  assert empty_str('') == ''

  with raises( ValidationError ):
    empty_str('123')

  with raises( ValidationError ):
    empty_str(123)


  assert nonempty_str('123') == '123'
  assert nonempty_str(123) == '123'

  with raises( ValidationError ):
    nonempty_str('')

  #.............................................................................
  zs = ['1', '2', '3']
  assert str_list(zs) == zs

  qs = [1, 2, 3]
  assert str_list(qs) == zs

  #.............................................................................
  assert nonempty_str_list(zs) == zs

  with raises( ValidationError ):
    nonempty_str_list(['', '', '123'])


#===============================================================================
def test_as_list():
  assert as_list(None) == [None]
  assert as_list('a') == ['a']
  assert as_list(['a', 'b']) == ['a', 'b']
  assert as_list({'a': 'b'}) == [{'a': 'b'}]

#===============================================================================
def test_nonprintable_pattern():
  # the compiled pattern must strip exactly the characters of the reference
  # definition, for every code point and on every interpreter
  mismatched = [
    c for c in map(chr, range(sys.maxunicode+1))
    if bool(nonprintable.match(c)) is not _strip_char(c) ]

  assert not mismatched

#===============================================================================
def test_nonprintable_unicode_version():
  # The set of stripped characters must not depend on the Unicode version of
  # the running interpreter: it is compiled into the back-end, so anything
  # version-dependent makes the meta-data emitted for one project differ
  # between interpreters, and makes every Unicode release silently delete the
  # code points it newly assigns. Cn (unassigned) is the only category that
  # changes, and the only part of it that is stripped is the noncharacters,
  # which are permanently reserved.
  assert 'Cn' not in STRIP_CATEGORIES

  noncharacters = {
    chr(i) for lo, hi in NONCHARACTERS for i in range(lo, hi+1) }

  stripped_unassigned = {
    c for c in map(chr, range(sys.maxunicode+1))
    if _strip_char(c) and unicodedata.category(c) == 'Cn' }

  assert stripped_unassigned == noncharacters

#===============================================================================
def test_norm_printable():
  assert norm_printable(None) == ''
  assert norm_printable("") == ''
  assert norm_printable("hello\t\tfoo bar\ngoodbye\n\n") == "hello\t\tfoo bar\ngoodbye"

  # control (Cc), line/paragraph separator (Zl, Zp), private use (Co) and
  # surrogate (Cs) characters are stripped
  assert norm_printable("a\x00\x07\x1bb") == "ab"
  assert norm_printable("a\u2028\u2029b") == "ab"
  assert norm_printable("a\ue000b") == "ab"
  assert norm_printable("a\ud800b") == "ab"

  # noncharacters are permanently reserved and not for interchange
  assert norm_printable("a\ufdd0b\ufffeb\uffffb") == "abbb"
  assert norm_printable("a\U0010FFFFb") == "ab"

  # unassigned (Cn) characters are kept: which code points are unassigned
  # depends on the Unicode version of the interpreter, and a later Unicode
  # release may assign them
  assert unicodedata.category("\U0001EE78") in ('Cn', 'Lo')
  assert norm_printable("a\U0001EE78b") == "a\U0001EE78b"

  # meta-data is serialized as UTF-8, so printable non-ASCII is kept as-is
  assert norm_printable("Caf\xe9 \u2615 \u2014 na\xefve") == "Caf\xe9 \u2615 \u2014 na\xefve"
  assert norm_printable("\u4f60\u597d") == "\u4f60\u597d"

  # format (Cf) and non-space separator (Zs) characters are needed by legitimate
  # text, even though str.isprintable() excludes them
  assert not "a\u200cb".isprintable()
  assert norm_printable("a\xa0b") == "a\xa0b"
  assert norm_printable("a\u200cb") == "a\u200cb"
  assert norm_printable("\U0001f469\u200d\U0001f4bb") == "\U0001f469\u200d\U0001f4bb"
  assert norm_printable("f\ubaaar") == "f몪r"

#===============================================================================
def test_valid_dist_name():
  valid_names = [
    'xyz',
    '\txyz\n',
    'x_y_z',
    'x1_y2',
    'x.y.z',
    'x-y-z' ]

  invalid_names = [
    '_123',
    '-1x',
    '.x1'
    'x y z',
    '']

  for name in valid_names:
    assert name.strip() == valid_dist_name(name)

  for name in invalid_names:
    print(name)
    with raises( PEPValidationError ):
      valid_dist_name(name)

#===============================================================================
def test_norm_dist_name():
  names = [
    ('  x.-__.--__Y0.z \n', 'x-y0-z') ]

  for name, val in names:
    assert val == norm_dist_name(name)

#===============================================================================
def test_norm_dist_filename():
  names = [
    ('  x.-__.--__y0.z \n', 'x_y0_z') ]

  for name, val in names:
    assert val == norm_dist_filename(norm_dist_name(name))

#===============================================================================
def test_join_dist_filename():
  assert 'w_x-y-z' == join_dist_filename(['w--x','y','','','z'])

#===============================================================================
def test_norm_dist_version():
  valid = [
    '1',
    '1.2',
    '1.2.3',
    ' 1.2.3\n',
    '1.2.3a0',
    '1.2.3b12',
    '1.2.3rc123',
    '1.2.3.post0']

  invalid = [
    'xyz']

  for x in valid:
    assert x.strip() == norm_dist_version(x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_version(x)

#===============================================================================
def test_norm_dist_author():
  valid = [
    (('', ''), ('', '')),
    (('x', ''), ('x', '')),
    (('', 'y@z.com'), ('', 'y@z.com')),
    (('x', 'y@z.com'), ('', 'x <y@z.com>') ),
    # the meta-data is serialized as UTF-8, so a non-ASCII name is not encoded
    # as an RFC 2047 encoded-word
    (('f\ubaaar', ''), ('f\ubaaar', '')),
    (('\xc9mile Zola', 'y@z.com'), ('', '\xc9mile Zola <y@z.com>')),
    # quoted only where the RFC 822 "specials" require it
    (('J. Random', 'y@z.com'), ('', '"J. Random" <y@z.com>')) ]

  invalid = [
    ('', 'xyz>'),
    ('a,', ''),
    ('', 'xyz')  ]

  for x, y in valid:
    assert y == norm_dist_author(*x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_author(*x)

#===============================================================================
def test_norm_dist_classifier():
  valid = [
    ( 'x   \n:: y  ', 'x :: y' ) ]

  invalid = [
    "%",
    "*",
    "asd :: *" ]

  for x, y in valid:
    assert y == norm_dist_classifier(x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_classifier(x)

#===============================================================================
def test_norm_dist_keyword():
  valid = [
    "asd " ]

  invalid = [
    "asd bfr",
    "asd, bfr" ]

  for x in valid:
    assert x.strip() == norm_dist_keyword(x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_keyword(x)

#===============================================================================
def test_norm_dist_url():
  valid = [
    (('xyz','http://xyz.com/123'), ('xyz','http://xyz.com/123')) ]

  invalid = [
    ('', ''),
    ('a,', ''),
    ('', '(*&(*&))')  ]

  for x, y in valid:
    assert y == norm_dist_url(*x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_url(*x)

#===============================================================================
def test_norm_dist_extra():
  valid = [
    "asd " ]

  invalid = [
    "asd bfr" ]

  for x in valid:
    assert x.strip() == norm_dist_extra(x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_extra(x)

#===============================================================================
def test_norm_dist_build():
  valid = [
    "1A" ]

  invalid = [
    "a1" ]

  for x in valid:
    assert x.lower() == norm_dist_build(x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_build(x)


  assert dist_build() == ''
  assert dist_build(1) == '1'
  assert dist_build(build_tag = 'asd') == '0_asd'
  assert dist_build(123, 'asd') == '123_asd'

  with raises( ValueError ):
    dist_build('qwe', 'asd')

  with raises( PEPValidationError ):
    dist_build(123, 'asd-test')

#===============================================================================
def test_norm_dist_compat():
  valid = [
    ( 'py3', 'none', 'any' ) ]

  invalid = [
    ( '', 'none', 'any' ),
    ( 'py3', '', 'any' ),
    ( 'py3', 'none', '' ) ]

  for x in valid:
    assert x == norm_dist_compat(*x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_compat(*x)

#===============================================================================
def test_join_dist_compat():
  assert 'x.y.z' == join_dist_compat(['z','x','x','y'])

#===============================================================================
def test_compress_dist_compat():
  assert ( "py2.py3", "cp3.none", "any.linux" ) == compress_dist_compat([
    ( 'py3', 'cp3', 'linux' ),
    ( 'py2', 'none', 'any' ) ])

#===============================================================================
def test_norm_data():
  assert norm_data("asd") == "asd".encode('utf-8')
  assert norm_data(b"asd") == b"asd"
  assert norm_data(io.BytesIO(b"asd")) == b"asd"

#===============================================================================
def test_norm_py_identifier():
  valid = [
    "asd",
    " asd\n",
    "a1" ]

  invalid = [
    "1a",
    "import" ]

  for x in valid:
    assert x.strip() == norm_py_identifier(x)

  for x in invalid:
    print(x)
    with raises( ValidationError ):
      norm_py_identifier(x)

#===============================================================================
def test_norm_entry_point_group():
  valid = [
    "a.b.c",
    " a.b.c\n" ]

  invalid = [
    "a b c" ]

  for x in valid:
    assert x.strip() == norm_entry_point_group(x)

  for x in invalid:
    print(x)
    with raises( ValidationError ):
      norm_entry_point_group(x)

#===============================================================================
def test_norm_entry_point_name():
  valid = [
    "a.b.c",
    " a.b.c\n" ]

  invalid = [
    "a=b",
    "a[b]",
    "a b"]

  for x in valid:
    assert x.strip() == norm_entry_point_name(x)

  for x in invalid:
    print(x)
    with raises( ValidationError ):
      norm_entry_point_name(x)

#===============================================================================
def test_norm_entry_point_ref():
  valid = [
    ("a.b.c", "a.b.c"),
    ("a.b.c : xyz ", "a.b.c:xyz") ]

  invalid = [
    ":asd",
    "a.b.c ; xyz ",
    "a.1b.c" ]

  for x, y in valid:
    assert norm_entry_point_ref(x) == y

  for x in invalid:
    print(x)
    with raises( ValidationError ):
      norm_entry_point_ref(x)

#===============================================================================
def test_norm_path():

  valid = [
    ("a/b/c", "a/b/c"),
    (r"a\b\c", "a/b/c") ]

  invalid = [
    "/asd",
    "asd/a b c/xyz",
    "a/b/../..",
    "../"]

  for x, y in valid:
    assert norm_path(x) == y

  for x in invalid:
    print(x)
    with raises( ValidationError ):
      norm_path(x)


#===============================================================================
def test_norm_path_to_os():

  assert norm_path_to_os(__file__) == __file__

#===============================================================================
def test_norm_mode():
  assert norm_mode() == 0o644
  assert norm_mode('1') == 0o644

  assert norm_mode(0o755) == 0o755
  assert norm_mode(0o744) == 0o755

  assert norm_mode(0o655) == 0o644
  assert norm_mode(0o644) == 0o644

#===============================================================================
def test_norm_zip_external_attr():
  assert norm_zip_external_attr(0o644) == 0o644 << 16

#===============================================================================
def test_b64_nopad():
  assert b64_nopad(b'data') == 'ZGF0YQ'

#===============================================================================
def test_hash_sha256():
  data = b'data'

  assert hash_sha256(data) == hash_sha256(io.BytesIO(data))

#===============================================================================
def test_email_encode_items():

  b = email_encode_items(
    headers = [
      ('a', 'b'),
      ('c', 'd') ],
    payload = "hello world" )

  c = b.decode('ascii')

  assert c == "a: b\nc: d\n\nhello world"

#===============================================================================
def test_email_encode_items_unicode():
  # > Whenever metadata is serialised to a byte stream (for example, to save to
  # > a file), strings must be serialised using the UTF-8 encoding.
  # In particular, non-ASCII must not be written as RFC 2047 encoded-words,
  # since consumers of the meta-data do not decode them.
  summary = 'héllo — ünicode'
  author = 'Émile Zola'
  payload = "# Rëadme\n\nCafé ☕ — naïve 👩‍💻\n"

  b = email_encode_items(
    headers = [
      ('Summary', summary),
      ('Author', author) ],
    payload = payload )

  assert b == f"Summary: {summary}\nAuthor: {author}\n\n{payload}".encode('utf-8')
  assert b'=?utf-8?' not in b

  # the meta-data is parsed as an RFC 822 message decoded as UTF-8
  msg = Parser(policy = compat32).parsestr(b.decode('utf-8'))

  assert msg['Summary'] == summary
  assert msg['Author'] == author
  assert msg.get_payload() == payload

#===============================================================================
def test_email_encode_items_fold():
  # multi-line values must be folded into RFC 822 continuation lines, otherwise
  # the generator raises HeaderWriteError (CVE-2024-6923)
  b = email_encode_items(
    headers = [
      ('License', 'MIT ©\nsecond line'),
      ('Summary', 'a\rb\u2028c') ] )

  assert b.decode('utf-8') == (
    "License: MIT ©\n         second line\n"
    "Summary: a\n         b\n         c\n\n")

  msg = Parser(policy = compat32).parsestr(b.decode('utf-8'))

  assert msg['License'] == 'MIT ©\n         second line'


if __name__ == '__main__':
  for name, func in dict(globals()).items():
    if callable(func) and name.startswith('test_'):
      print(f"{name}")
      func()