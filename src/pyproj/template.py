from __future__ import annotations
import re
from pathlib import Path
from collections.abc import (
  Sequence,
  Mapping)
from string import Template

namespace_sep = re.compile(r"[\.\[\]]")

#===============================================================================
class NamespaceTemplate(Template):
  r"""Template subclass to support nested mappings using :class:`Namespace`
  """
  idpattern = r"[A-Z_][A-Z0-9_]*(\.[A-Z0-9_]+|\[-?[0-9]+\])*"

#===============================================================================
class Namespace(Mapping):
  r"""Namespace mapping for using with :class:`NamespaceTemplate`
  """
  #-----------------------------------------------------------------------------
  def __init__(self, data: Mapping):
    self.data = data

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
  def __getitem__(self, name):
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
            raise TypeError(f"Expected mapping or sequence for '{k}': {type(data).__name__}")

          cur.append(k)

    except (KeyError,TypeError,IndexError) as e:
      raise KeyError(f"Invalid key '{k}' of name '{name}': {str(e)}") from None

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
    return cls(NamespaceTemplate(value).substitute(namespace))

  if isinstance(value, Path):
    return cls(*(
      NamespaceTemplate(v).substitute(namespace)
      for v in value.parts))

  if isinstance(value, Mapping):
    return cls({
      k: NamespaceTemplate(v).substitute(namespace) if isinstance(v, str) else v
      for k,v in value.items()})

  if isinstance(value, Sequence):
    return cls([
      NamespaceTemplate(v).substitute(namespace)
      for v in value])


  raise TypeError(f"Unknown template value type: {value}")

