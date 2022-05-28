import os.path as osp
import io
import warnings
import stat
import re
import pathlib
import inspect
from copy import copy
from collections.abc import (
  Mapping,
  Sequence,
  Iterable )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ValidationError( ValueError ):
  """General validation error

  Parameters
  ----------
  msg : str
    Error message
  """
  def __init__( self, msg ):

    msg = inspect.cleandoc( msg )

    super().__init__( msg )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
optional = None
required = object()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def validate(val, default, validators):
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
      for _validator in validator[::-1]:
        try:
          val = validate(val, required, _validator)
          break
        except Exception as e:
          pass

      else:
        raise e

  return val

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Validator:

  #-----------------------------------------------------------------------------
  def __init__(self, *args):

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
        except Exception:
          # if the type cannot be instantiated without arguments, remains required
          pass

      else:
        # cannot be used as default, put back to use as validator
        args.insert(0, v)

    if len(args) == 0 and default not in [required, optional]:
      # convenience method to used default value to derive type
      args.append(type(v))

    self._default = default
    self._validators = args

  #-----------------------------------------------------------------------------
  def __call__(self, val):
    return validate(val, self._default, self._validators)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Restricted(Validator):
  #-----------------------------------------------------------------------------
  def __init__(self, *options ):
    if len(options) == 0:
      raise ValueError(f"Must have at least one option")

    self._options = options

    super().__init__(options[0], type(options[0]))

  #-----------------------------------------------------------------------------
  def __call__(self, val):
    val = super().__call__(val)

    if val not in self._options:
      raise ValidationError(
        f"Must be one of {self._options}: {val}")

    return val

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def valid(*validators):
  if len(validators) == 1:
    v = validators[0]

    if isinstance(v, Validator):
      return v

    elif any(isinstance(v, t) for t in [bool, int, float, str, Sequence, Mapping]):
      return Validator(v, type(v))

  return Validator(*validators)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def union(*validators):
  return Validator(validators)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def restrict(*options):
  return Restricted(*options)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def valid_type(
  name,
  obj,
  types ):

  for t in types:
    if isinstance( obj, t ):
      return t

  raise ValidationError(
    f"{name} must be of type {types}: {type(obj)}" )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def valid_keys(
  name,
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
  default = None ):
  """Check that a mapping does not contain un-expected keys
  """

  if not isinstance( obj, Mapping ):
    raise ValidationError(
      f"{name} must be mapping: {type(obj)}" )

  if forbid_keys:
    for k in forbid_keys:
      if k in obj:
        raise ValidationError(f"Use of {name} key '{k}' is not allowed")

  if deprecate_keys:
    for k_old, k_new in deprecate_keys:
      if k_old in obj:
        if k_new:
          if k_new is required:
            raise ValidationError(f"Use of {name} key '{k_old}' is deprecated")
          else:
            warnings.warn(f"Use of {name} key '{k_old}' is deprecated, replaced by '{k_new}'")

          if k_new not in obj:
            obj[k_new] = obj[k_old]

        else:
          warnings.warn(f"Use of {name} key '{k_old}' is deprecated")

        obj.pop(k_old)

  if default:
    for k, v in default.items():
      if not isinstance(v, Validator):
        v = valid(v)

      val = v( obj.get(k, None) )

      if val is not None:
        obj[k] = val

  if allow_keys:
    allow_keys.extend( require_keys or [] )
    allow_keys.extend( [k_new for k_old, k_new in deprecate_keys] if deprecate_keys else [] )
    allow_keys.extend( default.keys() if default else [] )

    if min_keys:
      for k1, k2 in min_keys:
        allow_keys.append(k1)
        allow_keys.append(k2)

    if wedge_keys:
      for k1, k2 in wedge_keys:
        allow_keys.append(k1)
        allow_keys.append(k2)

    if mutex_keys:
      for k1, k2 in mutex_keys:
        allow_keys.append(k1)
        allow_keys.append(k2)

    for k in obj.keys():
      if k not in allow_keys:
        raise ValidationError(
          f"{name} allowed keys {allow_keys}: '{k}'" )

  if require_keys:
    for k in require_keys:
      if k not in obj:
        raise ValidationError(
          f"{name} required keys {require_keys}: '{k}'" )

  if min_keys:
    for keys in min_keys:
      if not any(k in obj for k in keys):
        raise ValidationError(
          f"{name} must have at least one of keys: {keys}" )

  if wedge_keys:
    for keys in wedge_keys:
      if any(k in obj for k in keys) and not all(k in obj for k in keys):
        raise ValidationError(
          f"{name} must have either all, or none, of keys: {keys}" )

  if mutex_keys:
    for keys in mutex_keys:
      if sum(k in obj for k in keys) > 1:
        raise ValidationError(
          f"{name} may not have more than one of keys: {keys}" )


  if key_valid:
    _obj = copy(obj)

    for k, v in obj.items():
      _obj[key_valid(k)] = v

    obj = _obj

  if value_valid:
    _obj = copy(obj)

    for k, v in obj.items():
      _obj[k] = value_valid(v)

    obj = _obj

  if item_valid:
    _obj = copy(obj)

    for k,v in obj.items():
      k,v = item_valid(k,v)
      _obj[k] = v

    obj = _obj

  return obj

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class validating:
  def __init__(self, obj):
    self._obj = obj

  def __enter__(self):
    self._obj._validating = True

  def __exit__(self, type, value, traceback):
    self._obj._validating = False

    # do not handle any exceptions here
    return False

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class valid_dict(dict):
  name = ''
  proxy_key = None
  value_valid = None
  item_valid = None
  key_valid = None
  allow_keys = None
  require_keys = None
  min_keys = None
  wedge_keys = None
  mutex_keys = None
  deprecate_keys = None
  forbid_keys = None
  default = None
  validator = None

  # internal
  _all_keys = list()

  #---------------------------------------------------------------------------#
  def __init__( self, *args, **kwargs ):

  if self.proxy_key and len(kwargs) == 0 and len(args) == 1:
      args = [{self.proxy_key : args[0]}]

    super().__init__(*args, **kwargs)

    self.key_valid = valid(self.key_valid) if self.key_valid else None
    self.value_valid = valid(self.value_valid) if self.value_valid else None

    self.default = { k: valid(v) for k,v in ( self.default or dict() ) }
    self.validator = valid(self.validator if self.validator else lambda v: v)

    self._all_keys = list()
    self._all_keys.extend( self.require_keys or [] )
    self._all_keys.extend(
      [ k_new for k_old, k_new in self.deprecate_keys]
      if self.deprecate_keys else [] )

    self._all_keys.extend( self.default.keys() )

    if self.min_keys:
      for k1, k2 in self.min_keys:
        self._all_keys.append(k1)
        self._all_keys.append(k2)

    if self.wedge_keys:
      for k1, k2 in self.wedge_keys:
        self._all_keys.append(k1)
        self._all_keys.append(k2)

    if self.mutex_keys:
      for k1, k2 in self.mutex_keys:
        self._all_keys.append(k1)
        self._all_keys.append(k2)

    self._validating = False
    self._validate()

  #-----------------------------------------------------------------------------
  def _validate(self):
    if self._validating:
      return

    with validating(self):
      self.update( **self.validator( valid_keys(
        self.name,
        self,
        key_valid = self.key_valid,
        value_valid = self.value_valid,
        item_valid = self.item_valid,
        allow_keys = self.allow_keys,
        require_keys = self.require_keys,
        min_keys = self.min_keys,
        wedge_keys = self.wedge_keys,
        mutex_keys = self.mutex_keys,
        deprecate_keys = self.deprecate_keys,
        forbid_keys = self.forbid_keys,
        default = self.default ) ) )

  #-----------------------------------------------------------------------------
  def clear( self ):
    super().clear()
    self._validate()

  #---------------------------------------------------------------------------#
  def update(self, *args, **kwargs ):

    super().update(*args, **kwargs)
    self._validate()

  #-----------------------------------------------------------------------------
  def pop( self, *args, **kwargs ):
    super().pop(*args, **kwargs)
    self._validate()

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    super().__setitem__(key, val)
    self._validate()

  #-----------------------------------------------------------------------------
  def __setattr__( self, name, val ):

    try:

      if name in self._all_keys:
        super().__getattribute__(name)

      object.__setattr__( self, name, val )

    except AttributeError as e:

      self[name] = val
      self._validate()

  #-----------------------------------------------------------------------------
  def __getattribute__( self, name ):
    try:
      return super().__getattribute__(name)

    except AttributeError as e:

      return self[name]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class valid_list(list):
  name = ''
  value_valid = None

  #---------------------------------------------------------------------------#
  def __init__( self, vals = None ):

    self.value_valid = valid(self.value_valid)

    vals = vals or list()
    vals = [ self.value_valid(v) for v in vals ]
    super().__init__(vals)

  #-----------------------------------------------------------------------------
  def clear( self ):
    super().clear()

  #---------------------------------------------------------------------------#
  def append(self, val ):
    val = self.value_valid(val)
    super().append(val)

  #---------------------------------------------------------------------------#
  def extend(self, vals ):
    vals = [ self.value_valid(v) for v in vals ]
    super().extend(vals)

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    val = self.value_valid(val)
    super().__setitem__(key, val)

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
