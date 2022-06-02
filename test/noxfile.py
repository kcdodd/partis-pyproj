#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# This is the config file for running the nox testing automation tool
# This will run pytest and generate a combined coverage report for all runs

import nox
import sys
import os
import os.path as osp
import re
import tomli
import itertools
import subprocess

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Config
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
test_dir = osp.dirname(osp.abspath(__file__))
root_dir = osp.join( test_dir, os.pardir )
source_dir =  osp.join( root_dir, 'src' )
pptoml_file = osp.join( root_dir, 'pyproject.toml' )
sitcustom_dir = osp.join( test_dir, 'sitecustom' )
flake8_file = osp.join( test_dir, '.flake8' )

with open( pptoml_file, 'r' ) as fp:
  pptoml = tomli.loads( fp.read() )

opt_deps = pptoml['project']['optional-dependencies']

test_deps = opt_deps['test']
test_deps += [sitcustom_dir]

cov_deps = opt_deps['cov']
lint_deps = opt_deps['lint']

ppnox = pptoml['tool']['noxfile']
python_versions = ppnox['python']
nox.options.envdir = osp.join( root_dir, ppnox['envdir'] )
nox.options.default_venv_backen = 'venv'


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Sessions
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@nox.session()
def prepare(session):
  session.chdir('..')

  session.install(*cov_deps)

  session.env['COVERAGE_RCFILE'] = pptoml_file

  session.run('coverage', 'erase')

  session.run(
    'python',
    '-m',
    'make_dists',
    '--no-doc' )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# successivly build and install sdist/wheel, run tests as individual sub-projects
@nox.session(
  python = python_versions )
def test( session ):

  session.chdir('..')

  # coverage data for this sessions
  name = re.sub(r"[^A-Za-z0-9]+", "", session.name )
  session.env['COVERAGE_FILE'] = osp.join( root_dir, 'tmp', f'.coverage.{name}' )

  # global coverage config
  session.env['COVERAGE_RCFILE'] = pptoml_file

  # initialize in subprocess coverage hook
  session.env['COVERAGE_PROCESS_START'] = pptoml_file

  # this is so the sdist/wheel can be found by pip to resolve inter-package deps.
  session.env['PIP_FIND_LINKS'] = osp.join(root_dir, 'dist')

  # remove from the pip cache to prevent using a previously installed distro.
  session.run(
    'python3',
    '-m',
    'pip',
    'cache',
    'remove',
    "'partis-pyproj'" )

  session.install(
    *test_deps,
    'partis-pyproj' )

  session.run(
    'pytest',
    test_dir )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@nox.session( venv_backend = 'venv' )
def report(session):
  session.chdir('..')

  session.install(*cov_deps)

  session.env['COVERAGE_RCFILE'] = pptoml_file

  session.run('coverage', 'combine')
  session.run('coverage', 'report')
  session.run('coverage', 'html')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# @nox.session()
# def lint(session):
#   session.chdir('..')
#
#   session.install(*lint_deps)
#
#   session.run(
#     'python3',
#     '-m',
#     'pyflakes',
#     source_dir )
