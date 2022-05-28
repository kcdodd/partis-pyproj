
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from .validate import (
  optional,
  required,
  valid,
  union,
  valid_dict,
  valid_list,
  ValidationError )

from .norms import (
  empty_str,
  nonempty_str,
  str_list,
  nonempty_str_list,
  norm_path,
  norm_path_to_os )

from .pep import (
  norm_printable,
  valid_dist_name,
  norm_dist_version,
  norm_dist_author_dict,
  norm_dist_extra,
  norm_entry_point_group,
  norm_entry_point_name,
  norm_entry_point_ref,
  norm_dist_keyword,
  norm_dist_classifier,
  norm_dist_url )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class readme(valid_dict):
  name = 'project.readme'
  proxy_key = 'file'
  min_keys = [
    ('file', 'text')]
  mutex_keys = [
    ('file', 'text')]
  default = {
    'file': valid(optional, norm_path, norm_path_to_os),
    'text': valid(optional, norm_printable) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class license(valid_dict):
  name = 'project.license'
  min_keys = [
    ('file', 'text')]
  default = {
    'file': valid(optional, norm_path, norm_path_to_os),
    'text': valid(optional, norm_printable) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class author(valid_dict):
  name = 'project.authors'
  min_keys = [
    ('name', 'email')]
  validator = norm_dist_author_dict

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class authors(valid_list):
  name = 'project.authors'
  value_valid = author

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class maintainer(author):
  name = 'project.maintainers'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class maintainers(valid_list):
  name = 'project.maintainers'
  value_valid = maintainer

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class dependencies(valid_list):
  name = 'project.dependencies'
  value_valid = valid(norm_printable, Requirement, str)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class optional_dependency_group(dependencies):
  name = 'project.optional-dependencies'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class optional_dependencies(valid_dict):
  name = 'project.optional-dependencies'
  key_valid = norm_dist_extra
  value_valid = optional_dependency_group

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class entry_point_group(valid_dict):
  name = 'project.entry-points'
  key_valid = norm_entry_point_name
  value_valid = norm_entry_point_ref

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class scripts(entry_point_group):
  name = 'project.scripts'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class gui_scripts(entry_point_group):
  name = 'project.gui-scripts'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class entry_points(valid_dict):
  name = 'project.entry-points'
  key_valid = norm_entry_point_group
  value_valid = entry_point_group
  forbid_keys = [
    'scripts',
    'console_scripts',
    'gui-scripts',
    'gui_scripts' ]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class keywords(valid_list):
  name = 'project.keywords'
  value_valid = norm_dist_keyword

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class classifiers(valid_list):
  name = 'project.classifiers'
  value_valid = norm_dist_classifier

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class urls(valid_dict):
  name = 'project.urls'
  item_valid = norm_dist_url

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class project(valid_dict):
  name = 'project'
  require_keys = [
    'name']
  default = {
    'dynamic': nonempty_str_list,
    'name': valid_dist_name,
    'version': valid(optional, norm_dist_version),
    'description': valid(optional, norm_printable),
    'readme': valid(optional, readme),
    'license': valid(optional, license),
    'authors': valid(optional, authors),
    'maintainers': valid(optional, maintainers),
    'keywords': valid(optional, keywords),
    'classifiers': valid(optional, classifiers),
    'urls': valid(optional, urls),
    'requires-python': valid(optional, norm_printable, SpecifierSet, str),
    'dependencies': valid(optional, dependencies),
    'optional-dependencies': valid(optional, optional_dependencies),
    'scripts': valid(optional, scripts),
    'gui-scripts': valid(optional, gui_scripts),
    'entry-points': valid(optional, entry_points) }

  #-----------------------------------------------------------------------------
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    for k in self.dynamic:
      if k == 'name':
        raise ValidationError(f"project.dynamic may not contain 'name'")

      if k not in self._all_keys:
        keys = list(self.default.keys())
        raise ValidationError(f"project.dynamic may only contain {keys}: {k}")

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_requires(dependencies):
  name = 'build-system.requires'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class path_parts(valid_list):
  value_valid = nonempty_str

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_system(valid_dict):
  name = 'build-system'
  require_keys = [
    'build-backend']
  default = {
    'requires': build_requires,
    'build-backend': norm_entry_point_ref,
    'backend-path': valid(optional, path_parts) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_prep(valid_dict):
  name = 'tool.pyproj.prep'
  require_keys = [
    'entry' ]
  default = {
    'entry': norm_entry_point_ref,
    'kwargs': dict }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_prep(pyproj_prep):
  name = 'tool.pyproj.dist.prep'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_source_prep(pyproj_prep):
  name = 'tool.pyproj.dist.source.prep'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_binary_prep(pyproj_prep):
  name = 'tool.pyproj.dist.binary.prep'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_meson(valid_dict):
  name = 'tool.pyproj.meson'
  default = {
    'compile': valid(False, norm_bool),
    'src_dir': valid('.', nonempty_str, norm_path, norm_path_to_os),
    'build_dir': valid('build', nonempty_str, norm_path, norm_path_to_os),
    'prefix': valid('build', nonempty_str, norm_path, norm_path_to_os),
    'setup_args': nonempty_str_list,
    'compile_args': nonempty_str_list,
    'install_args': nonempty_str_list,
    'options': dict,
    'build_clean': valid(True, norm_bool) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_copy(valid_dict):
  name = 'tool.pyproj.dist.copy'
  proxy_key = 'src'
  min_keys = [
    ('src', 'glob') ],
  default = {
    'src': valid('', union(empty_str, valid(norm_path, norm_path_to_os))),
    'dst': valid(optional, union(empty_str, valid(norm_path, norm_path_to_os))),
    # TODO; now to normalize patterns?
    'glob': str,
    'ignore': str_list }

  #---------------------------------------------------------------------------#
  def __init__( self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.setdefault('dst', self['src']))

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_copy_list(valid_list):
  name = 'tool.pyproj.dist.copy'
  value_valid = pyproj_dist_copy

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_scheme(valid_dict):
  name = 'tool.pyproj.dist.binary'
  default = {
    'ignore': nonempty_str_list,
    'copy': pyproj_dist_copy_list }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_binary(valid_dict):
  name = 'tool.pyproj.dist.binary'
  default = {
    'prep': valid(optional, pyproj_dist_binary_prep),
    'ignore': nonempty_str_list,
    'copy': pyproj_dist_copy_list,
    'data': pyproj_dist_scheme,
    'headers': pyproj_dist_scheme,
    'scripts': pyproj_dist_scheme,
    'purelib': pyproj_dist_scheme,
    'platlib': pyproj_dist_scheme }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_source(valid_dict):
  name = 'tool.pyproj.dist.source'
  default = {
    'prep': valid(optional, pyproj_dist_source_prep),
    'ignore': nonempty_str_list,
    'copy': pyproj_dist_copy_list,
    'add_legacy_setup': valid(False, norm_bool) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist(valid_dict):
  name = 'tool.pyproj.dist'
  default = {
    'prep': valid(optional, pyproj_dist_prep),
    'ignore': nonempty_str_list,
    'source': pyproj_dist_source,
    'binary': pyproj_dist_binary }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_config(valid_dict):
  name = 'tool.pyproj.config'
  value_valid = union(bool, int, float, nonempty_str)
  key_valid = norm_dist_extra

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj(valid_dict):
  name = 'tool.pyproj'
  default = {
    'config': pyproj_config,
    'prep': valid(optional, pyproj_prep),
    'dist': pyproj_dist,
    'meson': pyproj_meson }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class tool(valid_dict):
  name = 'tool'
  require_keys = ['pyproj']
  default = {
    'pyproj': pyproj }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pptoml(valid_dict):
  name = 'pyproject.toml'
  require_keys = [
    'project',
    'tool',
    'build-system']
  default = {
    'project': project,
    'tool': tool,
    'build-system': build_system }
