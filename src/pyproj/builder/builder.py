from __future__ import annotations
import os
import os.path as osp
import tempfile
import sysconfig
import re
from copy import copy
import shutil
import subprocess
from logging import Logger
from pathlib import Path

from ..file import tail
from ..validate import (
  validating,
  ValidationError,
  ValidPathError,
  FileOutsideRootError )

from ..load_module import EntryPoint

from ..path import (
  subdir,
  resolve)

from ..template import (
  template_substitute,
  Namespace)
from ..pptoml import pyproj_targets

ERROR_REC = re.compile(r"error:", re.I)

#===============================================================================
class BuildCommandError(ValidationError):
  pass

#===============================================================================
class Builder:
  """Run build setup, compile, install commands

  Parameters
  ----------
  root:
    Path to root project directory
  targets:
  logger:

  """
  #-----------------------------------------------------------------------------
  def __init__(self,
    pyproj,
    root: str | Path,
    targets: pyproj_targets,
    logger: Logger):

    root = resolve(Path(root))

    self.pyproj = pyproj
    self.root = root
    # isolate (shallow) changes to targets
    self.targets = [copy(v) for v in targets]
    self.clean_dirs = [False]*len(self.targets)
    self.logger = logger
    self.tmpdir = Path(tempfile.mkdtemp(prefix=f"build-{pyproj.project.name}-"))
    self.namespace = Namespace({
      'root': root,
      'pptoml': pyproj.pptoml,
      'project': pyproj.project,
      'pyproj': pyproj.pyproj,
      'config_settings': pyproj.config_settings,
      'targets': targets,
      'env': os.environ,
      'tmpdir': self.tmpdir,
      'config_vars': sysconfig.get_config_vars()},
      root=root,
      # better way for builders to whitelist templated directories?
      dirs=[self.tmpdir, Path(tempfile.gettempdir())/'partis-pyproj-downloads'])

  #-----------------------------------------------------------------------------
  def __enter__(self):
    return self

  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback):
    self.build_clean()

    # do not handle any exceptions here
    return False

  #-----------------------------------------------------------------------------
  def build_targets(self):
    exclusive = {
      target.exclusive: None
      for target in self.targets
      if target.exclusive}

    if exclusive:
      for i, target in enumerate(self.targets):
        if not (group := target.exclusive):
          continue

        cur = exclusive[group]

        if target.enabled:
          if cur is None:
            exclusive[group] = i


      missing = [group for group, idx in exclusive.items() if idx is None]

      if missing:
        raise ValidationError(f"Exclusive group {missing} does not have an enabled target")

    for i, target in enumerate(self.targets):
      if not target.enabled:
        self.logger.info(f"Skipping targets[{i}], disabled for environment markers")
        continue

      if (group := target.exclusive) and (group_idx := exclusive.get(group)) != i:
        self.logger.warning(
          f"Skipping targets[{i}], exclusive group {group!r} already satisfied by targets[{group_idx}]")

      # each target isolated (shallow) changes to namespace
      namespace = copy(self.namespace)

      # check paths
      for k in ('work_dir', 'src_dir', 'build_dir', 'prefix'):
        with validating(key = f"tool.pyproj.targets[{i}].{k}"):
          rel_path = target[k]
          rel_path = template_substitute(rel_path, namespace)

          if rel_path.is_absolute():
            abs_path = rel_path
          else:
            abs_path = self.root/rel_path

          abs_path = resolve(abs_path)

          if not (subdir(self.root, abs_path, check=False) or subdir(self.tmpdir, abs_path, check=False)):
            raise FileOutsideRootError(
              f"Must be within project root directory or tmpdir:"
              f"file = \"{abs_path}\",  root = \"{self.root}\"")

          if k in ('build_dir', 'prefix') and subdir(abs_path, self.root, check=False):
            raise ValidPathError(
              f"'{k}' cannot be project root directory:"
              f"file = \"{abs_path}\",  root = \"{self.root}\"")

          target[k] = abs_path
          namespace[k] = abs_path

      src_dir = target.src_dir
      build_dir = target.build_dir
      prefix = target.prefix
      work_dir = target.work_dir

      with validating(key = f"tool.pyproj.targets[{i}].src_dir"):
        if not src_dir.exists():
          raise ValidPathError(f"Source directory not found: {src_dir}")

        if not src_dir.is_dir():
          raise ValidPathError(f"Source directory not a directory: {src_dir}")

      with validating(key = f"tool.pyproj.targets[{i}]"):
        if subdir(build_dir, prefix, check=False):
          raise ValidPathError(
            f"'prefix' cannot be inside 'build_dir', which will be cleaned: {build_dir} > {prefix}")

      build_dirty = build_dir.exists() and any(build_dir.iterdir())

      if target.build_clean and build_dirty:
        raise ValidPathError(
          f"'build_dir' is not empty, please remove manually."
          f" If this was intended, set 'build_clean = false': {build_dir}")

      # create output directories
      for k in ['build_dir', 'prefix']:
        with validating(key = f"tool.pyproj.targets[{i}].{k}"):
          target[k].mkdir(parents=True, exist_ok=True)

      with validating(key = f"tool.pyproj.targets[{i}].options"):
        # original target options remain until evaluated
        options = target.options

        # top-level options updated in order of appearance
        _options = {}
        namespace['options'] = _options

        for k,v in options.items():
          v = template_substitute(v, namespace)
          # update target
          options[k] = v
          # update
          _options[k] = v

      with validating(key = f"tool.pyproj.targets[{i}].env"):
        # original target options remain until evaluated
        env = target.env

        # top-level options updated in order of appearance
        # copy of environment dict, each target isolated changes
        _env = copy(namespace['env'])
        namespace['env'] = _env

        for k,v in env.items():
          v = template_substitute(v, namespace)
          env[k] = v
          _env[k] = v

      for attr in ['setup_args', 'compile_args', 'install_args']:
        with validating(key = f"tool.pyproj.targets[{i}].{attr}"):
          value = target[attr]
          value = template_substitute(value, namespace)

          target[attr] = value
          namespace[attr] = value

      entry_point = EntryPoint(
        pyproj = self,
        root = self.root,
        name = f"tool.pyproj.targets[{i}]",
        logger = self.logger,
        entry = target.entry)

      log_dir = self.root/'build'/'logs'

      log_dir.mkdir(parents=True, exist_ok=True)

      runner = ProcessRunner(
        logger=self.logger,
        log_dir=log_dir,
        target_name=f"target_{i:02d}",
        env=_env)

      self.logger.info('\n'.join([
        f"targets[{i}]:",
        f"  work_dir: {work_dir}",
        f"  src_dir: {src_dir}",
        f"  build_dir: {build_dir}",
        f"  prefix: {prefix}",
        f"  log_dir: {log_dir}",
        "  options: " + ('\n' if target.options else 'none') + '\n'.join([
          f"    {k}: {v}" for k,v in target.options.items()]),
        "  env: " + ('\n' if target.env else 'default') + '\n'.join([
          f"    {k}: {v}" for k,v in target.env.items()])]))

      cwd = os.getcwd()

      # allow cleaning once the target is validated
      self.clean_dirs[i] = True

      try:
        os.chdir(work_dir)

        entry_point(
          options = target.options,
          work_dir = work_dir,
          src_dir = src_dir,
          build_dir = build_dir,
          prefix = prefix,
          setup_args = target.setup_args,
          compile_args = target.compile_args,
          install_args = target.install_args,
          build_clean = not build_dirty,
          runner = runner)

      finally:
        os.chdir(cwd)

  #-----------------------------------------------------------------------------
  def build_clean(self):
    for i, (target, clean) in enumerate(zip(self.targets, self.clean_dirs)):
      if not clean:
        continue

      build_dir = target.build_dir

      if build_dir is not None and build_dir.exists() and target.build_clean:
        self.logger.info(f"Removing build dir: {build_dir}")
        shutil.rmtree(build_dir)

    shutil.rmtree(self.tmpdir)

#===============================================================================
class ProcessRunner:
  #-----------------------------------------------------------------------------
  def __init__(self,
      logger,
      log_dir: Path,
      target_name: str,
      env: dict):

    self.logger = logger
    self.log_dir = log_dir
    self.target_name = target_name
    self.commands = {}
    self.env = env

  #-----------------------------------------------------------------------------
  def run(self, args: list, env: dict = None):
    if len(args) == 0:
      raise ValueError(f"Command for {self.target_name} is empty.")

    cmd_exec = args[0]
    cmd_exec_src = shutil.which(cmd_exec)

    if cmd_exec_src is None:
      raise ValidationError(
        f"Executable does not exist or has in-sufficient permissions: {cmd_exec}")

    # cmd_exec_src = resolve(Path(cmd_exec_src))
    cmd_exec_src = Path(cmd_exec_src)
    cmd_name = cmd_exec_src.name
    args = [str(cmd_exec_src)]+args[1:]

    cmd_hist = self.commands.setdefault(cmd_exec_src, [])
    cmd_idx = len(cmd_hist)
    cmd_hist.append(args)

    run_name = re.sub(r'[^\w]+', "_", cmd_name)
    run_id = f"{self.target_name}.{run_name}.{cmd_idx:02d}"

    stdout_file = self.log_dir/f"{run_id}.log"

    try:
      self.logger.info(f"Running {run_id!r}: "+' '.join(args))

      with open(stdout_file, 'wb') as fp:
        subprocess.run(
          args,
          shell=False,
          stdout=fp,
          stderr=subprocess.STDOUT,
          check=True,
          env=self.env)

    except subprocess.CalledProcessError as e:


      num_windows = 20
      window_size = 5
      with open(stdout_file, 'rb') as fp:
        lines = [
          (lineno,line)
          for lineno,line in enumerate(fp.read().decode('utf-8', errors='replace').splitlines())]

      suspect_linenos = [
        lineno
        for lineno,line in lines
        if ERROR_REC.search(line)]

      # suspect_linenos = suspect_linenos[:num_windows]

      extra = [
        '\n'.join(
          [f"{'':-<70}",f"{'':>4}⋮"]
          +[f"{j:>4d}| {line}" for j,line in lines[i:i+window_size]]
          +[f"{'':>4}⋮"])
        for i in suspect_linenos]

      m = len(lines)-num_windows

      if suspect_linenos:
        m = max(m, suspect_linenos[-1])

      last_lines = lines[m:]

      if last_lines:
        extra += [
          f"{'':-<70}",
          f"Last {len(last_lines)} lines of command output:",
          f"{'':>4}⋮"]

        extra += [
          f"{j:>4d}| {line}"
          for j,line in last_lines]

      extra += [
        f"{'END':>4}| [See log file: {stdout_file}]",
        f"{'':-<70}",]

      raise BuildCommandError(
        str(e),
        extra='\n'.join(extra)) from None
