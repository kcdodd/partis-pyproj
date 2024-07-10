import os
import re
import shutil
import subprocess
from pathlib import Path

from ..file import tail
from ..validate import (
  validating,
  ValidationError,
  ValidPathError,
  FileOutsideRootError )

from ..load_module import EntryPoint

from ..path import (
  subdir )

ERROR_REC = re.compile(r"error:", re.I)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class BuildCommandError(ValidationError):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Builder:
  """Run build setup, compile, install commands

  Parameters
  ----------
  root : str | pathlib.Path
    Path to root project directory
  targets : :class:`pyproj_build <partis.pyproj.pptoml.pyproj_targets>`
  logger : logging.Logger
  """
  #-----------------------------------------------------------------------------
  def __init__(self,
    pyproj,
    root,
    targets,
    logger):

    self.pyproj = pyproj
    self.root = Path(root).resolve()
    self.targets = targets
    self.logger = logger
    self.target_paths = [
      dict(
        src_dir = target.src_dir,
        build_dir = target.build_dir,
        prefix = target.prefix,
        work_dir = target.work_dir)
      for target in targets ]

  #-----------------------------------------------------------------------------
  def __enter__(self):

    try:
      for i, (target, paths) in enumerate(zip(self.targets, self.target_paths)):
        if not target.enabled:
          self.logger.info(f"Skipping targets[{i}], disabled for environment markers")
          continue

        # check paths
        for k in ['src_dir', 'build_dir', 'prefix', 'work_dir']:
          with validating(key = f"tool.pyproj.targets[{i}].{k}"):

            rel_path = paths[k]

            abs_path = (self.root / rel_path).resolve()

            if not subdir(self.root, abs_path, check = False):
              raise FileOutsideRootError(
                f"Must be within project root directory:"
                f"\n  file = \"{abs_path}\"\n  root = \"{self.root}\"")


            paths[k] = abs_path

        src_dir = paths['src_dir']
        build_dir = paths['build_dir']
        prefix = paths['prefix']
        work_dir = paths['work_dir']

        with validating(key = f"tool.pyproj.targets[{i}].src_dir"):
          if not src_dir.exists():
            raise ValidPathError(f"Source directory not found: {src_dir}")

        with validating(key = f"tool.pyproj.targets[{i}]"):
          if subdir(build_dir, prefix, check = False):
            raise ValidPathError(f"'prefix' cannot be inside 'build_dir': {build_dir}")

        build_dirty = build_dir.exists() and any(build_dir.iterdir())

        if target.build_clean and build_dirty:
          raise ValidPathError(
            f"'build_dir' is not empty, please remove manually."
            f" If this was intended, set 'build_clean = false': {build_dir}")

        for k in ['build_dir', 'prefix']:
          with validating(key = f"tool.pyproj.targets[{i}].{k}"):
            dir = paths[k]

            if dir == self.root:
              raise ValidPathError(f"'{k}' cannot be root directory: {dir}")

            dir.mkdir( parents = True, exist_ok = True )

        entry_point = EntryPoint(
          pyproj = self,
          root = self.root,
          name = f"tool.pyproj.targets[{i}]",
          logger = self.logger,
          entry = target.entry )

        log_dir = self.root/'build'/'logs'
        if not log_dir.exists():
          log_dir.mkdir(parents=True)

        runner = ProcessRunner(
          logger = self.logger,
          log_dir=log_dir,
          target_name=f"target_{i:02d}")

        self.logger.info(f"Build targets[{i}]")
        self.logger.info(f"Working dir: {work_dir}")
        self.logger.info(f"Source dir: {src_dir}")
        self.logger.info(f"Build dir: {build_dir}")
        self.logger.info(f"Log dir: {log_dir}")
        self.logger.info(f"Prefix: {prefix}")

        cwd = os.getcwd()

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

    except:
      self.build_clean()
      raise

  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback):
    self.build_clean()

    # do not handle any exceptions here
    return False

  #-----------------------------------------------------------------------------
  def build_clean(self):
    for i, (target, paths) in enumerate(zip(self.targets, self.target_paths)):
      build_dir = paths['build_dir']

      if build_dir is not None and build_dir.exists() and target.build_clean:
        self.logger.info(f"Removing build dir: {build_dir}")
        shutil.rmtree(build_dir)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ProcessRunner:
  #-----------------------------------------------------------------------------
  def __init__(self,
      logger,
      log_dir: Path,
      target_name: str):

    self.logger = logger
    self.log_dir = log_dir
    self.target_name = target_name
    self.commands = {}

  #-----------------------------------------------------------------------------
  def run(self, args: list):
    if len(args) == 0:
      raise ValueError(f"Command for {self.target_name} is empty.")

    cmd_exec = args[0]
    cmd_exec_src = shutil.which(cmd_exec)

    if cmd_exec_src is None:
      raise ValueError(
        f"Executable does not exist or has in-sufficient permissions: {cmd_exec}")

    cmd_exec_src = Path(cmd_exec_src).resolve()
    cmd_name = cmd_exec_src.name
    args = [str(cmd_exec_src)]+args[1:]

    cmd_hist = self.commands.setdefault(cmd_exec_src, [])
    cmd_idx = len(cmd_hist)
    cmd_hist.append(args)

    run_name = re.sub(r'[^\w]+', "_", cmd_name)

    stdout_file = self.log_dir/f"{self.target_name}.{run_name}.{cmd_idx:02d}.log"

    try:
      self.logger.info("Running command: "+' '.join(args))

      with open(stdout_file, 'wb') as fp:
        subprocess.run(
          args,
          shell=False,
          stdout=fp,
          stderr=subprocess.STDOUT,
          check=True)

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
