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
  allow_keys = None,
  require_keys = None,
  min_keys = None,
  wedge_keys = None,
  mutex_keys = None,
  deprecate_keys = None,
  default = None ):
  """Check that a mapping does not contain un-expected keys
  """

  if not isinstance( obj, Mapping ):
    raise ValidationError(
      f"{name} must be mapping: {type(obj)}" )

  if deprecate_keys:
    for k_old, k_new in deprecate_keys:
      if k_old in obj:
        if k_new:
          warnings.warn(f"Use of {name} key '{k_old}' is deprecated, replaced by '{k_new}'")

          if k_new not in obj:
            obj[k_new] = obj[k_old]

        else:
          warnings.warn(f"Use of {name} key '{k_old}' is deprecated")

        obj.pop(k_old)

  if default is not None:

    for k, v in default.items():

      restricted = False

      if isinstance(v, type):

        if issubclass(v, valid_dict):
          try:
            obj[k] = v( obj.get(k, dict() ) )
            continue
          except ValidationError as e:
            raise ValidationError(f"{name} key '{k}' sub-mapping not validated") from e

        elif k in obj:
            _v = obj[k]

            if isinstance(_v, v):
              continue

            try:
              obj[k] = v(_v)
              continue
            except Exception as e:
              raise ValidationError(f"{name} key '{k}' not cast to {v.__name__}: {_v}") from e
        else:
          obj[k] = v()
          continue

      elif isinstance(v, Sequence) and not isinstance(v, str):
        opts = v
        restricted = True
      else:
        opts = [v]

      if len(opts) == 0:
        raise ValidationError(
          f"{name} default for key '{k}' cannot be an empty list: {opts}")

      # default value and type is first item in list
      v = opts[0]

      typ = valid_type(
        f'{name} key {k} default',
        v,
        [bool, int, float, str] )

      for i, _v in enumerate(opts[1:]):
        valid_type(
          f"{name} key '{k}' option[{i+1}]",
          _v,
          [typ] )

      if k not in obj or obj[k] is None:
        obj[k] = v

      else:
        _v = obj[k]

        if typ is bool:
          t = [True, 'true', 'True', 'yes', 'y', 'enable', 'enabled']
          f = [False, 'false', 'False', 'no', 'n', 'disable', 'disabled']

          if _v not in t + f:
            raise ValidationError(
              f"{name} key '{k}' could not be interpreted as boolean: {_v}")

          _v = True if _v in t else False

        elif typ is int:
          try:
            _v = int(_v)
          except Exception as e:
            raise ValidationError(
              f"{name} key '{k}' could not be interpreted as integer: {_v}") from e

        elif typ is float:
          try:
            _v = float(_v)
          except Exception as e:
            raise ValidationError(
              f"{name} key '{k}' could not be interpreted as float: {_v}") from e

        if restricted and _v not in opts:
          raise ValidationError(
            f"{name} key '{k}' is restricted to one of {opts}: {_v}")

        obj[k] = _v

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
  allow_keys = None
  require_keys = None
  min_keys = None
  wedge_keys = None
  mutex_keys = None
  deprecate_keys = None
  default = None

  # internal
  _all_keys = list()

  #---------------------------------------------------------------------------#
  def __init__( self, *args, **kwargs ):
    super().__init__(*args, **kwargs)

    self._all_keys = list()
    self._all_keys.extend( self.require_keys or [] )
    self._all_keys.extend(
      [ k_new for k_old, k_new in self.deprecate_keys]
      if self.deprecate_keys else [] )
      
    self._all_keys.extend( self.default.keys() if self.default else [] )

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
      self.update( valid_keys(
        self.name,
        self,
        allow_keys = self.allow_keys,
        require_keys = self.require_keys,
        min_keys = self.min_keys,
        wedge_keys = self.wedge_keys,
        mutex_keys = self.mutex_keys,
        deprecate_keys = self.deprecate_keys,
        default = self.default ) )

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
  allow_type = None

  #---------------------------------------------------------------------------#
  def __init__( self, vals = None ):
    vals = vals or list()

    vals = [ v if isinstance(v, self.allow_type) else self.allow_type(v)
      for v in vals ]

    super().__init__(vals)

  #-----------------------------------------------------------------------------
  def clear( self ):
    super().clear()

  #---------------------------------------------------------------------------#
  def append(self, val ):

    if not isinstance(val, self.allow_type):
      val = self.allow_type(val)

    super().append(val)

  #---------------------------------------------------------------------------#
  def extend(self, vals ):

    vals = [ v if isinstance(v, self.allow_type) else self.allow_type(v)
      for v in vals ]

    super().extend(vals)

  #-----------------------------------------------------------------------------
  def __setitem__( self, key, val ):
    if not isinstance(val, self.allow_type):
      val = self.allow_type(val)

    super().__setitem__(key, val)
