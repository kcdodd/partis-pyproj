
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
  norm_bool,
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
  # a string at top-level interpreted as a path to the readme file
  _proxy_key = 'file'
  _allow_keys = list()
  # _min_keys = [
  #   ('file', 'text')]
  _mutex_keys = [
    ('file', 'text')]
  _default = {
    'file': valid(optional, nonempty_str, norm_path, norm_path_to_os),
    'text': valid(optional, nonempty_str, norm_printable) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class license(valid_dict):
  _allow_keys = list()
  # _min_keys = [
  #   ('file', 'text')]
  _default = {
    'file': valid(optional, nonempty_str, norm_path, norm_path_to_os),
    'text': valid(optional, nonempty_str, norm_printable) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class author(valid_dict):
  _validator = valid(norm_dist_author_dict)
  _allow_keys = list()
  _min_keys = [
    ('name', 'email')]
  _default = {
    'name': valid(str),
    'email': valid(str) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class authors(valid_list):
  _value_valid = valid(author)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class maintainer(author):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class maintainers(valid_list):
  _value_valid = valid(maintainer)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class dependencies(valid_list):
  _value_valid = valid(norm_printable, Requirement, str)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class optional_dependency_group(dependencies):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class optional_dependencies(valid_dict):
  _key_valid = valid(norm_dist_extra)
  _value_valid = valid(optional_dependency_group)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class entry_point_group(valid_dict):
  _key_valid = valid(norm_entry_point_name)
  _value_valid = valid(norm_entry_point_ref)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class scripts(entry_point_group):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class gui_scripts(entry_point_group):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class entry_points(valid_dict):
  _key_valid = valid(norm_entry_point_group)
  _value_valid = valid(entry_point_group)

  # PEP 621
  # > Build back-ends MUST raise an error if the metadata defines a
  # > [project.entry-points.console_scripts] or [project.entry-points.gui_scripts]
  # > table, as they would be ambiguous in the face of [project.scripts]
  # > and [project.gui-scripts], respectively.
  _forbid_keys = [
    'scripts',
    'console_scripts',
    'gui-scripts',
    'gui_scripts' ]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class keywords(valid_list):
  _value_valid = valid(norm_dist_keyword)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class classifiers(valid_list):
  _value_valid = valid(norm_dist_classifier)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class urls(valid_dict):
  _item_valid = valid(norm_dist_url)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class project(valid_dict):
  _allow_keys = list()
  _require_keys = [
    'name']
  _default = {
    'dynamic': nonempty_str_list,
    'name': valid_dist_name,
    'version': valid(str, norm_dist_version),
    'description': valid(str, norm_printable),
    'readme': valid(readme),
    'license': valid(license),
    'authors': valid(authors),
    'maintainers': valid(maintainers),
    'keywords': valid(keywords),
    'classifiers': valid(classifiers),
    'urls': valid(urls),
    'requires-python': valid(str, norm_printable, SpecifierSet, str),
    'dependencies': valid(dependencies),
    'optional-dependencies': valid(optional_dependencies),
    'scripts': valid(scripts),
    'gui-scripts': valid(gui_scripts),
    'entry-points': valid(entry_points) }

  #-----------------------------------------------------------------------------
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    for k in self.dynamic:
      if k == 'name':
        raise ValidationError(f"project.dynamic may not contain 'name'")

      if k not in self._p_all_keys:
        keys = list(self._default.keys())
        raise ValidationError(f"project.dynamic may only contain {keys}: {k}")

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_requires(dependencies):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class path_parts(valid_list):
  _value_valid = valid(nonempty_str)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_system(valid_dict):
  _allow_keys = list()
  _require_keys = [
    'build-backend']
  _default = {
    'requires': build_requires,
    'build-backend': norm_entry_point_ref,
    'backend-path': valid(optional, path_parts) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_prep(valid_dict):
  _allow_keys = list()
  _require_keys = [
    'entry' ]
  _default = {
    'entry': norm_entry_point_ref,
    'kwargs': dict }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_prep(pyproj_prep):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_source_prep(pyproj_prep):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_binary_prep(pyproj_prep):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_meson(valid_dict):
  _allow_keys = list()
  _default = {
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
  _proxy_key = 'src'
  _allow_keys = list()
  _min_keys = [
    ('src', 'glob') ]
  _default = {
    'src': valid('', union(empty_str, valid(norm_path, norm_path_to_os))),
    'dst': valid(optional, union(empty_str, valid(norm_path, norm_path_to_os))),
    # TODO; how to normalize patterns?
    'glob': str,
    'ignore': str_list }

  #---------------------------------------------------------------------------#
  def __init__( self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.setdefault('dst', self['src'])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_copy_list(valid_list):
  _value_valid = valid(pyproj_dist_copy)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_scheme(valid_dict):
  _allow_keys = list()
  _default = {
    'ignore': nonempty_str_list,
    'copy': pyproj_dist_copy_list }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist_binary(valid_dict):
  _allow_keys = list()
  _default = {
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
  _allow_keys = list()
  _default = {
    'prep': valid(optional, pyproj_dist_source_prep),
    'ignore': nonempty_str_list,
    'copy': pyproj_dist_copy_list,
    'add_legacy_setup': valid(False, norm_bool) }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_dist(valid_dict):
  _allow_keys = list()
  _default = {
    'prep': valid(optional, pyproj_dist_prep),
    'ignore': nonempty_str_list,
    'source': pyproj_dist_source,
    'binary': pyproj_dist_binary }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj_config(valid_dict):
  _value_valid = union(bool, int, float, nonempty_str)
  _key_valid = valid(norm_dist_extra)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pyproj(valid_dict):
  _allow_keys = list()
  _default = {
    'config': pyproj_config,
    'prep': valid(optional, pyproj_prep),
    'dist': pyproj_dist,
    'meson': pyproj_meson }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class tool(valid_dict):
  _allow_keys = list()
  _require_keys = ['pyproj']
  _default = {
    'pyproj': pyproj }

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class pptoml(valid_dict):
  _allow_keys = list()
  _require_keys = [
    'project',
    'tool',
    'build-system']
  _default = {
    'project': valid(required, project),
    'tool': valid(required, tool),
    'build-system': valid(required, build_system) }