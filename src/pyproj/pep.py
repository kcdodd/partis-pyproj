from __future__ import annotations
import sys
import re
import inspect

from collections import namedtuple
from email.utils import parseaddr
from email.headerregistry import Address
from urllib.parse import urlparse
import keyword

from packaging.tags import sys_tags

from .validate import (
  ValidationError,
  validating)
from ._nonprintable import nonprintable

#===============================================================================
CompatibilityTags = namedtuple('CompatibilityTags', ['py_tag', 'abi_tag', 'plat_tag'])

#===============================================================================
# NOTE: patterns used for validation are defined at the end of this file

#===============================================================================
class PEPValidationError( ValidationError ):
  """Error from value incompatible with a :term:`PEP`

  Parameters
  ----------
  pep : int
    The referenced PEP number
  msg : str
    Error message
  val : object
    Value that was being validated
  """

  def __init__( self, *, pep, msg, val ):

    msg = inspect.cleandoc( msg )

    super().__init__(
      msg = f'{msg} (PEP {pep}): {val}' )

#===============================================================================
def norm_printable(
  text = None ):
  r"""Removes leading and trailing whitespace, and all control, surrogate,
  private use, noncharacter, line/paragraph separator, explicit directional
  formatting, and byte order mark characters, except for newlines '\\n' and
  tabs '\\t'.

  Parameters
  ----------
  text : None | str
    If None, an empty string is returned.

  Returns
  -------
  str

  Note
  ----
  Package meta-data is serialized as UTF-8, so non-ASCII text is retained as-is.
  What is removed are the characters that are either not encodable, have no
  defined meaning, or would break the RFC 822 header format that the core
  meta-data is based on, or that let the rendered value disagree with the source
  it was written from. This is narrower than :meth:`str.isprintable`, which also
  excludes non-space separators (Zs) and most format characters (Cf) that
  legitimate text depends on, and unassigned characters (Cn) that a later
  Unicode version may assign -- see
  :data:`partis.pyproj._nonprintable.STRIP_CATEGORIES` and
  :data:`partis.pyproj._nonprintable.STRIP_FORMAT`.

  Example
  -------

  .. code-block:: python

    import re
    from partis.pyproj import norm_printable

    x = ''.join([ chr(i) for i in range(50) ])
    print( x.isprintable() )

    y = norm_printable(x)
    print( y.isprintable() )

    z = re.sub(r'[\t\n]', '', y)
    print( z.isprintable() )

    print( norm_printable(None) )
    print( norm_printable('f\ubaaar') )

  """

  if text is None:
    return ''


  return nonprintable.sub( '', str(text).strip() )

#===============================================================================
def valid_dist_name( name ):
  """Checks for valid distribution name (:pep:`426`)

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0426/#name
  """

  name = norm_printable( name )

  if not pep426_dist_name.fullmatch( name ):
    raise PEPValidationError(
      pep = 426,
      msg = "Distribution names MUST ASCII letters, digits, _, -, ., start and end with an ASCII letter or digit",
      val = name )

  return name

#===============================================================================
def norm_dist_name( name ):
  """Normalizes a distribution name (:pep:`503`)

  Note
  ----
  The name should be lowercased with all runs of the
  characters ., -, or _ replaced with a single - character.

  See Also
  --------
  * :func:`valid_dist_name`
  * https://www.python.org/dev/peps/pep-0503/#normalized-names
  """

  name = valid_dist_name( name ).lower()

  # > The name should be lowercased with all runs of the
  # > characters ., -, or _ replaced with a single - character.
  name = pep_503_name_norm.sub('-', name)

  return name

#===============================================================================
def norm_dist_filename( name ):
  """Normalize distribution filename component (:pep:`427`)

  Note
  ----
  Each component of the filename is escaped by replacing runs of
  non-alphanumeric characters with an underscore '_'

  Addendum - It seems that "local" versions require '+'

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0427/#file-name-convention
  """

  return re.sub( r"[^\w\d\.\+]+", "_", name )

#===============================================================================
def join_dist_filename( parts ):
  """Joins distribution filename component (:pep:`427`)

  Note
  ----
  Each component of the filename is joined by '-'

  See Also
  --------
  * :func:`norm_dist_filename`
  * https://www.python.org/dev/peps/pep-0427/#file-name-convention
  """

  return '-'.join([
    norm_dist_filename(p)
    for p in parts
    if p != ''])

#===============================================================================
def norm_dist_version( version ):
  """Checks for valid distribution version (:pep:`440`)

  .. versionchanged:: 0.1.9

    Allow local version identifiers ``<public version identifier>[+<local version label>]``,
    in addition to public versions.
    Version pattern now uses :ref:`~packaging.version.VERSION_PATTERN`.

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0440/#version-scheme
  """

  version = norm_printable( version )

  if not pep440_version.fullmatch( version ):
    raise PEPValidationError(
      pep = 440,
      msg = """Public version identifiers MUST comply with the following scheme,
        [N!]N(.N)*[{a|b|rc}N][.postN][.devN]""",
      val = version )

  return version

#===============================================================================
def norm_dist_author(
  name = None,
  email = None ):
  """Checks for valid distribution author/maintainer name/email (:pep:`621`)

  * The name value MUST be a valid email name
    (i.e. whatever can be put as a name, before an email, in RFC #822)
    and not contain commas.
  * If only name is provided, the value goes in Author/Maintainer as
    appropriate.
  * If only email is provided, the value goes in Author-email/Maintainer-email
    as appropriate.
  * If both email and name are provided, the value goes in
    Author-email/Maintainer-email as appropriate,
    with the format {name} <{email}> (with appropriate quoting,
    e.g. using email.headerregistry.Address).

    .. note::

      The returned name field will be empty in this case.


  Parameters
  ----------
  name : str
  email : str

  Returns
  -------
  name : str
  email : str

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0621/#authors-maintainers
  """

  val = norm_dist_author_dict(dict(name = name, email = email))

  #.............................................................................
  # > If both email and name are provided, the value goes in
  # > Author-email/Maintainer-email as appropriate, with the
  # > format {name} <{email}>.
  if name and email:
    return '', format_dist_author( name, email )

  # > If only name is provided, the value goes in Author/Maintainer as
  # > appropriate.
  # > If only email is provided, the value goes in Author-email/Maintainer-email
  # > as appropriate.
  return name, email

#===============================================================================
def format_dist_author(name, email):
  """Formats a "{name} <{email}>" value

  Note
  ----
  :func:`email.utils.formataddr` is not used, since it re-encodes a non-ASCII
  name as an RFC 2047 encoded-word. The meta-data is serialized as UTF-8, and
  consumers do not decode encoded-words, so the name is kept as-is and only
  quoted where the RFC 822 "specials" require it.

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0621/#authors-maintainers
  """

  return str( Address( display_name = name, addr_spec = email ) )

#===============================================================================
def norm_dist_author_dict(val):

  name = norm_printable( val.get('name', '') )
  email = norm_printable( val.get('email', '') )

  _name = name or "Placeholder Name"
  _email = email or "place@holder.com"

  #.............................................................................
  with validating(key = 'name'):
    if not pep621_author_name.fullmatch(name):
      raise PEPValidationError(
        pep = 621,
        msg = "The name value MUST be a valid email name, and not contain commas",
        val = name )

  #.............................................................................
  with validating(key = 'email'):
    if not pep621_author_email.fullmatch(email):
      raise PEPValidationError(
        pep = 621,
        msg = "The email value MUST be a valid email address",
        val = email )

    # ensure that at least that the standard Python library can understand the
    # "name" <email> combination
    try:
      _name, _email = parseaddr( format_dist_author( _name, _email ) )

    except ValueError as e:
      raise PEPValidationError(
        pep = 621,
        msg = "The email value MUST be a valid email address",
        val = email ) from e

    if email and _email != email:
      raise PEPValidationError(
        pep = 621,
        msg = "The email value MUST be a valid email address",
        val = email )

  #.............................................................................
  with validating(key = 'name'):
    if name and _name != name:
      raise PEPValidationError(
        pep = 621,
        msg = "The name value MUST be a valid email name, and not contain commas",
        val = name )

  val = {
    'name': name,
    'email': email }

  return val

#===============================================================================
def norm_dist_classifier( classifier ):
  """
  See Also
  --------
  * https://www.python.org/dev/peps/pep-0301/#distutils-trove-classification
  """

  classifier = norm_printable( classifier )

  parts = [ s.strip() for s in classifier.split('::') ]

  for part in parts:
    if not pep_301_classifier.fullmatch( part ):
      raise PEPValidationError(
        pep = 301,
        msg = f"Invalid classifier component '{part}'",
        val = classifier )

  classifier = ' :: '.join( parts )

  return classifier

#===============================================================================
def norm_dist_keyword( keyword ):
  """
  See Also
  --------
  * https://www.python.org/dev/peps/pep-0621/#keywords
  """

  keyword = norm_printable( keyword )

  if not pep_621_keyword.fullmatch( keyword ):
    raise PEPValidationError(
      pep = 621,
      msg = "Invalid keyword",
      val = keyword )

  return keyword

#===============================================================================
def norm_dist_url( label, url ):
  """
  See Also
  --------
  * https://packaging.python.org/en/latest/specifications/core-metadata/#project-url-multiple-use
  """

  # > The label is free text limited to 32 characters.
  label = norm_printable( label )[:32]
  url = norm_printable( url )

  if not pep621_author_name.fullmatch(label):
    raise PEPValidationError(
      pep = 621,
      msg = "Invalid url label",
      val = label )

  try:
    res = urlparse( url )

    if not ( res.scheme and res.netloc ):
      raise PEPValidationError(
        pep = 621,
        msg = "URL must have a valid scheme and net location",
        val = url )

  except Exception as e:
    raise PEPValidationError(
      pep = 621,
      msg = "Invalid url",
      val = url ) from e

  return label, url

#===============================================================================
def norm_dist_extra( extra ):
  """Normalize distribution 'extra' requirement

  .. versionchanged:: 0.2.0

    Extra names are normalized according to PEP-685 and validated according to
    Core Metadata 2.3.
    Previously, extra names "must be a valid Python identifier" (Core Metadata 2.1)


  Note
  ----
  * MUST write out extra names in their normalized form.
  * This applies to the Provides-Extra field and the extra marker when used
    in the Requires-Dist field.

  See Also
  --------
  * https://peps.python.org/pep-0685/#specification
  """

  extra = norm_printable(extra).lower()
  extra = pep_503_name_norm.sub('-', extra)

  if not pep_685_extra.fullmatch(extra):
    raise PEPValidationError(
      pep = 685,
      msg = "Invalid extra",
      val = extra )

  return extra

#===============================================================================
def dist_build( build_number = None, build_tag = None ):
  if build_number is None and build_tag is None:
    build = ''

  elif build_tag is None:
    build = str(int(build_number))

  elif build_number is None:
    build = f"0_{build_tag}"

  else:
    build = f"{int(build_number)}_{build_tag}"

  return norm_dist_build(build)

#===============================================================================
def norm_dist_build( build ):
  """
  Note
  ----
  * Must start with a digit, remainder is ASCII alpha-numeric

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0427/#file-name-convention
  """

  build = norm_printable( build ).lower()

  if not pep427_build.fullmatch( build ):
    raise PEPValidationError(
      pep = 427,
      msg = """Must start with a digit. Acts as a tie-breaker if two wheel file
        names are the same in all other respects""",
      val = build )

  return build

#===============================================================================
def norm_dist_compat( py_tag, abi_tag, plat_tag ):
  """

  Note
  ----
  * Tags must contain only ASCII alpha-numeric or underscore
  * platform tag with all hyphens -
    and periods . replaced with underscore _.

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0425/#details
  """

  py_tag = norm_printable( py_tag ).lower()
  abi_tag = norm_printable( abi_tag ).lower()

  # > platform tag is simply distutils.util.get_platform() with all hyphens -
  # > and periods . replaced with underscore _.
  plat_tag = re.sub( r'[\-\_\.]+', "_", norm_printable(plat_tag).lower() )

  if not pep425_pytag.fullmatch( py_tag ):
    raise PEPValidationError(
      pep = 425,
      msg = """The version is py_version_nodot. CPython gets away with no dot,
        but if one is needed the underscore _ is used instead""",
      val = py_tag )


  if not pep425_pytag.fullmatch( abi_tag ):
    # use the same validation for abi tag
    raise PEPValidationError(
      pep = 425,
      msg = """The version is py_version_nodot. CPython gets away with no dot,
        but if one is needed the underscore _ is used instead""",
      val = abi_tag )

  if not pep425_pytag.fullmatch( plat_tag ):
    # use the same validation for platform tag
    raise PEPValidationError(
      pep = 425,
      msg = """Platform tag is simply distutils.util.get_platform() with all
        hyphens - and periods . replaced with underscore _""",
      val = plat_tag )

  # if not common_pytag.fullmatch( py_tag ):
  #   warnings.warn(f"python tag was not recognized: {py_tag}")
  #
  # if not common_abitag.fullmatch( abi_tag ):
  #   warnings.warn(f"abi tag was not recognized: {abi_tag}")
  #
  # if not any( plat.fullmatch( plat_tag ) for plat in common_plattag.values() ):
  #   warnings.warn(f"platform tag was not recognized: {plat_tag}")

  return CompatibilityTags( py_tag, abi_tag, plat_tag )

#===============================================================================
def join_dist_compat( tags ):
  """
  See Also
  --------
  * https://www.python.org/dev/peps/pep-0425/#compressed-tag-sets
  """
  return '.'.join( sorted(list(set(tags))) )

#===============================================================================
def compress_dist_compat( compat ):
  """
  See Also
  --------
  * https://www.python.org/dev/peps/pep-0425/#compressed-tag-sets
  """

  py_tags, abi_tags, plat_tags = zip( *compat )

  py_tags = join_dist_compat( py_tags )
  abi_tags = join_dist_compat( abi_tags )
  plat_tags = join_dist_compat( plat_tags )

  return py_tags, abi_tags, plat_tags

#===============================================================================
def purelib_compat_tags():
  """Return general compatability tags for the current system
  """

  compat = [ CompatibilityTags( 'py3', 'none', 'any' ) ]

  return compat

#===============================================================================
def platlib_compat_tags():
  """Get platform compatability tags for the current system
  """
  tag = next(iter(sys_tags()))

  # interpreter = "py{0}{1}".format(sys.version_info.major, sys.version_info.minor)
  interpreter = tag.interpreter

  compat_tags = [ CompatibilityTags( interpreter, tag.abi, tag.platform ) ]

  return compat_tags

#===============================================================================
def norm_py_identifier( name ):

  name = norm_printable( name )

  if not py_identifier.fullmatch( name ):
    raise ValidationError(
      msg = f"""Python identifier may only contain letters in a small case (a-z),
        upper case (A-Z), digits (0-9), and underscore (_), and not start with
        a digit: {name}""" )

  if py_keyword.fullmatch( name ):
    raise ValidationError(
      msg = f"Python identifier may not be a reserved keyword: {name}" )

  return name

#===============================================================================
def norm_entry_point_group( name ):
  """Normalizes entry point group

  See Also
  --------
  * https://packaging.python.org/en/latest/specifications/entry-points/
  """

  name = norm_printable( name )

  if not entry_point_group.fullmatch( name ):
    raise ValidationError(
      msg = f"""Entry point group must be one or more groups of
        letters, numbers and underscores, separated by dots: {name}""" )

  return name

#===============================================================================
def norm_entry_point_name( name ):
  """Normalizes entry point name

  See Also
  --------
  * https://packaging.python.org/en/latest/specifications/entry-points/
  * The name may contain any characters except =, but it cannot start or end with
    any whitespace character, or start with [
  """

  name = norm_printable( name )

  if not entry_point_name.fullmatch( name ):
    raise ValidationError(
      msg = f"""Entry point name must be only letters, numbers, underscores,
        dots and dashes: {name}""" )

  return name

#===============================================================================
def norm_entry_point_ref( ref ):
  """Normalizes entry point object reference

  See Also
  --------
  * https://packaging.python.org/en/latest/specifications/entry-points/
  """

  ref = norm_printable( ref )

  modname, sep, qualname = ref.partition(':')

  if not modname:
    raise ValidationError(
      msg = f"Entry point reference must give a module name: {ref}" )

  try:

    modname = '.'.join( norm_py_identifier(name) for name in modname.split('.') )

    if qualname:
      qualname = '.'.join( norm_py_identifier(name) for name in qualname.split('.') )

      return f'{modname}:{qualname}'

    return modname

  except ValidationError as e:
    raise ValidationError(
      msg = f"""Entry point reference must have the form 'importable.module'
        or 'importable.module:object.attr': {ref}""") from e

#===============================================================================
# https://packaging.python.org/en/latest/specifications/name-normalization/#name-format
pep426_dist_name = re.compile(
  r'^([A-Z0-9]|[A-Z0-9][A-Z0-9._\-]*[A-Z0-9])$',
  re.IGNORECASE )

# https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
# > runs of characters ., -, or _ replaced with a single - character.
pep_503_name_norm = re.compile(r'[\-\_\.]+', re.IGNORECASE)

# value of packaging.version.VERSION_PATTERN, as of 'packaging == 25.0'
# just in case the variable is ever deprecated
VERSION_PATTERN = r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>alpha|a|beta|b|preview|pre|c|rc)
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""

pep440_version = re.compile(VERSION_PATTERN, re.VERBOSE | re.IGNORECASE)

# NOTE: PEP 427 does not specify any constraints on the string following the
# digits, but given the form it is used in the filenames it really cannot
# contain anything other than alpha-numeric characters.
pep427_build = re.compile(
  r'^([0-9]+[A-Z0-9_]*)?$',
  re.IGNORECASE )

pep425_pytag = re.compile(
  r'^([A-Z0-9_]+)$',
  re.IGNORECASE )

#===============================================================================
# https://www.python.org/dev/peps/pep-0621/#authors-maintainers
# https://www.rfc-editor.org/rfc/inline-errata/rfc5322.html
# > name value MUST be a valid email name (i.e. whatever can be put as a name,
# > before an email, in RFC #822) and not contain commas

# NOTE: email names are notoriously hard to validate correctly,
# this is probably not correct.
# strategy here is to do minimal sanity check by ensuring the absense of
# likely invalid characters.
# The strings should also be checked if they are 'printable'.

# ensures the name does not include double-quotes, backslashes, or linefeeds
# or tabs.
# the '@' here is also included here
pep621_author_name = re.compile( r'^([^\"\\\,\@\r\n\t\f\v]+)?$', re.UNICODE )

# ensures that there is a single `@` separating two non-empty segments,
# and each segment does not contain white-space or another `@`
pep621_author_email = re.compile( r'^([^\@\s]+@[^\@\s]+)?$', re.UNICODE )

local_plat = re.sub(r'[\-\.]', '_', sys.platform )

common_pytag = re.compile( r'^(py|cp|ip|pp|jy)(\w+)$', re.IGNORECASE )
common_abitag = re.compile( r'^(none|cp|abi)(\w*)$', re.IGNORECASE )
common_plattag = {
  'any' : re.compile( r'^(any)$', re.IGNORECASE ),
  'win' : re.compile( r'^(win(32|64))$', re.IGNORECASE ),
  'mac' : re.compile( r'^((macos(x)?|darwin)(_\w+)?)$', re.IGNORECASE ),
  # https://www.python.org/dev/peps/pep-0600/
  # manylinux_${GLIBCMAJOR}_${GLIBCMINOR}_${ARCH}
  'linux' : re.compile(
    r'^((many)?linux(_(\d\d?)_(\d\d?))?'
    r'_(i386|x86_64|i686|aarch64|armv7l|ppc64|ppc64le|s390x))$',
    re.IGNORECASE ),
  'local' : re.compile( rf'^({local_plat})$', re.IGNORECASE )}

#===============================================================================
# https://www.python.org/dev/peps/pep-0301/#distutils-trove-classification
# > It was decided that strings would be used for the classification entries
# > due to the deep nesting that would be involved in a more formal Python
# > structure.
# > ... classification namespaces be separated by ...  double-colon solution
# > (" :: ")
# NOTE: the PEP does not specify a valid form for classifiers, other than
# "The list of classifiers will be available through the web".
# This allows any package or version text, brackets, parentheses, spaces,
# and forward slash.
# TODO: write test against current list of classifiers
pep_301_classifier = re.compile(
  r'^[A-Z0-9._\-\/\[\]\(\) ]+$',
  re.IGNORECASE )

#===============================================================================
# https://packaging.python.org/en/latest/specifications/core-metadata/#keywords
# https://www.python.org/dev/peps/pep-0621/#keywords
# NOTE: does not say what is a valid keyword, but does say they are comma separted,
# and other implemented with space separated. To be safe ensure no white-space or commas
pep_621_keyword = re.compile( r'^[^\s\,]+$' )

#===============================================================================
# https://packaging.python.org/en/latest/specifications/core-metadata/#core-metadata-provides-extra
pep_685_extra = re.compile( r'^[a-z0-9]+(-[a-z0-9]+)*$', re.IGNORECASE)


#===============================================================================
# https://packaging.python.org/en/latest/specifications/entry-points/
# Group names must be one or more groups of letters, numbers and underscores,
# separated by dots
entry_point_group = re.compile( r'^[A-Z0-9_]+(\.[A-Z0-9_]+)*$', re.IGNORECASE  )

# The name may contain any characters except =, but it cannot start or end with
# any whitespace character, or start with [
# For new entry points (names), it is recommended to use only letters, numbers,
# underscores, dots and dashes
# entry_point_name = re.compile(r'^([A-Z0-9_\.\-]+)?$', re.IGNORECASE)
entry_point_name = re.compile(r'^([^\[\]\=\s]+)?$', re.IGNORECASE)

#===============================================================================
py_keyword = re.compile( '^(' + '|'.join(keyword.kwlist) + ')$' )
py_identifier = re.compile( r'^[A-Z_][A-Z0-9_]*$', re.IGNORECASE )
