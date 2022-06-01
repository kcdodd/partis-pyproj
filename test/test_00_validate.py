import warnings
from copy import copy

from pytest import (
  warns,
  raises )

from partis.pyproj.validate import (
  ValidationError,
  ValidDefinitionError,
  validating,
  validate,
  Optional,
  optional,
  Required,
  required,
  fmt_validator,
  Validator,
  Restricted,
  valid,
  union,
  restrict,
  valid_type,
  valid_keys,
  valid_dict,
  valid_list,
  mapget,
  as_list )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_special():
  assert optional == Optional()
  print(str(optional))
  print(repr(optional))
  print(hash(optional))

  assert required == Required()
  print(hash(required))

  assert optional != required
  assert optional != None
  assert required != None

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_validating():

  def f():
    assert False

  def g():
    raise ValidationError("qwe")

  with raises( ValidationError ):
    try:
      with validating( key = 1, root = {1:'a'}, file = 'asd'):
        with validating( key = 'xyz' ):
          with validating( key = 2 ):
            f()

    except ValidationError as e:
      assert e.msg == "Error while validating"
      assert e.doc_path == [1, 'xyz', 2]
      assert e.doc_root == {1:'a'}
      assert e.doc_file == 'asd'
      print(str(e))
      print(repr(e))
      raise

  with raises( ValidationError ):
    try:
      with validating( key = 'xyz', root = {1:'a'}, file = 'asd'):
        with validating( key = 1 ):
          g()

    except ValidationError as e:
      assert e.msg == "qwe"
      assert e.doc_path == ['xyz', 1]
      assert e.doc_root == {1:'a'}
      assert e.doc_file == 'asd'
      print(str(e))
      raise


  with raises( ValidationError ):
    try:
      with validating():
        g()

    except ValidationError as e:
      assert e.msg == "qwe"
      assert e.doc_path == list()
      assert e.doc_root is None
      assert e.doc_file is None
      print(str(e))
      raise

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_validate():

  assert validate(None, 1.0, [float]) == 1.0
  assert validate(None, 1.0, float) == 1.0

  with raises( ValidationError ):
    validate(None, required, [int])

  with raises( ValidationError ):
    validate('asd', required, [int])

  def f(x):
    raise ValidationError("asd")

  with raises( ValidationError ):
    validate('asd', required, [f])

  assert validate('12.34', required, [[int, float]]) == 12.34
  assert validate(12.34, required, [[int, float]]) == 12
  assert validate('asdasd', required, [[]]) == 'asdasd'

  with raises( ValidationError ):
    validate('12.34', required, [[int, f]])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_validator():

  m = Validator()
  print(str(m))
  print(repr(m))
  assert m._default == required
  assert m._validators == []

  m = Validator(default = None)
  assert m._default == optional
  assert m._validators == []

  m = Validator(None)
  assert m._default == optional
  assert m._validators == []

  a = Validator(1)
  print(str(a))
  assert a._default == 1
  assert a._validators == [int]

  b = Validator(int)
  print(str(b))
  assert b._default == 0
  assert b._validators == [int]

  c = Validator(int, default = 2)
  print(str(c))
  assert c._default == 2
  assert c._validators == [int]

  class Test:
    def __init__(self, x):
      self._x = x

    def __eq__(self, other):
      if isinstance(other, Test):

        return self._x == other._x

      return self._x == other

  d = Validator(Test, default = 1)
  print(str(d))
  assert d._default == Test(1)
  assert d._validators == [Test]

  with raises( ValidDefinitionError ):
    Validator(Test)

  def f(x):
    return x

  print(str(Validator(1, int, a, f, lambda x: x)))
  print(str(Validator('')))

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_restricted():
  a = Restricted(1, 5, 10)
  assert a._default == 1
  assert a._validators == [int]
  assert a._options == {1, 5, 10}

  assert a(1) == 1
  assert a(5) == 5
  assert a(10) == 10

  with raises( ValidationError ):
    a(2)

  with raises( ValidDefinitionError ):
    Restricted()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_valid_type():
  valid_type('xyz', types = [str])

  with raises( ValidationError ):
    valid_type('xyz', types = [int])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_valid_keys():
  with raises( ValidationError ):
    valid_keys( 'xyz', allow_keys = ['x', 'y', 'z'] )

  with raises( ValidationError ):
    valid_keys( list(), allow_keys = ['x', 'y', 'z'] )

  valid_keys( dict(), allow_keys = ['x', 'y', 'z'] )

  obj = {
    'x': 1,
    'y': 2,
    'z': 3 }

  valid_keys( obj, allow_keys = ['w', 'x', 'y', 'z'] )

  with raises( ValidationError ):
    valid_keys( obj, allow_keys = ['x', 'y'] )

  with raises( ValidationError ):
    valid_keys( obj,
      allow_keys = ['x', 'y', 'z'],
      require_keys = ['w'] )

  with raises( ValidationError ):
    valid_keys( obj,
      allow_keys = ['x', 'y', 'z'],
      mutex_keys = [('x', 'y')] )

  with raises( ValidationError ):
    valid_keys( obj,
      allow_keys = ['x', 'y', 'z'],
      deprecate_keys = [('x', required)] )

  obj2 = valid_keys( obj,
    allow_keys = ['x', 'y', 'z'],
    deprecate_keys = [('x', None)] )

  assert 'x' not in obj2

  with warns(DeprecationWarning):
    obj2 = valid_keys( obj,
      allow_keys = ['x', 'y', 'z'],
      deprecate_keys = [('x', 'w')] )

  assert 'x' not in obj2
  assert obj2['w'] == 1

  with warns(DeprecationWarning):
    obj2 = valid_keys( obj,
      allow_keys = ['x', 'y', 'z'],
      deprecate_keys = [('x', 'y')] )

  assert 'x' not in obj2
  assert obj2['y'] == 2

  with warnings.catch_warnings():
    warnings.simplefilter("error")

    # should not warn because obj does not have key 'w'
    valid_keys( obj,
      allow_keys = ['x', 'y', 'z'],
      deprecate_keys = [('w', None)] )

  with raises( ValidationError ):
    valid_keys( obj,
      allow_keys = ['y', 'z'],
      wedge_keys = [('w', 'x')] )

  valid_keys( obj,
    allow_keys = ['z'],
    wedge_keys = [('x', 'y')] )

  _obj = {
    ' x': 1,
    'y ': 2,
    ' z   ': 3 }

  obj2 = valid_keys( _obj,
    key_valid = lambda k: k.strip() )

  assert obj2 == obj
  assert obj2 != _obj

  _obj = {
    'x': 1,
    'y': 2.2,
    'z': 3 }

  obj2 = valid_keys( _obj,
    value_valid = lambda v: int(v) )

  assert obj2 is not _obj
  assert obj2 == obj
  assert obj2 != _obj

  _obj = {
    ' x': 1,
    'y': 2.2,
    ' z   ': 3 }

  obj2 = valid_keys( _obj,
    item_valid = lambda kv: (kv[0].strip(), int(kv[1]) ) )

  assert obj2 is not _obj
  assert obj2 == obj
  assert obj2 != _obj

  _obj = {
    'x': 1 }

  obj2 = valid_keys( _obj,
    allow_keys = list(),
    proxy_keys = [('y', 'x'), ('z', 'x')] )


  assert obj2['x'] == 1
  assert obj2['y'] == _obj['x']
  assert obj2['z'] == _obj['x']

  obj2 = valid_keys( {},
    default = obj )

  assert obj2 is not _obj
  assert obj2 == obj


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_valid_dict():
  class test(valid_dict):
    _deprecate_keys = [('x', None), ('y', required)]
    _wedge_keys = [('a','b')]
    _mutex_keys = [('c', 'd')]

  a = test()

  with warns(DeprecationWarning):
    a.setdefault('x', 4)

  with raises(ValidationError):
    a['y'] = 6

  b = test({'a':1, 'b':2, 'c':3})

  c = copy(b)
  print(str(b))
  print(repr(b))
  print(str(c))

  for k in b:
    print(k)

  for k in b.keys():
    print(k)

  for v in b.values():
    print(v)

  assert c.pop('c') == 3
  assert 'c' not in c

  class test(valid_dict):
    _proxy_key = 'x'

  a = test()
  assert a == {}

  b = test(None)
  assert b == {}

  c = test(1)
  assert 'x' in c
  assert c['x'] == 1



#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_valid_list():
  class test(valid_list):
    pass

  a = test()
  a.extend([1,2,3])
  a[1] = 4
  print(str(a))
  print(repr(a))

  a.clear()

  class test(valid_list):
    _min_len = 1

  a = test(['a', 'b'])
  assert a.pop(0) == 'a'

  with raises(ValidationError):
    a.pop()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_mapget():
  obj = {
    'x': 1,
    'y': {
      'a' : 2,
      'b' : [4,5,6] },
    'z': [7,8,9] }

  default = 1234

  valid_paths = [
    ('w', default),
    ('x', 1),
    ('y.a', 2),
    ('y.b', [4,5,6]),
    ('y.c', default),
    ('z', [7,8,9]) ]

  invalid_paths = [
    'x.y',
    'y.a.c',
    'y.b.0.z',
    'z.0' ]

  for p, val in valid_paths:
    assert val == mapget( obj, p, default = default )

  for p in invalid_paths:
    print(p)
    with raises( ValidationError ):
      mapget( obj, p, default = default )

  with raises( ValidationError ):
    mapget( 'asd', 'x', default = default )
