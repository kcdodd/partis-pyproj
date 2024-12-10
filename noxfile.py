#===============================================================================
# This is the config file for running the nox testing automation tool
# This will run pytest and generate a combined coverage report for all runs
from __future__ import annotations
import nox
from logging import getLogger
import sys
import os
import re
import tomli
import subprocess
from pathlib import Path

log = getLogger(__name__)

#===============================================================================
# Config
#===============================================================================

root_dir = Path(__file__).resolve().parent
# needed to import pkgaux
sys.path.insert(0, str(root_dir))

is_repo = (root_dir/'.git').exists()

#...............................................................................
pptoml_file = root_dir/'pyproject.toml'
source_dir = root_dir/'src'
pkgaux_dir = root_dir/'pkgaux'

test_dir = root_dir/'tests'

work_dir = Path(os.environ.get('PIPELINE_ROOT', root_dir))
tmp_dir = work_dir/'tmp'
dist_dir = work_dir/'dist'
build_dir = work_dir/'build'
reports_dir = work_dir/'reports'


pptoml = tomli.loads(pptoml_file.read_text())

pkg = pptoml['project']['name']
opt_deps = pptoml['project']['optional-dependencies']
version = pptoml['project']['version']

sdist_dir = dist_dir/f"{pkg.replace('-','_')}-{version}"
sdist_file = dist_dir/f"{sdist_dir.name}.tar.gz"
docdist_file = dist_dir/f"{sdist_dir.name}-doc.tar.gz"

ppnox = pptoml['tool']['noxfile']
python_versions = ppnox['python']

nox.options.stop_on_first_error = True
nox.options.envdir = str(tmp_dir / '.nox')
nox.options.default_venv_backen = 'venv'

sitcustom_dir = test_dir/'cov_sitecustom'

#===============================================================================
# Commands
#===============================================================================
from pkgaux.utils import (  # noqa: E402
  env_prepend,
  mkdir,
  remove,
  run,
  install,
  clear_pip_cache,
  run_cmds)

# needed for installing distributions
env_prepend(os.environ, 'PIP_FIND_LINKS', dist_dir, ' ')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
clean_cmds = [
  remove(build_dir),
  remove(dist_dir),
  remove(tmp_dir),
  remove(reports_dir)]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
prepare_cmds = [
  { ('deps', 'Re-installing build requirements'): [
      install('-r', pkgaux_dir/'base_requirements.txt'),
      clear_pip_cache(pkg),
      mkdir(build_dir),
      mkdir(dist_dir),
      mkdir(tmp_dir),
      mkdir(reports_dir)],
    ('sdist', 'Building source distributions'): [{
      'clean': [
        remove([sdist_dir, sdist_file])],
      'build': [
        run('python3', '-m', 'build', '--sdist', '-o', dist_dir, '.')]}] }]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
doc_cmds = [{
  (f'docdist_{pkg}', f'Building documentation {pkg} {version}'): [
    install('-r', pkgaux_dir/'doc_requirements.txt'),
    dist_dir,
    remove(docdist_file),
    install(str(sdist_file)),
    run('tar', 'zxf', sdist_file),
    sdist_dir,
    # build documentation
    run('python3', '-m', 'docs', '-b', 'html', '-o', dist_dir) ]}]

#===============================================================================
# Sessions
#===============================================================================
@nox.session()
def clean(session):
  run_cmds(session, 0, 'clean', clean_cmds)

#===============================================================================
@nox.session()
def prepare(session):
  if is_repo:
    session.log(f"Preparing distribution for {pkg}")
    session.log(f"  root          : {root_dir}")
    session.log(f"  dist_dir      : {dist_dir}")

    run_cmds(session, 0, 'prepare', prepare_cmds)
  else:
    session.log(f"No preparation, running as distribution of {pkg}")

#===============================================================================
@nox.session()
def doc(session):
  session.log(f"Building documentation for {pkg}")
  session.log(f"  root          : {root_dir}")
  session.log(f"  dist_dir      : {dist_dir}")

  name = re.sub(r"[^A-Za-z0-9]+", "", session.name)
  session.env['COVERAGE_FILE'] = os.fspath(tmp_dir/f'.coverage.{name}')

  # initialize in subprocess coverage hook
  session.install(sitcustom_dir)
  session.env['COVERAGE_PROCESS_START'] = str(pptoml_file)
  run_cmds(session, 0, 'build_doc', doc_cmds)

#===============================================================================
# successivly build and install sdist/wheel, run tests as individual sub-projects
@nox.session(
  python = python_versions)
def test(session):
  session.install(
    '-r',
    pkgaux_dir/'test_requirements.txt')

  # coverage data for this sessions
  name = re.sub(r"[^A-Za-z0-9]+", "", session.name)
  session.env['COVERAGE_FILE'] = os.fspath(tmp_dir/f'.coverage.{name}')

  # global coverage config
  session.env['COVERAGE_RCFILE'] = str(pptoml_file)

  # initialize in subprocess coverage hook
  session.install(sitcustom_dir)
  session.env['COVERAGE_PROCESS_START'] = str(pptoml_file)

  session.install(
    # needed for gathering coverage from temporary build installs
    '--no-clean',
    sdist_file)

  session.run(
    'python3',
    '-m',
    'pytest',
    test_dir)

  _env = {'COVERAGE_FILE': os.fspath(tmp_dir/f'.coverage')}
  session.run('coverage', 'combine', success_codes=[0, 1], env=_env)
  session.run('coverage', 'report', success_codes=[0, 1], env=_env)

#===============================================================================
@nox.session( venv_backend = 'venv' )
def report(session):
  session.install(
    '-r',
    pkgaux_dir/'test_requirements.txt')

  session.env['COVERAGE_FILE'] = str( tmp_dir/'.coverage' )
  session.env['COVERAGE_RCFILE'] = str(pptoml_file)

  # NOTE: avoid error when theres nothing to combine
  session.run('coverage', 'combine', success_codes=[0, 1])
  session.run('coverage', 'report')

  session.run('coverage', 'json', '-o', str(reports_dir/'coverage.json'))
  session.run('coverage', 'html', '--directory', str(reports_dir/'htmlcov'))


#===============================================================================
# @nox.session()
# def lint(session):
#   session.chdir(root_dir)
#
#   session.install(*lint_deps)
#
#   session.run(
#     'python3',
#     '-m',
#     'pyflakes',
#     root_dir )
