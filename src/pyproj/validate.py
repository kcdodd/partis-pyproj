import sys
import os.path as osp
import io
import warnings
import stat
import re
import pathlib
import inspect
import types
from copy import copy
from collections.abc import (
  Mapping,
  Sequence,
  Iterable )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# NOTE: Filtering works by changing the traceback linked-list, which means
# writing to the 'tb_next' attrbute to the next frame not to be skipped.
# However, 'tb_next' was a read-only attribute until Python 3.7
FILTER_VALIDATING_FRAMES = sys.version_info >= (3,7)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def ignore_validating(frame, lineno):
  if frame.f_code.co_filename == __file__:
    return True

  return False

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ValidationWarning( RuntimeWarning ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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
    doc_path = None ):

    msg = inspect.cleandoc( msg )

    self.msg = msg
    self.doc_root = doc_root
    self.doc_file = doc_file
    self.doc_path = doc_path or list()

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

    return msg

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ValidDefinitionError( ValidationError ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ValidPathError(ValidationError):
  """File is not valid
  """
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FileOutsideRootError(ValidPathError):
  """File path is outside a desired root directory
  """
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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
          f"Error while validating",
          doc_root = self.root,
          doc_file = self.file,
          doc_path = [self.key] if self.key else None) from value

    # do not handle any exceptions here
    return False

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Special:
  #-----------------------------------------------------------------------------
  def __str__(self):
    return type(self).__name__

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self)

  #-----------------------------------------------------------------------------
  def __eq__(self, other):
    return str(self) == str(other)

  #-----------------------------------------------------------------------------
  def __hash__(self):
    return hash(str(self))

class Optional(Special):
  """Optional value
  """
  pass

class Required(Special):
  """Required value
  """
  pass

class NotSet(Special):
  """Special value indicating a value is not set
  """
  pass

optional = Optional()
required = Required()
notset = NotSet()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def validate(val, default, validators):
  """Internal method to apply default value and validators
  """
  if val is None:
    if default is optional:
      return None

    elif default is required:
      raise ValidationError(f"Value is required")

    else:
      val = default

  if not isinstance(validators, Sequence):
    validators = [validators]

  for validator in validators:
    if isinstance(validator, type):
      # cast to valid type (if needed)
      if not isinstance(val, validator):
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
          val = validate(val, required, _validator)
          break
        except Exception as e:
          errs.append((_validator, e))

      else:
        if errs:
          errs = '\n'.join([f"- {k} -> {v}" for k,v in errs])
          raise ValidationError(f"Value must pass at least one of the validators:\n{errs}")

  return val

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Validator:
  """Validates a value
  """
  #-----------------------------------------------------------------------------
  def __init__(self, *args, default = notset):

    args = list(args)

    if default is notset:
      default = required

      if len(args):
        v = args.pop(0)

        if v in [ None, optional ]:
          default = optional

        elif any(isinstance(v, t) for t in [bool, int, float, str, Sequence, Mapping]):
          default = v

        elif isinstance(v, type):
          # still used to validate the type
          args.insert(0, v)

          try:
            default = v()
          except Exception as e:
            # the type cannot be instantiated without arguments
            raise ValidDefinitionError(
              f"Default value must be specified, or explicitly set as optional or required") from e

        else:
          # cannot be used as default, put back to use as validator
          args.insert(0, v)

    if default is None:
      default = optional

    if len(args) == 0 and default not in [required, optional]:
      # convenience method to used default value to derive type
      args.append(type(default))

    self._default = default
    self._validators = args

  #-----------------------------------------------------------------------------
  def __str__(self):
    args = list()
    for v in self._validators:
      args.append(fmt_validator(v))

    args.append(f"default = {fmt_validator(self._default)}")
    args = ', '.join(args)
    return f"{type(self).__name__}({args})"

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self)

  #-----------------------------------------------------------------------------
  def __call__(self, val):
    return validate(val, self._default, self._validators)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Restricted(Validator):
  """Restricts a value to one of listed options
  """
  #-----------------------------------------------------------------------------
  def __init__(self, *options ):
    if len(options) == 0:
      raise ValidDefinitionError(f"Must have at least one option")

    super().__init__(options[0], type(options[0]))

    _options = list()

    with validating(key = 'options'):
      for i,v in enumerate(options):
        with validating(key = i):
          _options.append(super().__call__(v))

    self._options = set(_options)

  #-----------------------------------------------------------------------------
  def __call__(self, val):
    val = super().__call__(val)

    if val not in self._options:
      raise ValidationError(
        f"Must be one of {self._options}: {val}")

    return val

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def valid(*validators):
  """Casts list of objects to Validator, if needed
  """
  if len(validators) == 1:
    v = validators[0]

    if isinstance(v, Validator):
      return v

  return Validator(*validators)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def union(*validators):
  """Value must pass at least one of listed validators
  """
  return Validator([valid(v) for v in validators], default = required)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def restrict(*options):
  """Restricts a value to one of listed options
  """
  return Restricted(*options)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def valid_type(
  obj,
  types ):

  for t in types:
    if isinstance( obj, t ):
      return t

  raise ValidationError(
    f"Must be of type {types}: {type(obj)}" )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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
      return dict(obj)

    return out

  if forbid_keys:
    for k in forbid_keys:
      if k in out:
        raise ValidationError(f"Use of key '{k}' is not allowed")

  if deprecate_keys:
    for k_old, k_new in deprecate_keys:
      if k_old in out:
        out = copy_once(out)

        if k_new and k_new is not optional:
          if k_new is required:
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
      if k_src in out and out.get(k, None) is None:
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
        if k_new not in [None, optional, required ] ]
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
        v = valid(v)

      val = out.get(k, None)

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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class validating_block:
  def __init__(self, obj):
    self._obj = obj

  def __enter__(self):
    self._obj._validating = True

  def __exit__(self, type, value, traceback):
    self._obj._validating = False

    # do not handle any exceptions here
    return False

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def attrs_modifiable( obj ):
  return (
    not hasattr( obj, '_p_attrs_modify' )
    or obj._p_attrs_modify )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class attrs_modify:
  #-----------------------------------------------------------------------------
  def __init__( self, obj ):
    self._obj = obj

  #-----------------------------------------------------------------------------
  def __enter__(self):
    self._obj._p_attrs_modify = True

  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback):
    self._obj._p_attrs_modify = False

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class valid_dict(Mapping):
  """Validated Mapping

  Attributes
  ----------
  _proxy_key: None | str
    If initialized with a value that is not a Mapping, this key is assigned the
    value before performing validation.
  _key_valid: None | callable
    Validates all keys
  _value_valid: None | callable
    Validates all values
  _item_valid: None | callable
    Validates all (key,value) pairs
  _allow_keys: None | list[str]
    Mapping may not contain keys that are not listed.
  _require_keys: None | list[str]
    Mapping must contain all listed keys.
  _min_keys: None | list[ list[str] ]
    Mapping must contain at least one key from each list.
  _wedge_keys: None | list[ list[str] ]
    Mapping must contain either none or all of the listed keys.
  _mutex_keys: None | list[ list[str] ]
    Mapping may contain at most one key from each list.
  _deprecate_keys: None | list[ (str, None | str | Required) ]
    First key is marked as deprecated and removed from the Mapping.
    If new key is given, the value is remapped to the new key.
    If new key is Required, an error is raised, otherwise a deprecation warning
    is reported.
  _forbid_keys: None | list[str]
    Mapping must not contain any of the listed keys.
  _default: None | Mapping[object, object | type | Validator]
    Default value or validator for given keys.
  _validator : None | Validator
    General validator for entire Mapping after above constraints are satisfied.
  See Also
  --------
  * :func:`valid_keys`
  """

  _proxy_key = None
  _proxy_keys = None
  _key_valid = None
  _value_valid = None
  _item_valid = None
  _allow_keys = None
  _require_keys = None
  _min_keys = None
  _wedge_keys = None
  _mutex_keys = None
  _deprecate_keys = None
  _forbid_keys = None
  _default = None
  _validator = None

  # internal
  _p_all_keys = list()

  #-----------------------------------------------------------------------------
  def __new__( cls, *args, **kwargs ):

    self = super().__new__( cls )
    self._p_attrs_modify = False

    with attrs_modify( self ):
      self._p_dict = dict()
      self._p_key_attr = dict()

    return self

  #---------------------------------------------------------------------------#
  def __init__( self, *args, **kwargs ):
    cls = type(self)

    if (
      len(kwargs) == 0
      and len(args) == 1
      and not isinstance(args[0], Mapping) ):

      v = args[0]

      if v in [None, optional]:
        args = [dict()]
      elif cls._proxy_key:
        args = [{ cls._proxy_key : v }]

    self._p_dict = dict(*args, **kwargs)

    with attrs_modify( self ):
      self._default = { k: valid(v) for k,v in ( cls._default or dict() ).items() }
      self._validator = valid(cls._validator or (lambda v: v))

      self._p_all_keys = list()
      self._validating = False

    self._p_all_keys.extend( self._require_keys or [] )
    self._p_all_keys.extend( self._default.keys() )

    if self._deprecate_keys:
      for keys in self._deprecate_keys:
        self._p_all_keys.extend( [
            k_new
            for k_old, k_new in self._deprecate_keys
            if k_new not in [None, optional, required] ] )

    if self._min_keys:
      for keys in self._min_keys:
        self._p_all_keys.extend(keys)

    if self._wedge_keys:
      for keys in self._wedge_keys:
        self._p_all_keys.extend(keys)

    if self._mutex_keys:
      for keys in self._mutex_keys:
        self._p_all_keys.extend(keys)

    self._p_key_attr = { k.replace('-','_') : k for k in self._p_all_keys }
    self._validate()

  #-----------------------------------------------------------------------------
  def __copy__(self):
    obj = copy(super())
    obj._p_dict = copy(self._p_dict)
    return obj

  #-----------------------------------------------------------------------------
  def __str__(self):
    return str(self._p_dict)

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self._p_dict)

  #-----------------------------------------------------------------------------
  def __len__( self ):
    return len(self._p_dict)

  #-----------------------------------------------------------------------------
  def __iter__( self ):
    return iter(self._p_dict)

  #-----------------------------------------------------------------------------
  def keys( self ):
    return self._p_dict.keys()

  #-----------------------------------------------------------------------------
  def values( self ):
    return self._p_dict.values()

  #-----------------------------------------------------------------------------
  def items( self ):
    return self._p_dict.items()

  #-----------------------------------------------------------------------------
  def clear( self ):
    self._p_dict.clear()
    self._validate()

  #---------------------------------------------------------------------------#
  def update(self, *args, **kwargs ):
    self._p_dict.update(*args, **kwargs)
    self._validate()

  #-----------------------------------------------------------------------------
  def setdefault( self, *args, **kwargs ):
    val = self._p_dict.setdefault(*args, **kwargs)
    self._validate()
    return val

  #-----------------------------------------------------------------------------
  def get( self, *args, **kwargs ):
    return self._p_dict.get(*args, **kwargs)

  #-----------------------------------------------------------------------------
  def pop( self, *args, **kwargs ):
    val = self._p_dict.pop(*args, **kwargs)
    self._validate()
    return val

  #-----------------------------------------------------------------------------
  def __getitem__( self, key ):
    return self._p_dict.__getitem__(key)

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    self._p_dict.__setitem__(key, val)
    self._validate()

  #-----------------------------------------------------------------------------
  def __delitem__( self, key ):
    self._p_dict.__delitem__( key )
    self._validate()

  #-----------------------------------------------------------------------------
  def __setattr__( self, name, val ):

    try:

      if name != '_p_attrs_modify' and not attrs_modifiable( self ):
        # only set mapping if base object doesn't have the attribute
        super().__getattribute__(name)

        if name in self._p_key_attr:
          warnings.warn(f"'{type(self).__name__}' attribute shadows mapping key: {name}")

      object.__setattr__( self, name, val )
      return

    except AttributeError as e:
      pass

    if name != '_p_dict' and name != '_p_key_attr':
      if name in self._p_key_attr:
        self._p_dict[ self._p_key_attr[name] ] = val
        self._validate()
        return

      if name in self._p_dict:
        self._p_dict[ name ] = val
        self._validate()
        return

    raise AttributeError(
      f"'{type(self).__name__}' object has no key '{name}'."
      " New keys must be added using a Mapping method;"
      f" E.G. x['{name}'] = {val}" )


  #-----------------------------------------------------------------------------
  def __getattribute__( self, name ):

    try:
      val = super().__getattribute__(name)

      if name != '_p_dict' and name != '_p_key_attr' and name in self._p_key_attr:
        warnings.warn(f"'{type(self).__name__}' attribute shadows mapping key: {name}")

      return val

    except AttributeError as e:
      pass

    # only get mapping if base object does not have attribute
    if name != '_p_dict' and name != '_p_key_attr':
      if name in self._p_key_attr:
        return self._p_dict[ self._p_key_attr[name] ]

      if name in self._p_dict:
        return self._p_dict[ name ]

    raise AttributeError(
      f"'{type(self).__name__}' object has no key '{name}'")


  #-----------------------------------------------------------------------------
  def _validate(self):
    if self._validating:
      return

    with validating_block(self):
      self.update( **self._validator( valid_keys(
        self._p_dict,
        key_valid = self._key_valid,
        value_valid = self._value_valid,
        item_valid = self._item_valid,
        allow_keys = self._allow_keys,
        require_keys = self._require_keys,
        min_keys = self._min_keys,
        wedge_keys = self._wedge_keys,
        mutex_keys = self._mutex_keys,
        deprecate_keys = self._deprecate_keys,
        forbid_keys = self._forbid_keys,
        default = self._default,
        proxy_keys = self._proxy_keys ) ) )

  #-----------------------------------------------------------------------------
  def __str__(self):
    return str(self._p_dict)

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class valid_list(list):
  """Validated list
  """
  _as_list = None
  _value_valid = None
  _min_len = 0

  #---------------------------------------------------------------------------#
  def __init__( self, vals = None ):
    cls = type(self)
    self._as_list = cls._as_list or list
    self._value_valid = valid(
      cls._value_valid or (lambda v: v))

    if vals is None:
      vals = list()

    elif self._as_list:
      vals = self._as_list(vals)

    for i,v in enumerate(vals):
      with validating(key = i):
        vals[i] = self._value_valid(v)

    super().__init__(vals)
    self._validate()

  #-----------------------------------------------------------------------------
  def clear( self ):
    super().clear()
    self._validate()

  #-----------------------------------------------------------------------------
  def pop( self, *args, **kwargs ):
    val = super().pop(*args, **kwargs)
    self._validate()
    return val

  #---------------------------------------------------------------------------#
  def append(self, val ):
    with validating(key = len(self)):
      val = self._value_valid(val)

    super().append(val)

  #---------------------------------------------------------------------------#
  def extend(self, vals ):
    vals = list(vals)

    for i,v in enumerate(vals):
      with validating(key = len(self) + i):
        vals[i] = self._value_valid(v)

    super().extend(vals)

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    with validating(key = key):
      val = self._value_valid(val)

    super().__setitem__(key, val)

  #-----------------------------------------------------------------------------
  def _validate(self):
    if len(self) < self._min_len:
      raise ValidationError(f"Must have length >= {self._min_len}: {len(self)}")

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def as_list( obj ):
  if isinstance( obj, str ) or not isinstance(obj, Iterable):
    return [ obj ]

  return list(obj)
