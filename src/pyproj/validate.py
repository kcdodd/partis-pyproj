from __future__ import annotations
import sys
import warnings
from functools import partial
import inspect
import types
from copy import copy
from abc import ABCMeta
from collections.abc import (
  Mapping,
  Sequence,
  Iterable )

#===============================================================================
# NOTE: Filtering works by changing the traceback linked-list, which means
# writing to the 'tb_next' attrbute to the next frame not to be skipped.
# However, 'tb_next' was a read-only attribute until Python 3.7
FILTER_VALIDATING_FRAMES = sys.version_info >= (3,7)

#===============================================================================
def filter_traceback(traceback, ignore):
  # NOTE: always keep the first frame in the trace-back (even if it would be filtered)
  cur_tb = traceback
  prev_kept_tb = cur_tb

  # start filtering at the next inner frame
  cur_tb = cur_tb.tb_next

  while cur_tb is not None:
    frame = cur_tb.tb_frame
    lineno = cur_tb.tb_lineno
    code = frame.f_code

    cur_tb = cur_tb.tb_next

    # check the ignore function to see if this frame should be kept
    # NOTE: always keep the last frame in the trace-back (the initial 'raise')
    if cur_tb is not None and ignore(frame, lineno):
      # if ignored, set the 'tb_next' attribute of the previously kept frame
      # to the next frame to be checked
      prev_kept_tb.tb_next = cur_tb
    else:
      prev_kept_tb = cur_tb

#===============================================================================
def ignore_validating(frame, lineno):
  if frame.f_code.co_filename == __file__:
    return True

  return False

#===============================================================================
class ValidationWarning( RuntimeWarning ):
  pass

#===============================================================================
class ValidationError( ValueError ):
  """General validation error

  Parameters
  ----------
  msg : str
    Error message
  """
  def __init__( self, msg,
    doc_root = None,
    doc_file = None,
    doc_path = None,
    extra = None):

    msg = inspect.cleandoc( msg )

    self.msg = msg
    self.doc_root = doc_root
    self.doc_file = doc_file
    self.doc_path = doc_path or list()
    self.extra = extra

    super().__init__( msg )

  #-----------------------------------------------------------------------------
  def __str__(self):

    parts = list()

    if self.doc_path:
      _path = self.doc_path[0]

      if isinstance(_path, int):
        _path = f"[{_path}]"

      for k in self.doc_path[1:]:
        if isinstance(k, int):
          _path += f"[{k}]"
        else:
          _path += f".{k}"

      parts.append( f"at `{_path}`" )

    if self.doc_file:
      parts.append(f"in \"{self.doc_file}\"")


    loc = " ".join(parts)
    msg = self.msg

    if loc:
      msg += '\n' + loc

    if self.extra:
      msg += '\n' + str(self.extra)

    return msg

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self)

  #-----------------------------------------------------------------------------
  def model_hint(self):
    from partis.utils import ModelHint, Loc

    return ModelHint(
      msg = type(self).__name__,
      data = self.msg,
      level = 'error',
      loc = Loc(
        filename = self.doc_file,
        path = self.doc_path ))

#===============================================================================
class RequiredValueError( ValidationError ):
  pass

#===============================================================================
class ValidDefinitionError( ValidationError ):
  pass

#===============================================================================
class ValidPathError(ValidationError):
  """File is not valid
  """
  pass

#===============================================================================
class FileOutsideRootError(ValidPathError):
  """File path is outside a desired root directory
  """
  pass

#===============================================================================
class validating:
  """Context manager to append information to a ValidationError as it propagates

  Intermediate frames for internal validating routines, except for the first
  and last frame, are filtered out of any tracebacks.

  Parameters
  ----------
  key: None | str
    Insert the current key being validated to the head of the 'doc_path'
  root: None | Mapping | Sequence
    Set the root document being validated as 'doc_root'
  file: None | str
    Set a file as the source of the data being validated as 'doc_file'

  See Also
  --------
  * ValidationError
  """
  #-----------------------------------------------------------------------------
  def __init__(self,
    key = None,
    root = None,
    file = None):

    self.key = key
    self.root = root
    self.file = file

  #-----------------------------------------------------------------------------
  def __enter__(self):
    return self

  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback):
    if type is not None:
      if issubclass(type, ValidationError):

        if FILTER_VALIDATING_FRAMES:
          filter_traceback(traceback, ignore_validating)

        value.doc_root = value.doc_root or self.root
        value.doc_file = value.doc_file or self.file

        if self.key is not None:
          value.doc_path.insert(0, self.key)

      else:
        raise ValidationError(
          "Error while validating",
          doc_root = self.root,
          doc_file = self.file,
          doc_path = None if self.key is None else [self.key] ) from value

    # do not handle any exceptions here
    return False

#===============================================================================
class Special:
  #-----------------------------------------------------------------------------
  def __repr__(self):
    return type(self).__name__

  #-----------------------------------------------------------------------------
  def __eq__(self, other):
    return type(self) is type(other)

  #-----------------------------------------------------------------------------
  def __ne__(self, other):
    return type(self) is not type(other)

  #-----------------------------------------------------------------------------
  def __hash__(self):
    return hash(str(self))

#===============================================================================
class Optional(Special):
  """Optional value
  """
  pass

#===============================================================================
class OptionalNone(Special):
  """Optional value, but is set to None if not initially set
  """
  pass

#===============================================================================
class Required(Special):
  """Required value
  """
  pass

#===============================================================================
class NotSet(Special):
  """Special value indicating a value is not set
  """
  pass

OPTIONAL = Optional()
OPTIONAL_NONE = OptionalNone()
REQUIRED = Required()
NOTSET = NotSet()

#===============================================================================
def validate(val, default, validators):
  """Internal method to apply default value and validators
  """

  if val in [NOTSET, None]:
    if default in [OPTIONAL, OPTIONAL_NONE]:
      #               | NOTSET | None |
      # --------------+--------+------+
      # OPTIONAL      | NOTSET | None |
      # --------------+--------+------+
      # OPTIONAL_NONE | None   | None |
      return None if default == OPTIONAL_NONE else val

    elif default == REQUIRED:
      raise RequiredValueError("Value is required")

    else:
      val = default

  if not isinstance(validators, Sequence):
    validators = [validators]

  if not isinstance(validators, (list,tuple)):
    raise ValidDefinitionError(
      "Validators must be list or tuple")

  for validator in validators:
    if isinstance(validator, type):
      # cast to valid type (if needed)
      # if not isinstance(val, validator):
      if type(val) is not validator:
        # NOTE: exact type check does not allow sub-classes
        try:
          val = validator(val)
        except ValidationError as e:
          # already a validation error
          raise e

        except Exception as e:
          # re-raise other errors as a ValidationError
          raise ValidationError(
            f"Failed to cast type {type(val).__name__} to {validator.__name__}: {val}") from e

    elif callable(validator):
      val = validator(val)

    elif isinstance(validator, Sequence):
      # union (only one needs to succeed)
      errs = list()

      for _validator in validator:
        try:
          val = validate(val, REQUIRED, _validator)
          break
        except Exception as e:
          errs.append((_validator, e))

      else:
        if errs:
          errs = '\n'.join([f"- {k} -> {v}" for k,v in errs])
          raise ValidationError(f"Value must pass at least one of the validators:\n{errs}")

  return val

#===============================================================================
def fmt_validator(v):

  if isinstance(v, Validator):
    return str(v)

  if v == '':
    return "''"

  if not (
    callable(v)
    or any(
      isinstance(v,t)
      for t in [type, types.BuiltinFunctionType, types.FunctionType]) ):

    return str(v)

  name = None

  while name is None:
    if hasattr(v, '__qualname__'):
      name = v.__qualname__

    elif hasattr(v, '__name__'):
      name = v.__name__

    else:
      v = type(v)

  if name.startswith('<'):
    return name

  mod = None

  if hasattr(v, '__module__'):
    mod = v.__module__

    if mod != 'builtins':
      name = f"{mod}.{name}"

  return f"<{name}>"

#===============================================================================
class Validator:
  """Validates a value
  """
  __slots__ = ('default', 'validators')

  #-----------------------------------------------------------------------------
  def __init__(self, *args, default = NOTSET):

    args = list(args)

    # TODO: change comparisons from 'is' to "==", reimplement Special __eq__
    if default == NOTSET:
      default = REQUIRED

      if len(args):
        v = args.pop(0)

        if v in [REQUIRED, OPTIONAL, OPTIONAL_NONE]:
          # set from special value
          default = v

        elif v is None:
          # set to fill in None if not given
          default = OPTIONAL_NONE

        elif any(isinstance(v, t) for t in [bool, int, float, str, Sequence, Mapping]):
          default = v

        elif isinstance(v, type):
          # still used to validate the type
          args.insert(0, v)

          try:
            default = v()
          except RequiredValueError:
            # this really is a required value
            pass

          except Exception as e:
            # the type cannot be instantiated without arguments
            raise ValidDefinitionError(
              "Default value must be specified, or explicitly set as optional or required") from e

        else:
          # cannot be used as default, put back to use as validator
          # and a value is assumed to be required
          args.insert(0, v)

    elif default is None:
      # set to fill in None if not given
      default = OPTIONAL_NONE

    if len(args) == 0 and default not in [REQUIRED, OPTIONAL, OPTIONAL_NONE]:
      # convenience method to used default value to derive type
      args.append(type(default))

    self.default = default
    self.validators = tuple(args)

  #-----------------------------------------------------------------------------
  def __str__(self):
    args = list()
    for v in self.validators:
      args.append(fmt_validator(v))

    args.append(f"default = {fmt_validator(self.default)}")
    args = ', '.join(args)
    return f"{type(self).__name__}({args})"

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self)

  #-----------------------------------------------------------------------------
  def __call__(self, val = NOTSET):
    return validate(val, self.default, self.validators)

#===============================================================================
class Restricted(Validator):
  """Restricts a value to one of listed options
  """
  __slots__ = ('options',)

  #-----------------------------------------------------------------------------
  def __init__(self, *options ):
    if len(options) == 0:
      raise ValidDefinitionError("Must have at least one option")

    super().__init__(options[0], type(options[0]))

    _options = list()

    with validating(key = 'options'):
      for i,v in enumerate(options):
        with validating(key = i):
          _options.append(super().__call__(v))

    self.options = set(_options)

  #-----------------------------------------------------------------------------
  def __call__(self, val):
    val = super().__call__(val)

    if val not in self.options:
      raise ValidationError(
        f"Must be one of {self.options}: {val}")

    return val

#===============================================================================
def valid(*validators, default = NOTSET):
  """Casts list of objects to Validator, if needed
  """
  if len(validators) == 1:
    v = validators[0]

    if isinstance(v, Validator):
      return v

  return Validator(*validators, default = default)

#===============================================================================
def union(*validators):
  """Value must pass at least one of listed validators
  """
  return Validator([valid(v) for v in validators], default = REQUIRED)

#===============================================================================
def restrict(*options):
  """Restricts a value to one of listed options
  """
  return Restricted(*options)

#===============================================================================
def valid_type(
  obj,
  types ):

  for t in types:
    if isinstance( obj, t ):
      return t

  raise ValidationError(
    f"Must be of type {types}: {type(obj)}" )

#===============================================================================
def valid_keys(
  obj,
  key_valid = None,
  value_valid = None,
  item_valid = None,
  allow_keys = None,
  require_keys = None,
  min_keys = None,
  wedge_keys = None,
  mutex_keys = None,
  deprecate_keys = None,
  forbid_keys = None,
  default = None,
  proxy_keys = None ):
  """Check that a mapping does not contain un-expected keys

  Parameters
  ----------
  obj: Mapping
    Mapping object to validate
  key_valid: None | callable
    Validates all keys
  value_valid: None | callable
    Validates all values
  item_valid: None | callable
    Validates all (key,value) pairs
  allow_keys: None | list[str]
    Mapping may not contain keys that are not listed.
  require_keys: None | list[str]
    Mapping must contain all listed keys.
  min_keys: None | list[ list[str] ]
    Mapping must contain at least one key from each list.
  wedge_keys: None | list[ list[str] ]
    Mapping must contain either none or all of the listed keys.
  mutex_keys: None | list[ list[str] ]
    Mapping may contain at most one key from each list.
  deprecate_keys: None | list[ (str, None | str | Required) ]
    First key is marked as deprecated and removed from the Mapping.
    If new key is given, the value is remapped to the new key.
    If new key is Required, an error is raised, otherwise a deprecation warning
    is reported.
  forbid_keys: None | list[str]
    Mapping must not contain any of the listed keys.
  default: None | Mapping[object, object | type | Validator]
    Default value or validator for given keys.
  proxy_keys : None | list[ list[str] ]
  """

  if not isinstance( obj, Mapping ):
    raise ValidationError(
      f"Must be mapping: {type(obj)}" )

  out = obj

  def copy_once(out):
    if out is obj:
      # copy only if 'out' is still the same object as obj
      return copy(obj)

    return out

  if forbid_keys:
    for k in forbid_keys:
      if k in out:
        raise ValidationError(f"Use of key '{k}' is not allowed")

  if deprecate_keys:
    for k_old, k_new in deprecate_keys:
      if k_old in out:
        out = copy_once(out)

        if k_new and k_new not in [OPTIONAL, OPTIONAL_NONE]:
          if k_new == REQUIRED:
            # Use of REQUIRED indicates this is an error
            raise ValidationError(f"Use of key '{k_old}' is deprecated")
          else:
            warnings.warn(f"Use of key '{k_old}' is deprecated, replaced by '{k_new}'", DeprecationWarning)

          if k_new not in out:
            out[k_new] = out[k_old]

        else:
          warnings.warn(f"Use of key '{k_old}' is deprecated", DeprecationWarning)

        out.pop(k_old)

  if proxy_keys:
    for k, k_src in proxy_keys:
      if k_src in out and out.get(k) is None:
        out = copy_once(out)
        out[k] = out[k_src]

  if key_valid:
    for k, v in out.items():
      with validating(key = k):
        _k = key_valid(k)

      if _k != k:
        out = copy_once(out)
        out.pop(k)
        out[_k] = v

  if value_valid:
    for k, v in out.items():
      with validating(key = k):
        _v = value_valid(v)

      if _v is not v:
        out = copy_once(out)
        out[k] = _v

  if item_valid:
    for k,v in out.items():
      with validating(key = k):
        _k, _v = item_valid( (k,v) )

      if _k != k:
        out = copy_once(out)
        out.pop(k)
        out[_k] = _v

      elif _v is not v:
        out = copy_once(out)
        out[k] = _v


  if allow_keys is not None:
    allow_keys = copy(allow_keys)
    allow_keys.extend( require_keys or [] )
    allow_keys.extend( [
        k_new
        for k_old, k_new in deprecate_keys
        if k_new not in [None, OPTIONAL, OPTIONAL_NONE, REQUIRED ] ]
      if deprecate_keys else [] )

    allow_keys.extend( default.keys() if default else [] )

    if proxy_keys:
      for keys in proxy_keys:
        allow_keys.extend(keys)

    if min_keys:
      for keys in min_keys:
        allow_keys.extend(keys)

    if wedge_keys:
      for keys in wedge_keys:
        allow_keys.extend(keys)

    if mutex_keys:
      for keys in mutex_keys:
        allow_keys.extend(keys)

    allow_keys = set(allow_keys)

    for k in out.keys():
      if k not in allow_keys:
        raise ValidationError(
          f"Allowed keys {allow_keys}: '{k}'" )

  if default:
    for k, v in default.items():
      if not isinstance(v, Validator):
        # convert literal value to a validator
        v = valid(v)

      val = out.get(k, NOTSET)

      with validating(key = k):
        _val = v( val )

      if _val is not val:
        out = copy_once(out)
        out[k] = _val

  if require_keys:
    for k in require_keys:
      if k not in out:
        raise ValidationError(
          f"Required keys {require_keys}: '{k}'" )

  if min_keys:
    for keys in min_keys:
      if not any(k in out for k in keys):
        raise ValidationError(
          f"Must have at least one of keys: {keys}" )

  if wedge_keys:
    for keys in wedge_keys:
      if any(k in out for k in keys) and not all(k in out for k in keys):
        raise ValidationError(
          f"Must have either all, or none, of keys: {keys}" )

  if mutex_keys:
    for keys in mutex_keys:
      if sum(k in out for k in keys) > 1:
        raise ValidationError(
          f"May not have more than one of keys: {keys}" )


  return out

#===============================================================================
class _ValidDictAttr:
  r"""Descriptor for accessing dictionary keys as attributes
  """
  __slots__ = ('name', 'key')

  #-----------------------------------------------------------------------------
  def __init__(self, name: str, key: str):
    self.name = name
    self.key = key

  #-----------------------------------------------------------------------------
  def __get__(self, obj, owner):
    if obj is None:
      return self

    return obj._data[self.key]

  #-----------------------------------------------------------------------------
  def __set__(self, obj, value):
    obj._data[self.key] = value
    obj._validate()

  #-----------------------------------------------------------------------------
  def __delete__(self, obj):
    del obj._data[self.key]
    obj._validate()

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return f"{type(self).__name__}({self.name!r}, {self.key!r})"

#===============================================================================
class _ValidDictMeta(ABCMeta):
  #-----------------------------------------------------------------------------
  def __new__(mcls,
      name,
      bases,
      namespace):

    schema_keys = (
      'key_valid',
      'value_valid',
      'item_valid',
      'allow_keys',
      'require_keys',
      'min_keys',
      'wedge_keys',
      'mutex_keys',
      'deprecate_keys',
      'forbid_keys',
      'default',
      'proxy_keys',
      'validator')

    schema = {}

    for base in bases:
      # include options from base classes
      if isinstance(base, _ValidDictMeta):
        for k in schema_keys:
          v = base.__dict__.get(k)

          if v is not None:
            schema[k] = v

    for k in schema_keys:
      v = namespace.get(k)

      if v is not None:
        schema[k] = v

    namespace.update(schema)

    validator = schema.get('validator')
    key_valid = schema.get('key_valid')
    value_valid = schema.get('value_valid')
    item_valid = schema.get('item_valid')
    allow_keys = schema.get('allow_keys')
    require_keys = schema.get('require_keys')
    min_keys = schema.get('min_keys')
    wedge_keys = schema.get('wedge_keys')
    mutex_keys = schema.get('mutex_keys')
    deprecate_keys = schema.get('deprecate_keys')
    forbid_keys = schema.get('forbid_keys')
    default = schema.get('default')
    proxy_keys = schema.get('proxy_keys')

    default = {
      k: valid(v)
      for k,v in (default or dict()).items()}
    all_keys = list()

    all_keys.extend(allow_keys or ())
    all_keys.extend(require_keys or ())
    all_keys.extend(default.keys())

    if deprecate_keys:
      all_keys.extend([
          k_new
          for k_old, k_new in deprecate_keys
          if k_new not in [None, OPTIONAL, OPTIONAL_NONE, REQUIRED]])

    if min_keys:
      for keys in min_keys:
        all_keys.extend(keys)

    if wedge_keys:
      for keys in wedge_keys:
        all_keys.extend(keys)

    if mutex_keys:
      for keys in mutex_keys:
        all_keys.extend(keys)

    all_keys = tuple(all_keys)

    # compose validator with parameterized valid_keys method
    validators = [partial(valid_keys,
      key_valid = key_valid,
      value_valid = value_valid,
      item_valid = item_valid,
      allow_keys = allow_keys,
      require_keys = require_keys,
      min_keys = min_keys,
      wedge_keys = wedge_keys,
      mutex_keys = mutex_keys,
      deprecate_keys = deprecate_keys,
      forbid_keys = forbid_keys,
      default = default,
      proxy_keys = proxy_keys)]

    if validator:
      validators.append(validator)

    validator = valid(*validators)

    namespace['_all_keys'] = all_keys
    namespace['_validator'] = validator
    namespace.setdefault('__slots__', ())

    for k in all_keys:
      # create attributes mapping to dictionary keys
      name = k.replace('-','_')
      attr = _ValidDictAttr(name, k)
      namespace[name] = attr

    cls = super().__new__(mcls, name, bases, namespace)

    return cls

#===============================================================================
class valid_dict(Mapping, metaclass = _ValidDictMeta):
  """Validated Mapping

  Attributes
  ----------
  proxy_key: None | str
    If initialized with a value that is not a Mapping, this key is assigned the
    value before performing validation.
  proxy_keys: None | list[tuple[str,str]]
    Pairs of keys, where the second key is used to get a value when the first key
    is missing a value.
  key_valid: None | callable
    Validates all keys
  value_valid: None | callable
    Validates all values
  item_valid: None | callable
    Validates all (key,value) pairs
  allow_keys: None | list[str]
    Mapping may not contain keys that are not listed.
  require_keys: None | list[str]
    Mapping must contain all listed keys.
  min_keys: None | list[ list[str] ]
    Mapping must contain at least one key from each list.
  wedge_keys: None | list[ list[str] ]
    Mapping must contain either none or all of the listed keys.
  mutex_keys: None | list[ list[str] ]
    Mapping may contain at most one key from each list.
  deprecate_keys: None | list[ (str, None | str | Required) ]
    First key is marked as deprecated and removed from the Mapping.
    If new key is given, the value is remapped to the new key.
    If new key is Required, an error is raised, otherwise a deprecation warning
    is reported.
  forbid_keys: None | list[str]
    Mapping must not contain any of the listed keys.
  default: None | Mapping[object, object | type | Validator]
    Default value or validator for given keys.
  validator : None | Validator
    General validator for entire Mapping after above constraints are satisfied.
  See Also
  --------
  * :func:`valid_keys`
  """
  __slots__ = ('_data',)

  proxy_key = None
  proxy_keys = None
  key_valid = None
  value_valid = None
  item_valid = None
  allow_keys = None
  require_keys = None
  min_keys = None
  wedge_keys = None
  mutex_keys = None
  deprecate_keys = None
  forbid_keys = None
  default = None
  validator = None

  #---------------------------------------------------------------------------#
  # pylint: disable-next=E0602
  def __init__( self, *args, **kwargs ):
    cls = type(self)

    if (
      len(kwargs) == 0
      and len(args) == 1
      and not isinstance(args[0], Mapping) ):

      v = args[0]

      if v in (None, OPTIONAL, OPTIONAL_NONE):
        args = [dict()]

      elif cls.proxy_key:
        args = [{ cls.proxy_key : v }]

      else:
        raise ValidationError(f"Expected mapping: got {v!r}")

    self._data = dict(*args, **kwargs)
    self._validate()

  #-----------------------------------------------------------------------------
  def __eq__(self, other):
    if isinstance(other, valid_dict):
      other = other._data

    return self._data.__eq__(other)

  #-----------------------------------------------------------------------------
  def __ne__(self, other):
    if isinstance(other, valid_dict):
      other = other._data

    return self._data.__ne__(other)

  #-----------------------------------------------------------------------------
  def __copy__(self):
    cls = type(self)
    obj = cls.__new__(cls)
    obj._data = copy(self._data)
    return obj

  #-----------------------------------------------------------------------------
  def __str__(self):
    return str(self._data)

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return repr(self._data)

  #-----------------------------------------------------------------------------
  def __len__(self):
    return len(self._data)

  #-----------------------------------------------------------------------------
  def __iter__(self):
    return iter(self._data)

  #-----------------------------------------------------------------------------
  def __contains__(self, name):
    return self._data.__contains__(name)

  #-----------------------------------------------------------------------------
  def keys(self):
    return self._data.keys()

  #-----------------------------------------------------------------------------
  def values(self):
    return self._data.values()

  #-----------------------------------------------------------------------------
  def items(self):
    return self._data.items()

  #-----------------------------------------------------------------------------
  def clear(self):
    self._data.clear()
    self._validate()

  #---------------------------------------------------------------------------#
  def update(self, *args, **kwargs ):
    self._data.update(*args, **kwargs)
    self._validate()

  #-----------------------------------------------------------------------------
  def setdefault( self, *args, **kwargs ):
    val = self._data.setdefault(*args, **kwargs)
    self._validate()
    return val

  #-----------------------------------------------------------------------------
  def get( self, *args, **kwargs ):
    return self._data.get(*args, **kwargs)

  #-----------------------------------------------------------------------------
  def pop( self, *args, **kwargs ):
    val = self._data.pop(*args, **kwargs)
    self._validate()
    return val

  #-----------------------------------------------------------------------------
  def popitem( self, *args, **kwargs ):
    val = self._data.popitem(*args, **kwargs)
    self._validate()
    return val

  #-----------------------------------------------------------------------------
  def __getitem__( self, key ):
    return self._data.__getitem__(key)

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    self._data.__setitem__(key, val)
    self._validate()

  #-----------------------------------------------------------------------------
  def __delitem__( self, key ):
    self._data.__delitem__( key )
    self._validate()

  #-----------------------------------------------------------------------------
  def _validate(self):
    self._data = self._validator(self._data)

#===============================================================================
class valid_list(list):
  """Validated list
  """
  _as_list = None
  value_valid = None
  _min_len = 0

  #---------------------------------------------------------------------------#
  def __init__( self, vals = None ):
    cls = type(self)

    if vals is None:
      vals = list()

    elif cls._as_list:
      vals = cls._as_list(vals)

    elif not isinstance(vals, Iterable) or isinstance(vals, (str,Mapping)):
      raise ValidationError(f"Excpected sequence: got {vals!r}")

    else:
      vals = list(vals)

    if cls.value_valid:
      for i,v in enumerate(vals):
        with validating(key = i):
          vals[i] = cls.value_valid(v)

    super().__init__(vals)
    self._validate()

  #-----------------------------------------------------------------------------
  def clear(self):
    super().clear()
    self._validate()

  #-----------------------------------------------------------------------------
  def pop( self, *args, **kwargs ):
    val = super().pop(*args, **kwargs)
    self._validate()
    return val

  #---------------------------------------------------------------------------#
  def append(self, val ):
    if self.value_valid:
      with validating(key = len(self)):
        val = self.value_valid(val)

    super().append(val)

  #---------------------------------------------------------------------------#
  def extend(self, vals ):
    vals = list(vals)

    if self.value_valid:
      for i,v in enumerate(vals):
        with validating(key = len(self) + i):
          vals[i] = self.value_valid(v)

    super().extend(vals)

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    if self.value_valid:
      with validating(key = key):
        val = self.value_valid(val)

    super().__setitem__(key, val)

  #-----------------------------------------------------------------------------
  def _validate(self):
    if len(self) < self._min_len:
      raise ValidationError(f"Must have length >= {self._min_len}: {len(self)}")

#===============================================================================
def mapget(
  obj,
  path,
  default = None ):
  """Convenience method for extracting a value from a nested mapping
  """

  parts = path.split('.')
  _obj = obj
  last_i = len(parts)-1

  for i, part in enumerate(parts):
    if not isinstance( _obj, Mapping ):
      lpath = '.'.join(parts[:i])
      rpath = '.'.join(parts[i:])

      if len(lpath) > 0:
        raise ValidationError(
          f"Expected a mapping object [{lpath}][{rpath}]: {_obj}")
      else:
        raise ValidationError(
          f"Expected a mapping object [{rpath}]: {_obj}")

    _default = default if i == last_i else dict()

    _obj = _obj.get( part, _default )

  return _obj

#===============================================================================
def as_list(obj):
  if isinstance(obj, (str, Mapping)) or not isinstance(obj, Iterable):
    return [obj]

  return list(obj)
