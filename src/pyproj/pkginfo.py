from __future__ import annotations
import os
import io
from copy import copy
import re
import configparser

from pathlib import (
  Path,
  PurePath,
  PurePosixPath)

from .validate import (
  ValidationError,
  validating,
  valid_type,
  valid_keys )

from .norms import (
  norm_path,
  norm_data,
  norm_zip_external_attr,
  hash_sha256,
  email_encode_items )

from .pep import (
  norm_printable,
  valid_dist_name,
  norm_dist_name,
  norm_dist_version,
  norm_dist_author,
  norm_dist_classifier,
  norm_dist_keyword,
  norm_dist_url,
  norm_dist_extra,
  norm_dist_build,
  norm_dist_compat,
  compress_dist_compat,
  norm_dist_filename,
  norm_entry_point_group,
  norm_entry_point_name,
  norm_entry_point_ref )

from .pptoml import project as pptoml_project

import configparser

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.markers import Marker

#===============================================================================
class EntryPointsParser(configparser.ConfigParser):
  """

  See Also
  --------
  * https://packaging.python.org/en/latest/specifications/entry-points/
  """
  optionxform = staticmethod(str)

#===============================================================================
class PkgInfoAuthor:
  """Internal container for normalizing Author/Maintainer
  and Author-email/Maintainer-email header metadata
  """
  #-----------------------------------------------------------------------------
  def __init__( self, name = '', email = '' ):
    # Note, the normalization will combine "name" <email> into email if both are provided

    # > PEP 621
    # > If only name is provided, the value goes in Author/Maintainer as appropriate.
    # > If only email is provided, the value goes in Author-email/Maintainer-email as appropriate.
    # > If both email and name are provided, the value goes in Author-email/Maintainer-email as
    # > appropriate, with the format {name} <{email}> (with appropriate quoting, e.g. using email.headerregistry.Address).
    self.name, self.email = norm_dist_author(
      name = str(name),
      email = str(email) )

  #-----------------------------------------------------------------------------
  def __str__( self ):
    return self.name + self.email

  #-----------------------------------------------------------------------------
  def __eq__( self, other ):
    return str(self) == str(other)

  #-----------------------------------------------------------------------------
  def __hash__( self ):
    return hash(str(self))

#===============================================================================
class PkgInfoURL:
  """Internal container for normalizing Project-URL
  """
  #-----------------------------------------------------------------------------
  def __init__( self, label = '', url = '' ):
    self.label, self.url = norm_dist_url(
      label = label,
      url = url )

  #-----------------------------------------------------------------------------
  def __str__( self ):
    return f'{self.label}, {self.url}'

  #-----------------------------------------------------------------------------
  def __eq__( self, other ):
    return str(self) == str(other)

  #-----------------------------------------------------------------------------
  def __hash__( self ):
    return hash(str(self))

#===============================================================================
class PkgInfoReq:
  """Internal container for normalizing "Requires-Dist" header metadata
  """
  req: Requirement

  #-----------------------------------------------------------------------------
  def __init__( self, req, extra = '' ):

    self.req = Requirement( norm_printable(req) )

    marker = str( self.req.marker ) if self.req.marker else ''

    if extra:
      extra = norm_dist_extra(extra)

      if marker:
        self.req.marker = Marker(f'extra == "{extra}" and ( {marker} )')
      else:
        self.req.marker = Marker(f'extra == "{extra}"')

  #-----------------------------------------------------------------------------
  def __str__( self ):
    return str(self.req)

  #-----------------------------------------------------------------------------
  def __eq__( self, other ):
    return str(self) == str(other)

  #-----------------------------------------------------------------------------
  def __hash__( self ):
    return hash(str(self))

#===============================================================================
class PkgInfo:
  def __init__( self,
    project,
    root = None ):
    """Internal container for normalizing metadata as defined in PEP 621 and


    Parameters
    ----------
    project : dict
      The project meta-data as defined in 'pyproject.toml'.
      May be the parsed [project] table from a 'pyproject.toml' file located
      in the 'root' directory.
    root : None | str | pathlib.Path
      Path to the root project directory that would contain 'pyproject.toml'.
      This is used to resolve file paths defined in the project metatada.
      If there are no files referenced, then this value has no effect.

    See Also
    --------
    * https://www.python.org/dev/peps/pep-0621/
    * https://packaging.python.org/en/latest/specifications/core-metadata/
    """

    if not isinstance(project, pptoml_project):
      project = pptoml_project(project)

    root = Path(root) if root else None

    with validating(key = 'dynamic'):
      if project.dynamic:
        raise ValidationError(
          f"All dynamic metadata must be resolved before constructing core metadata: {project.dynamic}")

    self.name = project.name
    self.name_normed = norm_dist_name( self.name )
    self.version = project.version
    self.description = project.description
    self.readme = project.get('readme', None)
    self.license = project.get('license', None)
    self.requires_python = SpecifierSet( project.requires_python )
    self.keywords = set(project.keywords)
    self.classifiers = set(project.classifiers)

    self.dependencies = set([ PkgInfoReq( req = d )
      for d in project.dependencies ])

    self.optional_dependencies = {
      extra : set([
        PkgInfoReq( req = d, extra = extra )
        for d in deps ])
      for extra, deps in project.optional_dependencies.items() }

    self.urls = set([
      PkgInfoURL( label = k, url = v )
      for k,v in project.urls.items() ])

    self.authors = set([ PkgInfoAuthor(**kw)
      for kw in project.authors ])

    self.maintainers = set([ PkgInfoAuthor(**kw)
      for kw in project.maintainers ])

    # NOTE: cannot use the pptoml validated dict
    # since it does not allow combined entry points as in core meta-data
    self.entry_points = dict(project.entry_points)

    # TODO: validate/normalize entrypoints
    if project.scripts:
      self.entry_points['console_scripts'] = project.scripts

    if project.gui_scripts:
      self.entry_points['gui_scripts'] = project.gui_scripts

    #...........................................................................
    # > PEP 621
    # > If the file path ends in a case-insensitive .md suffix, then tools MUST assume
    # > the content-type is text/markdown. If the file path ends in a case-insensitive
    # > .rst, then tools MUST assume the content-type is text/x-rst.
    # > If a tool recognizes more extensions than this PEP, they MAY infer the
    # > content-type for the user without specifying this field as dynamic.
    # > For all unrecognized suffixes when a content-type is not provided, tools MUST
    # > raise an error.
    # TODO: inspect for content-type in file?

    self._long_desc = ''
    self._desc_type = 'text/plain'

    if self.readme:
      with validating(key = 'readme'):
        if 'file' in self.readme:

          if not root:
            raise ValidationError(
              f"'root' must be given to resolve a 'readme.file' path")

          readme_file = root.joinpath(self.readme.file)

          if readme_file.suffix == '.rst':
            self._desc_type = 'text/x-rst'

          elif readme_file.suffix == '.md':
            self._desc_type = 'text/markdown'

          if not readme_file.exists():
            raise ValidationError(
              f"'readme' file not found: {readme_file}")

          with open( readme_file, 'rb' ) as fp:
            self._long_desc = norm_printable(
              fp.read().decode('utf-8', errors = 'replace') )

        else:
          # NOTE: if readme is non-empty, then it must either have 'file' or 'text'
          self._long_desc = self.readme.text

    if not self._long_desc:
      self._long_desc = self.description

    #...........................................................................
    # https://www.python.org/dev/peps/pep-0621/#license
    self._license = ''
    self.license_file = ''
    self.license_file_content = None

    if self.license:
      with validating(key = 'license'):
        # NOTE: PEP 621 specifically says
        # > The text key has a string value which is the license of the project
        # > whose meaning is that of the License field from the core metadata.
        # > These keys are mutually exclusive, so a tool MUST raise an error
        # > if the metadata specifies both keys.
        # However, many tools seem to assign both a 'short' license description
        # to License, in addition to a filename to 'License-File'.
        # It's not clear how to accomidate both with the above restriction.


        # > The table may have one of two keys. The file key has a string value that is
        # > a relative file path to the file which contains the license for the project.
        # > Tools MUST assume the file's encoding is UTF-8. The text key has a string
        # > value which is the license of the project whose meaning is that of the
        # > License field from the core metadata. These keys are mutually exclusive,
        # > so a tool MUST raise an error if the metadata specifies both keys.

        if 'file' in self.license:
          if not root:
            raise ValidationError(f"'root' must be given to resolve 'license.file' path")

          # if 'text' in self.license:
          #   raise ValidationError(f"'license' cannot have both 'text' and 'file': {self.license}")

          # TODO: Core Metadata standar does not mention a 'License-File' header
          # but many tools seem to assign this value.
          # https://packaging.python.org/en/latest/specifications/core-metadata/
          # It is not clear if this is now deprecated, or if any tools actually
          # expect this to be set

          self.license_file = os.fspath(PurePosixPath(self.license.file))

          license_file = root.joinpath(self.license.file)

          if not license_file.exists():
            raise ValidationError(
              f"'license' file not found: {license_file}")

          with open( license_file, 'rb' ) as fp:
            self.license_file_content = norm_printable(
              fp.read().decode('utf-8', errors = 'replace') ).encode('utf-8')

        if 'text' in self.license:
          self._license = norm_printable( self.license.text )

  #-----------------------------------------------------------------------------
  def add_dependencies( self, deps ):
    """Used to add dependencies

    Parameters
    ----------
    deps : List[ str ]
      dependencies to add

    Returns
    -------
    pkg_info :
      Resulting package info

    """

    new_info = copy(self)

    # NOTE: '|' for sets of requirements results in 'require all'
    new_info.dependencies |= set([ PkgInfoReq( req = d )
      for d in deps ])

    return new_info

  #-----------------------------------------------------------------------------
  @property
  def requires_dist( self ):
    """Computes total list of install requirements
    """
    requires_dist = list(self.dependencies)

    for extra, reqs in self.optional_dependencies.items():
      requires_dist.extend( list(reqs) )

    return requires_dist

  #-----------------------------------------------------------------------------
  @property
  def provides_extra( self ):
    """Provided extras
    """
    return list( self.optional_dependencies.keys() )

  #-----------------------------------------------------------------------------
  def encode_entry_points( self ):
    """Generate encoded content for .dist_info/entry_points.txt

    Returns
    -------
    content : bytes
    """

    entry_points = EntryPointsParser()

    for k, v in self.entry_points.items():
      entry_points[k] = v

    fp = io.StringIO()

    entry_points.write( fp )

    return fp.getvalue().encode('utf-8')

  #-----------------------------------------------------------------------------
  def encode_pkg_info( self ):
    """Generate encoded content for PKG-INFO, or .dist_info/METADATA

    Returns
    -------
    content : bytes
    """

    #...........................................................................
    # filter non-empty normalized author fields
    _authors = [ a.name for a in self.authors if a.name ]
    _author_emails = [ a.email for a in self.authors if a.email ]

    _maintainers = [ a.name for a in self.maintainers if a.name ]
    _maintainer_emails = [ a.email for a in self.maintainers if a.email ]


    #...........................................................................
    # construct metadata header values
    headers = [
      ( 'Metadata-Version', '2.1' ),
      ( 'Name', self.name ),
      ( 'Version', self.version ) ]

    if self.requires_python:
      headers.append( ( 'Requires-Python', str(self.requires_python) ) )

    #...........................................................................
    for name in _authors:
      headers.append( ( 'Author', name ) )

    for name in _maintainers:
      headers.append( ( 'Maintainer', name ) )

    for email in _author_emails:
      headers.append( ( 'Author-email', email ) )

    for email in _maintainer_emails:
      headers.append( ( 'Maintainer-email', email ) )

    summary_folded = re.sub(
      r'\n',
      '\n        |',
      self.description.strip() )

    headers.append( ( 'Summary', summary_folded ) )

    if self._license:
      license_folded = re.sub(
        r'\n',
        '\n        |',
        self._license.strip() )

      headers.append( ( 'License', license_folded ) )

    if self.license_file:
      headers.append( ( 'License-File', self.license_file ) )

    if len(self.keywords) > 0:
      headers.append( ( 'Keywords', ', '.join(self.keywords) ) )

    for url in self.urls:
      headers.append( ( 'Project-URL', str(url) ) )

    for classifier in self.classifiers:
      headers.append( ( 'Classifier', classifier ) )

    #...........................................................................
    for e in self.provides_extra:
      headers.append(
        ( 'Provides-Extra', str(e) ) )

    for d in self.requires_dist:
      headers.append(
        ( 'Requires-Dist', str(d) ) )

    headers.append( ( 'Description-Content-Type', self._desc_type ) )

    return email_encode_items(
      headers = headers,
      payload = self._long_desc )
