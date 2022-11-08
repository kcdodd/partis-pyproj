#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PathError(ValueError):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def _subdir(_start, _path):

  n = len(_start)

  if len(_path) < n or _path[:n] != _start:
    return None

  return _path[n:]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def subdir(start, path, check = True):
  """Relative path, restricted to sub-directories.

  Parameters
  ----------
  start : PurePath
    Starting directory.
  path : PurePath
    Directory to compute relative path to, *must* be a sub-directory of `start`.

  Returns
  -------
  rpath : PurePath
    Relative path from `start` to `path`.
  """

  _rpath = _subdir(start.parts, path.parts)

  if _rpath is None:
    if check:
      raise PathError(f"Not a subdirectory of {start}: {path}")

    return None
  
  return type(path)(*_rpath)
