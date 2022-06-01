
import io
import re
import pathlib
from pytest import (
  raises )

from email.utils import formataddr

from partis.pyproj import (
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
  email_encode_items )

from partis.pyproj._nonprintable import (
  _gen_nonprintable,
  gen_nonprintable )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_as_list():
  assert as_list(None) == [None]
  assert as_list('a') == ['a']
  assert as_list(['a', 'b']) == ['a', 'b']
  assert as_list({'a': 'b'}) == ['a']

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_printable():

  regex = gen_nonprintable()
  ns, test = _gen_nonprintable()

  test = norm_printable(norm_printable)

  # since norm_printable considers \t and \n to be printable, but isprintable does not
  test = re.sub(r'[\t\n]', '', test)

  assert test.isprintable()


  assert norm_printable(None) == ''
  assert norm_printable("") == ''
  assert norm_printable("hello\t\tfoo bar\ngoodbye\n\n") == "hello\t\tfoo bar\ngoodbye"
  assert norm_printable("\U0001EE78") == ''
  assert norm_printable("f\ubaaar") == "f몪r"

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_dist_name():
  names = [
    ('  x.-__.--__Y0.z \n', 'x-y0-z') ]

  for name, val in names:
    assert val == norm_dist_name(name)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_dist_filename():
  names = [
    ('  x.-__.--__y0.z \n', 'x_y0_z') ]

  for name, val in names:
    assert val == norm_dist_filename(norm_dist_name(name))

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_join_dist_filename():
  assert 'w_x-y-z' == join_dist_filename(['w--x','y','','','z'])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_dist_author():
  valid = [
    (('', ''), ('', '')),
    (('x', ''), ('x', '')),
    (('', 'y@z.com'), ('', 'y@z.com')),
    (('x', 'y@z.com'), ('', formataddr( ('x', 'y@z.com') )) ) ]

  invalid = [
    ('', 'xyz>'),
    ('f\ubaaar', ''),
    ('a,', ''),
    ('', 'xyz')  ]

  for x, y in valid:
    assert y == norm_dist_author(*x)

  for x in invalid:
    print(x)
    with raises( PEPValidationError ):
      norm_dist_author(*x)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_join_dist_compat():
  assert 'x.y.z' == join_dist_compat(['z','x','x','y'])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_compress_dist_compat():
  assert ( "py2.py3", "cp3.none", "any.linux" ) == compress_dist_compat([
    ( 'py3', 'cp3', 'linux' ),
    ( 'py2', 'none', 'any' ) ])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_data():
  assert norm_data("asd") == "asd".encode('utf-8')
  assert norm_data(b"asd") == b"asd"
  assert norm_data(io.BytesIO(b"asd")) == b"asd"

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_entry_point_name():
  valid = [
    "a.b.c",
    " a.b.c\n" ]

  invalid = [
    "%$" ]

  for x in valid:
    assert x.strip() == norm_entry_point_name(x)

  for x in invalid:
    print(x)
    with raises( ValidationError ):
      norm_entry_point_name(x)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_path_to_os():

  assert norm_path_to_os(__file__) == __file__

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_mode():
  assert norm_mode() == 0o644
  assert norm_mode('1') == 0o644

  assert norm_mode(0o755) == 0o755
  assert norm_mode(0o744) == 0o755

  assert norm_mode(0o655) == 0o644
  assert norm_mode(0o644) == 0o644

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_norm_zip_external_attr():
  assert norm_zip_external_attr(0o644) == 0o644 << 16

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_b64_nopad():
  assert b64_nopad(b'data') == 'ZGF0YQ'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_hash_sha256():
  data = b'data'

  assert hash_sha256(data) == hash_sha256(io.BytesIO(data))

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_email_encode_items():

  b = email_encode_items(
    headers = [
      ('a', 'b'),
      ('c', 'd') ],
    payload = "hello world" )

  c = b.decode('ascii')

  assert c == "a: b\nc: d\n\nhello world"
