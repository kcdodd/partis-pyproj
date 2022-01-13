import os
import os.path as osp
import io
import warnings
import stat
from copy import copy

import tempfile
import shutil
import configparser

from .norms import (
  allowed_keys,
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
  norm_wheel_name,
  norm_path,
  norm_data,
  mode_to_xattr,
  hash_sha256,
  email_encode_items )

import configparser

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.markers import Marker

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class EntryPointsParser(configparser.ConfigParser):
  """

  See Also
  --------
  https://packaging.python.org/en/latest/specifications/entry-points/
  """
  optionxform = staticmethod(str)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PkgInfoReq:
  """Internal container for normalizing "Requires-Dist" header metadata
  """
  #-----------------------------------------------------------------------------
  def __init__( self, req, extra = '' ):

    self.req = Requirement( norm_printable(req) )

    marker = str( self.req.marker ) if self.req.marker else ''
    extra = norm_dist_extra(extra)

    if extra:
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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
    root : None | str
      Path to the root project directory that would contain 'pyproject.toml'.
      This is used to resolve file paths defined in the project metatada.
      If there are no files referenced, then this value has no effect.

    See Also
    --------
    https://www.python.org/dev/peps/pep-0621/

    https://packaging.python.org/en/latest/specifications/core-metadata/
    """

    allowed_keys(
      name = 'project',
      obj = project,
      keys = [
        'name',
        'version',
        'description',
        'readme',
        'authors',
        'maintainers',
        'license',
        'dynamic',
        'requires-python',
        'dependencies',
        'optional-dependencies',
        'keywords',
        'classifiers',
        'urls',
        'scripts',
        'gui-scripts',
        'entry-points' ] )

    self.name = valid_dist_name( project.get('name') )
    self.name_normed = norm_dist_name( self.name )
    self.version = norm_dist_version( project.get('version') )
    self.description = project.get( 'description', None )
    self.readme = project.get( 'readme', None )
    self.license = project.get( 'license', None )
    self.dynamic = project.get( 'dynamic', list() )

    self.requires_python = SpecifierSet(
      norm_printable( project.get( 'requires-python', '' ) ) )

    self.dependencies = set([ PkgInfoReq( req = d )
      for d in project.get( 'dependencies', list() ) ])

    self.optional_dependencies = {
      norm_dist_extra(extra) : set([
        PkgInfoReq( req = d, extra = extra )
        for d in deps ])
      for extra, deps in project.get( 'optional-dependencies', dict() ).items() }

    self.keywords = set([
      norm_dist_keyword(k)
      for k in project.get( 'keywords', list() ) ])

    self.classifiers = set([ norm_dist_classifier(c)
      for c in project.get( 'classifiers', list() ) ])

    self.urls = set([
      PkgInfoURL( label = k, url = v )
      for k,v in project.get( 'urls', dict() ).items() ])

    self.authors = set([ PkgInfoAuthor(**kw)
      for kw in project.get( 'authors', list() ) ])

    self.maintainers = set([ PkgInfoAuthor(**kw)
      for kw in project.get( 'maintainers', list() ) ])

    self.entry_points = dict()

    # TODO: validate/normalize entrypoints
    if 'scripts' in project:
      self.entry_points['console_scripts'] = project.get('scripts')

    if 'gui-scripts' in project:
      self.entry_points['gui_scripts'] = project.get('gui-scripts')

    if 'entry-points' in project:
      for k, v in project.get('entry-points').items():
        # PEP 621
        # > Build back-ends MUST raise an error if the metadata defines a
        # > [project.entry-points.console_scripts] or [project.entry-points.gui_scripts]
        # > table, as they would be ambiguous in the face of [project.scripts]
        # > and [project.gui-scripts], respectively.
        if k in [ 'scripts', 'console_scripts' ]:
          raise ValueError(
            f"'console_scripts' should be defined in [project.scripts] instead of [project.entry-points]")

        if k in [ 'gui-scripts', 'gui_scripts' ]:
          raise ValueError(
            f"'gui_scripts' should be defined in [project.gui-scripts] instead of [project.entry-points]")

        self.entry_points[k] = v



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

    self._desc = ''
    self._desc_type = 'text/plain'

    readme_file = None

    if self.readme:

      if isinstance( self.readme, dict ):
        if 'file' in self.readme:
          if not root:
            raise ValueError(f"'root' must be given to resolve a 'readme.file' path")

          readme_file = os.path.join( root, self.readme['file'] )

        elif 'text' in self.readme:
          self._desc = norm_printable( self.readme['text'] )

      elif self.readme and isinstance( self.readme, str ):
        if not root:
          raise ValueError(f"'root' must be given to resolve 'readme' file path")

        readme_file = os.path.join( root, self.readme )

      if readme_file:
        if readme_file.lower().endswith('.rst'):
          self._desc_type = 'text/x-rst'

        if readme_file.lower().endswith('.md'):
          self._desc_type = 'text/markdown'

        with open( readme_file, 'r' ) as fp:
          self._desc = norm_printable( fp.read() )

    #...........................................................................
    # https://www.python.org/dev/peps/pep-0621/#license
    self._license = ''
    self.license_file = ''
    self.license_file_content = None

    if self.license:
      # NOTE: PEP 621 specifically says
      # > The text key has a string value which is the license of the project
      # > whose meaning is that of the License field from the core metadata.
      # > These keys are mutually exclusive, so a tool MUST raise an error
      # > if the metadata specifies both keys.
      # However, many tools seem to assign both a 'short' license description
      # to License, in addition to a filename to 'License-File'.
      # It's not clear how to accomidate both with the above restriction.

      if isinstance( self.license, dict ):
        # > The table may have one of two keys. The file key has a string value that is
        # > a relative file path to the file which contains the license for the project.
        # > Tools MUST assume the file's encoding is UTF-8. The text key has a string
        # > value which is the license of the project whose meaning is that of the
        # > License field from the core metadata. These keys are mutually exclusive,
        # > so a tool MUST raise an error if the metadata specifies both keys.

        if 'file' in self.license:
          if not root:
            raise ValueError(f"'root' must be given to resolve 'license.file' path")

          # if 'text' in self.license:
          #   raise ValueError(f"'license' cannot have both 'text' and 'file': {self.license}")

          # TODO: Core Metadata standar does not mention a 'License-File' header
          # but many tools seem to assign this value.
          # https://packaging.python.org/en/latest/specifications/core-metadata/
          # It is not clear if this is now deprecated, or if any tools actually
          # expect this to be set

          self.license_file = self.license['file']

          with open( osp.join( root, self.license_file ), 'r' ) as fp:
            self.license_file_content = norm_printable( fp.read() ).encode('utf-8')

        if 'text' in self.license:

          self._license = norm_printable( self.license['text'] )


      else:
        raise ValueError(f"'license' must be a mapping with either 'text' or 'file': {self.license}")


    # this is only used when 'prividing' another package in the same distro
    self._provides_dist = set()
    self._obsoletes_dist = set()

  #-----------------------------------------------------------------------------
  def provides( self, other ):
    """Used to combine multi-module package meta-data

    Parameters
    ----------
    other : PkgInfo
      Package info to include as 'provided'

    Returns
    -------
    pkg_info : PkgInfo
      Resulting package info

    Notes
    -----
    This should be used with extreme caution.
    It performs a very simple extending of information, requirements, and entry_points.

    Todo
    ----
    This does not currently handle if an 'extra' from a sub-project is requested
    by another, incidentally removing the needed dependency.
    """

    if not isinstance( other, PkgInfo ):
      raise ValueError(f"other must be instance of PkgInfo: {other}")


    provider = copy(self)

    # NOTE: requires_python is a specifier set, so '&' results in 'require both'
    provider.requires_python &= other.requires_python

    # NOTE: '|' for sets of requirements results in 'require all'
    provider.dependencies |= other.dependencies

    for extra, reqs in other.optional_dependencies.items():
      if extra in provider.optional_dependencies:
        provider.optional_dependencies[extra] |= reqs
      else:
        provider.optional_dependencies[extra] = copy(reqs)

    provider.keywords |= other.keywords
    provider.urls |= other.urls
    provider.classifiers |= other.classifiers

    provider.authors |= other.authors
    provider.maintainers |= other.maintainers


    for k, v in other.entry_points.items():
      if k in provider.entry_points:
        provider.entry_points[k].update(v)

      else:
        provider.entry_points[k] = copy(v)

    provider._provides_dist.add( other.name_normed )
    provider._obsoletes_dist.add( other.name_normed )

    return provider

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

    # filter out any dependencies listing the one being provided
    # NOTE: this dose not do any checking of version, up to repo maintainers
    requires_dist = [ d for d in requires_dist if d.req.name not in self._provides_dist ]

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

    if self.description:
      headers.append( ( 'Summary', self.description ) )

    if self._desc:
      headers.append( ( 'Description-Content-Type', self._desc_type ) )

    if self._license:
      headers.append( ( 'License', self._license ) )

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

    for d in self._provides_dist:
      headers.append(
        ( 'Provides-Dist', str(d) ) )

    for d in self._obsoletes_dist:
      headers.append(
        ( 'Obsoletes-Dist', str(d) ) )

    for d in self.requires_dist:
      headers.append(
        ( 'Requires-Dist', str(d) ) )

    return email_encode_items(
      headers = headers,
      payload = self._desc if self._desc else None )
