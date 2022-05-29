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
class Special:
  def __str__(self):
    return type(self).__name__

class Optional(Special):
  """Optional value
  """
  pass

class Required(Special):
  """Required value
  """
  pass

class NotSet(Special):
  pass

optional = Optional()
required = Required()
notset = NotSet()

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
      errs = list()

      for _validator in validator[::-1]:
        try:
          val = validate(val, required, _validator)
          break
        except Exception as e:
          errs.append((_validator, e))

      else:
        if errs:
          errs = '\n'.join([f"- {k} -> {v}" for k,v in errs])
          raise ValidationError(f"Union of validators failed:\n{errs}")

  return val

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Validator:
  """Validates a value
  """
  #-----------------------------------------------------------------------------
  def __init__(self, *args, default = notset):

    if default is notset:
      default = required

      if len(args):
        args = list(args)
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
            raise ValidationError(
              f"Default value must be specified, or explicitly set as optional or required") from e

        else:
          # cannot be used as default, put back to use as validator
          args.insert(0, v)

    if len(args) == 0 and default not in [required, optional]:
      # convenience method to used default value to derive type
      args.append(type(default))

    self._default = default
    self._validators = args

  #-----------------------------------------------------------------------------
  def __str__(self):
    args = list()
    for v in self._validators:
      if isinstance(v, type):
        args.append(f"<type {v.__name__}>")
      elif isinstance(v, Validator):
        args.append(str(v))
      elif callable(v):
        args.append('<function>')
      elif v == '':
        args.append("''")
      else:
        args.append(str(v))

    v = self._default
    if v == '':
      v = "''"

    args.append(f"default = {v}")
    args = ', '.join(args)
    return f"{type(self).__name__}({args})"

  #-----------------------------------------------------------------------------
  def __repr__(self):
    return str(self)

  #-----------------------------------------------------------------------------
  def __call__(self, val):
    print(str(self))
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
  """Casts list of objects to validator
  """
  if len(validators) == 1:
    v = validators[0]

    if isinstance(v, Validator):
      return v

    elif any(isinstance(v, t) for t in [bool, int, float, str, Sequence, Mapping]):
      return Validator(v, type(v))

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

  Parameters
  ----------
  name : str
    Name of the validation
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
      for keys in min_keys:
        allow_keys.extend(keys)

    if wedge_keys:
      for keys in wedge_keys:
        allow_keys.extend(keys)

    if mutex_keys:
      for keys in mutex_keys:
        allow_keys.extend(keys)

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

  See Also
  --------
  * :func:`valid_keys`
  """

  _name = ''
  _proxy_key = None
  _value_valid = None
  _item_valid = None
  _key_valid = None
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

    if (
      self._proxy_key
      and len(kwargs) == 0
      and len(args) == 1
      and not isinstance(args[0], Mapping) ):

      v = args[0]

      if v in [None, optional]:
        args = dict()
      else:
        args = [{self._proxy_key : args[0]}]

    self._p_dict = dict(*args, **kwargs)

    with attrs_modify( self ):
      self._value_valid = valid(self._value_valid) if self._value_valid else None
      self._item_valid = valid(self._item_valid) if self._item_valid else None
      self._key_valid = valid(self._key_valid) if self._key_valid else None

      self._allow_keys = self._allow_keys
      self._require_keys = self._require_keys
      self._min_keys = self._min_keys
      self._wedge_keys = self._wedge_keys
      self._mutex_keys = self._mutex_keys
      self._deprecate_keys = self._deprecate_keys
      self._forbid_keys = self._forbid_keys

      self._default = { k: valid(v) for k,v in ( self._default or dict() ).items() }
      self._validator = valid(self._validator if self._validator else lambda v: v)

      self._p_all_keys = list()
      self._validating = False

    self._p_all_keys.extend( self._require_keys or [] )
    self._p_all_keys.extend( self._default.keys() )

    if self._deprecate_keys:
      for keys in self._deprecate_keys:
        self._p_all_keys.extend(keys)

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
    obj = super().__copy__()
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
    self._p_dict.pop(*args, **kwargs)
    self._validate()

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
          warnings.warn(f"{self._name} attribute shadows mapping key: {name}")

      object.__setattr__( self, name, val )

    except AttributeError as e:

      if name != '_p_dict' and name != '_p_key_attr' and name in self._p_key_attr:
        self._p_dict[ self._p_key_attr[name] ] = val
        self._validate()

      else:
        raise AttributeError(
          f"'{type(self).__name__}' object has no key '{name}'."
          " New keys must be added using a Mapping method;"
          f" E.G. x['{name}'] = {val}" ) from e


  #-----------------------------------------------------------------------------
  def __getattribute__( self, name ):

    try:
      val = super().__getattribute__(name)

      if name != '_p_dict' and name != '_p_key_attr' and name in self._p_key_attr:
        warnings.warn(f"{self._name} attribute shadows mapping key: {name}")

      return val

    except AttributeError as e:
      # only get mapping if base object does not have attribute
      if name != '_p_dict' and name != '_p_key_attr' and name in self._p_key_attr:
        return self._p_dict[ self._p_key_attr[name] ]

      raise AttributeError(
        f"'{type(self).__name__}' object has no key '{name}'") from e


  #-----------------------------------------------------------------------------
  def _validate(self):
    if self._validating:
      return

    with validating(self):
      self.update( **self._validator( valid_keys(
        self._name,
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
        default = self._default ) ) )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class valid_list(list):
  """Validated list
  """
  _name = ''
  _value_valid = None

  #---------------------------------------------------------------------------#
  def __init__( self, vals = None ):

    self._value_valid = valid(self._value_valid)

    vals = vals or list()
    vals = [ self._value_valid(v) for v in vals ]
    super().__init__(vals)

  #-----------------------------------------------------------------------------
  def clear( self ):
    super().clear()

  #---------------------------------------------------------------------------#
  def append(self, val ):
    val = self._value_valid(val)
    super().append(val)

  #---------------------------------------------------------------------------#
  def extend(self, vals ):
    vals = [ self._value_valid(v) for v in vals ]
    super().extend(vals)

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    val = self._value_valid(val)
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
