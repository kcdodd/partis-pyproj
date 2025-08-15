from __future__ import annotations
import re
from copy import copy
from pathlib import Path
from collections.abc import (
  Sequence,
  Mapping)
# from string import Template

from .validate import (
  ValidationError,
  FileOutsideRootError)
from .path import (
  subdir,
  resolve)

namespace_sep = re.compile(r"[\.\[\]]")

_idpattern = re.compile(r"""(?:
  # references a template variable
  [A-Z_][A-Z0-9_]* # Python identifier
  (?:
    \.[A-Z_][A-Z0-9_]* # attribute access by Python identifier
    |
    \[-?[0-9]+\])* # integer index (potentially negative)
  |
  \/ # forward slash separate for building path
  |
  (?<=\/)\.\. # double-dot (parent directory), must follow a slash
  |
  '[A-Z0-9\-_\.]+' # string literal, quotes to be removed
  )+
  """,
  re.IGNORECASE|re.VERBOSE)

_group_pattern = re.compile(
  # NOTE: handles escaped '$' and missing closing brace
  r"\$(?:(?P<escaped>\$)|{ *(?P<braced>[^\s\}]+) *(?:}|(?P<unterminated>$|[^}])))",
  re.IGNORECASE)

#===============================================================================
class TemplateError(ValidationError):
  ...

#===============================================================================
class NamespaceError(ValidationError):
  ...

#===============================================================================
class Template:
  r"""Template support nested mappings and paths using :class:`Namespace`
  """

  #-----------------------------------------------------------------------------
  def __init__(self, template):
    self.template = template

  #-----------------------------------------------------------------------------
  def substitute(self, namespace: Mapping = None, /, **kwargs):
    if namespace is None:
      namespace = kwargs

    elif kwargs:
      raise TypeError("Cannot use both namespace and kwargs")

    if not isinstance(namespace, Namespace):
      namespace = Namespace(namespace)

    def _handler(m):
      if m.group('escaped'):
        return '$'

      if m.group('unterminated') is not None:
        raise TemplateError(f"Unterminated template substitution {m.group()!r}: {self.template!r}")

      name = m.group('braced').strip()

      if not _idpattern.fullmatch(name):
        raise TemplateError(f"Invalid template substitution {name!r}: {self.template!r}")

      return str(namespace[name])

    return _group_pattern.sub(_handler, self.template)

#===============================================================================
class Namespace(Mapping):
  r"""Namespace (potentially nested) mapping for using with :class:`Template`

  Parameters
  ----------
  data:
    Mapping for names to values. Note that changes to the namespace will also
    change the data. Making a shallow copy of the namespace also make a shallow
    copy of the data.
  root:
    If given, absolute path to project root, used to resolve relative paths and ensure
    any derived paths are within this parent directory.
  dirs:
    Additional white-listed directories to allow paths
  """
  __slots__ = ['data', 'root', 'dirs']

  #-----------------------------------------------------------------------------
  def __init__(self, data: Mapping, *, root: Path = None, dirs: list[Path]|None = None):
    if dirs is None:
      dirs = []
    elif isinstance(dirs, Path):
      dirs = [dirs]

    self.data = data
    self.root = root
    self.dirs = dirs

  #-----------------------------------------------------------------------------
  def __iter__(self):
    return iter(self.data)

  #-----------------------------------------------------------------------------
  def __len__(self):
    return len(self.data)

  #-----------------------------------------------------------------------------
  def __setitem__(self, name, value):
    self.data[name] = value

  #-----------------------------------------------------------------------------
  def __getitem__(self, key):
    raw_segments = key.split('/')
    segments = []

    for name in raw_segments:
      if len(name) == 0 or name == '..':
        # empty segment
        segments.append(name)

      elif name.startswith("'"):
        # string literal, remove quotes
        segments.append(name[1:-1])

      else:
        # variable name lookup
        segments.append(self.lookup(name))

    if len(segments) == 1:
      return segments[0]

    if self.root is None:
      out = Path(*segments)

    else:
      root = self.root
      out = type(root)(*segments)

      if not out.is_absolute():
        out = root/out

      if isinstance(root, Path):
        # NOTE: ignored if root is a pure path
        out = resolve(out)

      if any(subdir(v, out, check = False) for v in self.dirs):
        ...

      elif not subdir(root, out, check = False):
        raise FileOutsideRootError(
          f"Must be within project root directory:"
          f"\n  file = \"{out}\"\n  root = \"{root}\"")

    return out

  #-----------------------------------------------------------------------------
  def __copy__(self):
    cls = type(self)
    obj = cls.__new__(cls)
    obj.data = copy(self.data)
    obj.root = self.root
    obj.dirs = self.dirs
    return obj

  #-----------------------------------------------------------------------------
  def lookup(self, name):
    parts = namespace_sep.split(name)
    data = self.data

    try:
      cur = []

      for k in parts:
        if k:
          if isinstance(data, Mapping):
            data = data[k]
          elif not isinstance(data, (str,bytes)) and isinstance(data, Sequence):
            i = int(k)
            data = data[i]
          else:
            raise NamespaceError(f"Expected mapping or sequence for '{k}': {type(data).__name__}")

          cur.append(k)

    except (KeyError,TypeError,IndexError) as e:
      raise NamespaceError(f"Invalid key '{k}' of name '{name}': {str(e)}") from None

    return data

#===============================================================================
def template_substitute(
    value: bool|int|str|Path|Mapping|Sequence,
    namespace: Mapping):
  r"""Recursively performs template substitution based on type of value
  """

  if not isinstance(namespace, Namespace):
    namespace = Namespace(namespace)

  if isinstance(value, (bool,int)):
    # just handles case where definitely not a template
    return value

  cls = type(value)

  if isinstance(value, str):
    return cls(Template(value).substitute(namespace))

  if isinstance(value, Path):
    return cls(Template(str(value)).substitute(namespace))
    # return cls(*(
    #   Template(v).substitute(namespace)
    #   for v in value.parts))

  if isinstance(value, Mapping):
    return cls({
      k: template_substitute(v, namespace)
      for k,v in value.items()})

  if isinstance(value, Sequence):
    return cls([
      template_substitute(v, namespace)
      for v in value])


  raise TypeError(f"Unknown template value type: {value}")

