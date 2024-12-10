from collections.abc import (
  Iterable)
from email.utils import parseaddr
from importlib.metadata import metadata
from partis.pyproj import (
  norm_dist_name)

#===============================================================================
def get_meta(package):

  meta = metadata(package)
  project = meta['Name']
  version = meta['Version']
  description = meta['Summary']

  author = (
    meta.get('Author')
    or meta.get('Author-email')
    or meta.get('Maintainer')
    or meta.get('Maintainer-email') )

  if isinstance(author, Iterable) and not isinstance(author, str):
    author = list(author)
    if author:
      author = author[0]
    else:
      author = 'unknown'

  author, email = parseaddr( author )

  project_normed = norm_dist_name( project )

  return (
    project,
    project_normed,
    version,
    description,
    author,
    email )

#===============================================================================
copyright_year = 2024
project, project_normed, version, description, author, email = get_meta('partis-pyproj')
release = version
copyright = f'{copyright_year}, {author} ( {email} )'

needs_sphinx = '3.1'
extensions = [
  'sphinx.ext.autodoc',
  'sphinx.ext.napoleon',
  'sphinx.ext.intersphinx',
  'sphinx.ext.viewcode',
  'sphinx_copybutton',
  'sphinx_design']
source_suffix = '.rst'
root_doc = 'index'
language = 'en'
exclude_patterns = ['.git', '.nox', 'tmp', 'build', 'dist', 'examples', 'venv*', 'test', 'Thumbs.db', '.DS_Store', '**.inc.rst', '**/tmp']
todo_include_todos = False
add_module_names = False
numfig = True
footenote_backlinks = False

autodoc_inherit_docstrings = True
autodoc_default_options = {
  'members': True,
  'special-members': False,
  # 'undoc-members': False,
  'exclude-members': None,
  'private-members': False,
  'special-members': False,
  # alphabetical, groupwise, or bysource
  'member-order': 'bysource',
  'show-inheritance' : True }

intersphinx_mapping = {
  'python': ['https://docs.python.org/3', None],
  'setuptools': ['https://setuptools.pypa.io/en/latest', None],
  'mpi4py': ['https://mpi4py.readthedocs.io/en/stable/', None],
  'numpy': ['https://numpy.org/doc/stable/', None],
  'jax': ['https://jax.readthedocs.io/en/latest', None],
  'packaging': ["https://packaging.pypa.io/en/latest/", None]}

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_keyword = False
napoleon_attr_annotations = True
napoleon_use_rtype = False
typehints_use_rtype = False

plot_include_source = True
plot_html_show_source_link = False
plot_html_show_formats = False
html_theme = 'pydata_sphinx_theme'
html_static_path = ['/media/box/projects/moebius-n2212/v310/lib/python3.10/site-packages/nohm/document_module/_static']
html_css_files = ['tables.css', 'custom_sig.css']
templates_path = ['/media/box/projects/moebius-n2212/v310/lib/python3.10/site-packages/nohm/document_module/_templates']
html_logo = '/media/box/projects/moebius-n2212/v310/lib/python3.10/site-packages/nohm/document_module/_static/app_icon.svg'
html_title = 'MOEBIUS 0.0.1'
htmlhelp_basename = 'moebius-0.0.1_doc'
html_copy_source = True
