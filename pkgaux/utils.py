
from pathlib import Path
import shutil
import hashlib
from collections.abc import Iterable
import functools

#===============================================================================
def env_prepend(obj, name, val, sep):
  val = str(val)
  _val = obj.get(name, '')

  if not _val:
    obj[name] = val
    return

  obj[name] = val + sep + _val

#===============================================================================
def env_append(obj, name, val, sep):
  val = str(val)
  _val = obj.get(name, '')

  if not _val:
    obj[name] = val
    return

  obj[name] = _val + sep + val

#===============================================================================
def env_update(obj, **kwargs):
  kwargs = {str(k):str(v) for k,v in kwargs.items()}

  obj.update(kwargs)

#===============================================================================
def session_command(f):
  @functools.wraps(f)
  def wrapper(*args, **kwargs):
    def _f(session):
      return f(
        session,
        *[v() if callable(v) else v for v in args],
        **{k: v() if callable(v) else v for k,v in kwargs.items()})

    return _f

  return wrapper


#===============================================================================
@session_command
def mkdir(session, path):
  path.mkdir(exist_ok = True, parents = True)


#===============================================================================
@session_command
def remove(session, paths):
  if isinstance(paths, str):
    paths = Path(paths)

  if not isinstance(paths, Iterable):
    paths = [paths]


  for path in paths:
    if not path.exists():
      continue

    session.log(f"Removing: {path}")

    if path.is_dir():
      shutil.rmtree(path)
    else:
      path.unlink()

#===============================================================================
@session_command
def checksum_file(session, file, algo):
  hash = getattr(hashlib, algo)()

  with file.open('rb') as fp:
    for chunk in iter(lambda: fp.read(16384), b""):
      hash.update(chunk)

    hash.update(fp.read())

  content = hash.hexdigest() + f" *{file.name}"
  file_hash = file.parent / f'{file.name}.{algo}'
  file_hash.write_text(content)

  session.log(f"Generated checksum {file_hash.name}: {content}")

#===============================================================================
# remove from the pip cache to prevent using a previously installed distro.
@session_command
def clear_pip_cache(session, pkgs):
  for pkg in pkgs:
    try:
      session.run([
        'python',
        '-m',
        'pip',
        'cache',
        'remove',
        f"'{pkg.replace('-','_')}*'"])
    except:
      pass

  try:
    session.run([
      'python',
      '-m',
      'pip',
      'uninstall',
      '-y',
      *pkgs ])
  except:
    pass

#===============================================================================
@session_command
def run(session, *args):
  session.run(*[str(v) for v in args])


#===============================================================================
def install(*args):
  return run('python', '-m', 'pip', 'install', *args)

#===============================================================================
@session_command
def senv_update(session, **kwargs):
  env_update(session.env, **kwargs)

#===============================================================================
@session_command
def senv_append(session, name, val, sep):
  env_append(session.env, name, val, sep)

#===============================================================================
@session_command
def senv_prepend(session, name, val, sep):
  env_prepend(session.env, name, val, sep)

#===============================================================================
def run_cmds(session, lvl, name, cmds):

  ncmds = len(cmds)

  for idx, cmd in enumerate(cmds):
    _idx = f"[{idx+1}/{ncmds}]"
    stat = f"({name}-{_idx})"

    if isinstance(cmd, dict):
      for k, v in cmd.items():
        if isinstance(k, tuple):
          k, title = k
          session.log(f'({name}-{_idx}-{k}): {title}')

        run_cmds(session, lvl+1, f"{name}-{_idx}-{k}", v)

    elif isinstance(cmd, Path):
      cmd.mkdir(exist_ok = True, parents = True)

      with session.chdir(cmd):
        run_cmds(session, lvl, name, cmds[idx+1:])
        return

    elif isinstance(cmd, str):
      session.log(f'{stat}: {cmd}')

    elif callable(cmd):
      session.log(stat)
      res = cmd(session)

    elif isinstance(cmd, (tuple, list)):
      cmd = [v() if callable(v) else v for v in cmd]
      cmd = [str(v) for v in cmd]

      session.log(stat)

      session.run(*cmd)

    else:
      raise ValueError(f"Not a command: {cmd}")