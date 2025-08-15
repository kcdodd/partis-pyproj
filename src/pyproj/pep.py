from __future__ import annotations
import sys
import re
import inspect

from collections import namedtuple
from email.utils import parseaddr, formataddr
from urllib.parse import urlparse
import keyword

from packaging.tags import sys_tags

from .validate import (
  ValidationError,
  validating)

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
  r"""Removes leading and trailing whitespace and all non-printable characters,
  except for newlines '\\n' and tabs '\\t'.

  Parameters
  ----------
  text : None | str
    If None, an empty string is returned.

  Returns
  -------
  str

  Note
  ----
  While not explicitly stated in any PEP, it is implied through referenced RFCs
  and other assumptions that text in package meta-data should only contain
  printable unicode characters.

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
    return '', formataddr( (name, email) )

  # > If only name is provided, the value goes in Author/Maintainer as
  # > appropriate.
  # > If only email is provided, the value goes in Author-email/Maintainer-email
  # > as appropriate.
  return name, email

#===============================================================================
def norm_dist_author_dict(val):

  name = norm_printable( val.get('name', '') )
  email = norm_printable( val.get('email', '') )

  _name = name or "Placeholder Name"
  _email = email or "place@holder.com"

  # ensure that at least that the standard Python library can understand the
  # "name" <email> combination
  _name, _email = parseaddr( formataddr( (_name, _email) ) )

  #.............................................................................
  with validating(key = 'name'):
    if name and _name != name:
      raise PEPValidationError(
        pep = 621,
        msg = "The name value MUST be a valid email name, and not contain commas",
        val = name )

    if not pep621_author_name.fullmatch(name):
      raise PEPValidationError(
        pep = 621,
        msg = "The name value MUST be a valid email name, and not contain commas",
        val = name )

  #.............................................................................
  with validating(key = 'email'):
    if email and _email != email:
      raise PEPValidationError(
        pep = 621,
        msg = "The email value MUST be a valid email address",
        val = email )

    if not pep621_author_email.fullmatch(email):
      raise PEPValidationError(
        pep = 621,
        msg = "The email value MUST be a valid email address",
        val = email )

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

#===============================================================================
# NOTE: there may be a more efficient way to strip all non-printable characters
# Here consider new-lines '\n' and tabs '\t' to be printable
# even though '\n'.isprintable() returns False
# see _nonprintable.py for how this was generated
nonprintable = (
  r'[\x00-\x08\x0B-\x1F\x7F-\xA0\xAD\u0378-\u0379\u0380-\u0383\u038B\u038D'
  r'\u03A2\u0530\u0557-\u0558\u058B-\u058C\u0590\u05C8-\u05CF\u05EB-\u05EE'
  r'\u05F5-\u0605\u061C-\u061D\u06DD\u070E-\u070F\u074B-\u074C\u07B2-\u07BF'
  r'\u07FB-\u07FC\u082E-\u082F\u083F\u085C-\u085D\u085F\u086B-\u089F\u08B5'
  r'\u08C8-\u08D2\u08E2\u0984\u098D-\u098E\u0991-\u0992\u09A9\u09B1'
  r'\u09B3-\u09B5\u09BA-\u09BB\u09C5-\u09C6\u09C9-\u09CA\u09CF-\u09D6'
  r'\u09D8-\u09DB\u09DE\u09E4-\u09E5\u09FF-\u0A00\u0A04\u0A0B-\u0A0E'
  r'\u0A11-\u0A12\u0A29\u0A31\u0A34\u0A37\u0A3A-\u0A3B\u0A3D\u0A43-\u0A46'
  r'\u0A49-\u0A4A\u0A4E-\u0A50\u0A52-\u0A58\u0A5D\u0A5F-\u0A65\u0A77-\u0A80'
  r'\u0A84\u0A8E\u0A92\u0AA9\u0AB1\u0AB4\u0ABA-\u0ABB\u0AC6\u0ACA\u0ACE-\u0ACF'
  r'\u0AD1-\u0ADF\u0AE4-\u0AE5\u0AF2-\u0AF8\u0B00\u0B04\u0B0D-\u0B0E'
  r'\u0B11-\u0B12\u0B29\u0B31\u0B34\u0B3A-\u0B3B\u0B45-\u0B46\u0B49-\u0B4A'
  r'\u0B4E-\u0B54\u0B58-\u0B5B\u0B5E\u0B64-\u0B65\u0B78-\u0B81\u0B84'
  r'\u0B8B-\u0B8D\u0B91\u0B96-\u0B98\u0B9B\u0B9D\u0BA0-\u0BA2\u0BA5-\u0BA7'
  r'\u0BAB-\u0BAD\u0BBA-\u0BBD\u0BC3-\u0BC5\u0BC9\u0BCE-\u0BCF\u0BD1-\u0BD6'
  r'\u0BD8-\u0BE5\u0BFB-\u0BFF\u0C0D\u0C11\u0C29\u0C3A-\u0C3C\u0C45\u0C49'
  r'\u0C4E-\u0C54\u0C57\u0C5B-\u0C5F\u0C64-\u0C65\u0C70-\u0C76\u0C8D\u0C91'
  r'\u0CA9\u0CB4\u0CBA-\u0CBB\u0CC5\u0CC9\u0CCE-\u0CD4\u0CD7-\u0CDD\u0CDF'
  r'\u0CE4-\u0CE5\u0CF0\u0CF3-\u0CFF\u0D0D\u0D11\u0D45\u0D49\u0D50-\u0D53'
  r'\u0D64-\u0D65\u0D80\u0D84\u0D97-\u0D99\u0DB2\u0DBC\u0DBE-\u0DBF'
  r'\u0DC7-\u0DC9\u0DCB-\u0DCE\u0DD5\u0DD7\u0DE0-\u0DE5\u0DF0-\u0DF1'
  r'\u0DF5-\u0E00\u0E3B-\u0E3E\u0E5C-\u0E80\u0E83\u0E85\u0E8B\u0EA4\u0EA6'
  r'\u0EBE-\u0EBF\u0EC5\u0EC7\u0ECE-\u0ECF\u0EDA-\u0EDB\u0EE0-\u0EFF\u0F48'
  r'\u0F6D-\u0F70\u0F98\u0FBD\u0FCD\u0FDB-\u0FFF\u10C6\u10C8-\u10CC'
  r'\u10CE-\u10CF\u1249\u124E-\u124F\u1257\u1259\u125E-\u125F\u1289'
  r'\u128E-\u128F\u12B1\u12B6-\u12B7\u12BF\u12C1\u12C6-\u12C7\u12D7\u1311'
  r'\u1316-\u1317\u135B-\u135C\u137D-\u137F\u139A-\u139F\u13F6-\u13F7'
  r'\u13FE-\u13FF\u1680\u169D-\u169F\u16F9-\u16FF\u170D\u1715-\u171F'
  r'\u1737-\u173F\u1754-\u175F\u176D\u1771\u1774-\u177F\u17DE-\u17DF'
  r'\u17EA-\u17EF\u17FA-\u17FF\u180E-\u180F\u181A-\u181F\u1879-\u187F'
  r'\u18AB-\u18AF\u18F6-\u18FF\u191F\u192C-\u192F\u193C-\u193F\u1941-\u1943'
  r'\u196E-\u196F\u1975-\u197F\u19AC-\u19AF\u19CA-\u19CF\u19DB-\u19DD'
  r'\u1A1C-\u1A1D\u1A5F\u1A7D-\u1A7E\u1A8A-\u1A8F\u1A9A-\u1A9F\u1AAE-\u1AAF'
  r'\u1AC1-\u1AFF\u1B4C-\u1B4F\u1B7D-\u1B7F\u1BF4-\u1BFB\u1C38-\u1C3A'
  r'\u1C4A-\u1C4C\u1C89-\u1C8F\u1CBB-\u1CBC\u1CC8-\u1CCF\u1CFB-\u1CFF\u1DFA'
  r'\u1F16-\u1F17\u1F1E-\u1F1F\u1F46-\u1F47\u1F4E-\u1F4F\u1F58\u1F5A\u1F5C'
  r'\u1F5E\u1F7E-\u1F7F\u1FB5\u1FC5\u1FD4-\u1FD5\u1FDC\u1FF0-\u1FF1\u1FF5'
  r'\u1FFF-\u200F\u2028-\u202F\u205F-\u206F\u2072-\u2073\u208F\u209D-\u209F'
  r'\u20C0-\u20CF\u20F1-\u20FF\u218C-\u218F\u2427-\u243F\u244B-\u245F'
  r'\u2B74-\u2B75\u2B96\u2C2F\u2C5F\u2CF4-\u2CF8\u2D26\u2D28-\u2D2C'
  r'\u2D2E-\u2D2F\u2D68-\u2D6E\u2D71-\u2D7E\u2D97-\u2D9F\u2DA7\u2DAF\u2DB7'
  r'\u2DBF\u2DC7\u2DCF\u2DD7\u2DDF\u2E53-\u2E7F\u2E9A\u2EF4-\u2EFF\u2FD6-\u2FEF'
  r'\u2FFC-\u3000\u3040\u3097-\u3098\u3100-\u3104\u3130\u318F\u31E4-\u31EF'
  r'\u321F\u9FFD-\u9FFF\uA48D-\uA48F\uA4C7-\uA4CF\uA62C-\uA63F\uA6F8-\uA6FF'
  r'\uA7C0-\uA7C1\uA7CB-\uA7F4\uA82D-\uA82F\uA83A-\uA83F\uA878-\uA87F'
  r'\uA8C6-\uA8CD\uA8DA-\uA8DF\uA954-\uA95E\uA97D-\uA97F\uA9CE\uA9DA-\uA9DD'
  r'\uA9FF\uAA37-\uAA3F\uAA4E-\uAA4F\uAA5A-\uAA5B\uAAC3-\uAADA\uAAF7-\uAB00'
  r'\uAB07-\uAB08\uAB0F-\uAB10\uAB17-\uAB1F\uAB27\uAB2F\uAB6C-\uAB6F'
  r'\uABEE-\uABEF\uABFA-\uABFF\uD7A4-\uD7AF\uD7C7-\uD7CA\uD7FC-\uF8FF'
  r'\uFA6E-\uFA6F\uFADA-\uFAFF\uFB07-\uFB12\uFB18-\uFB1C\uFB37\uFB3D\uFB3F'
  r'\uFB42\uFB45\uFBC2-\uFBD2\uFD40-\uFD4F\uFD90-\uFD91\uFDC8-\uFDEF'
  r'\uFDFE-\uFDFF\uFE1A-\uFE1F\uFE53\uFE67\uFE6C-\uFE6F\uFE75\uFEFD-\uFF00'
  r'\uFFBF-\uFFC1\uFFC8-\uFFC9\uFFD0-\uFFD1\uFFD8-\uFFD9\uFFDD-\uFFDF\uFFE7'
  r'\uFFEF-\uFFFB\uFFFE-\uFFFF\U0001000C\U00010027\U0001003B\U0001003E'
  r'\U0001004E-\U0001004F\U0001005E-\U0001007F\U000100FB-\U000100FF'
  r'\U00010103-\U00010106\U00010134-\U00010136\U0001018F\U0001019D-\U0001019F'
  r'\U000101A1-\U000101CF\U000101FE-\U0001027F\U0001029D-\U0001029F'
  r'\U000102D1-\U000102DF\U000102FC-\U000102FF\U00010324-\U0001032C'
  r'\U0001034B-\U0001034F\U0001037B-\U0001037F\U0001039E\U000103C4-\U000103C7'
  r'\U000103D6-\U000103FF\U0001049E-\U0001049F\U000104AA-\U000104AF'
  r'\U000104D4-\U000104D7\U000104FC-\U000104FF\U00010528-\U0001052F'
  r'\U00010564-\U0001056E\U00010570-\U000105FF\U00010737-\U0001073F'
  r'\U00010756-\U0001075F\U00010768-\U000107FF\U00010806-\U00010807\U00010809'
  r'\U00010836\U00010839-\U0001083B\U0001083D-\U0001083E\U00010856'
  r'\U0001089F-\U000108A6\U000108B0-\U000108DF\U000108F3\U000108F6-\U000108FA'
  r'\U0001091C-\U0001091E\U0001093A-\U0001093E\U00010940-\U0001097F'
  r'\U000109B8-\U000109BB\U000109D0-\U000109D1\U00010A04\U00010A07-\U00010A0B'
  r'\U00010A14\U00010A18\U00010A36-\U00010A37\U00010A3B-\U00010A3E'
  r'\U00010A49-\U00010A4F\U00010A59-\U00010A5F\U00010AA0-\U00010ABF'
  r'\U00010AE7-\U00010AEA\U00010AF7-\U00010AFF\U00010B36-\U00010B38'
  r'\U00010B56-\U00010B57\U00010B73-\U00010B77\U00010B92-\U00010B98'
  r'\U00010B9D-\U00010BA8\U00010BB0-\U00010BFF\U00010C49-\U00010C7F'
  r'\U00010CB3-\U00010CBF\U00010CF3-\U00010CF9\U00010D28-\U00010D2F'
  r'\U00010D3A-\U00010E5F\U00010E7F\U00010EAA\U00010EAE-\U00010EAF'
  r'\U00010EB2-\U00010EFF\U00010F28-\U00010F2F\U00010F5A-\U00010FAF'
  r'\U00010FCC-\U00010FDF\U00010FF7-\U00010FFF\U0001104E-\U00011051'
  r'\U00011070-\U0001107E\U000110BD\U000110C2-\U000110CF\U000110E9-\U000110EF'
  r'\U000110FA-\U000110FF\U00011135\U00011148-\U0001114F\U00011177-\U0001117F'
  r'\U000111E0\U000111F5-\U000111FF\U00011212\U0001123F-\U0001127F\U00011287'
  r'\U00011289\U0001128E\U0001129E\U000112AA-\U000112AF\U000112EB-\U000112EF'
  r'\U000112FA-\U000112FF\U00011304\U0001130D-\U0001130E\U00011311-\U00011312'
  r'\U00011329\U00011331\U00011334\U0001133A\U00011345-\U00011346'
  r'\U00011349-\U0001134A\U0001134E-\U0001134F\U00011351-\U00011356'
  r'\U00011358-\U0001135C\U00011364-\U00011365\U0001136D-\U0001136F'
  r'\U00011375-\U000113FF\U0001145C\U00011462-\U0001147F\U000114C8-\U000114CF'
  r'\U000114DA-\U0001157F\U000115B6-\U000115B7\U000115DE-\U000115FF'
  r'\U00011645-\U0001164F\U0001165A-\U0001165F\U0001166D-\U0001167F'
  r'\U000116B9-\U000116BF\U000116CA-\U000116FF\U0001171B-\U0001171C'
  r'\U0001172C-\U0001172F\U00011740-\U000117FF\U0001183C-\U0001189F'
  r'\U000118F3-\U000118FE\U00011907-\U00011908\U0001190A-\U0001190B\U00011914'
  r'\U00011917\U00011936\U00011939-\U0001193A\U00011947-\U0001194F'
  r'\U0001195A-\U0001199F\U000119A8-\U000119A9\U000119D8-\U000119D9'
  r'\U000119E5-\U000119FF\U00011A48-\U00011A4F\U00011AA3-\U00011ABF'
  r'\U00011AF9-\U00011BFF\U00011C09\U00011C37\U00011C46-\U00011C4F'
  r'\U00011C6D-\U00011C6F\U00011C90-\U00011C91\U00011CA8\U00011CB7-\U00011CFF'
  r'\U00011D07\U00011D0A\U00011D37-\U00011D39\U00011D3B\U00011D3E'
  r'\U00011D48-\U00011D4F\U00011D5A-\U00011D5F\U00011D66\U00011D69\U00011D8F'
  r'\U00011D92\U00011D99-\U00011D9F\U00011DAA-\U00011EDF\U00011EF9-\U00011FAF'
  r'\U00011FB1-\U00011FBF\U00011FF2-\U00011FFE\U0001239A-\U000123FF\U0001246F'
  r'\U00012475-\U0001247F\U00012544-\U00012FFF\U0001342F-\U000143FF'
  r'\U00014647-\U000167FF\U00016A39-\U00016A3F\U00016A5F\U00016A6A-\U00016A6D'
  r'\U00016A70-\U00016ACF\U00016AEE-\U00016AEF\U00016AF6-\U00016AFF'
  r'\U00016B46-\U00016B4F\U00016B5A\U00016B62\U00016B78-\U00016B7C'
  r'\U00016B90-\U00016E3F\U00016E9B-\U00016EFF\U00016F4B-\U00016F4E'
  r'\U00016F88-\U00016F8E\U00016FA0-\U00016FDF\U00016FE5-\U00016FEF'
  r'\U00016FF2-\U00016FFF\U000187F8-\U000187FF\U00018CD6-\U00018CFF'
  r'\U00018D09-\U0001AFFF\U0001B11F-\U0001B14F\U0001B153-\U0001B163'
  r'\U0001B168-\U0001B16F\U0001B2FC-\U0001BBFF\U0001BC6B-\U0001BC6F'
  r'\U0001BC7D-\U0001BC7F\U0001BC89-\U0001BC8F\U0001BC9A-\U0001BC9B'
  r'\U0001BCA0-\U0001CFFF\U0001D0F6-\U0001D0FF\U0001D127-\U0001D128'
  r'\U0001D173-\U0001D17A\U0001D1E9-\U0001D1FF\U0001D246-\U0001D2DF'
  r'\U0001D2F4-\U0001D2FF\U0001D357-\U0001D35F\U0001D379-\U0001D3FF\U0001D455'
  r'\U0001D49D\U0001D4A0-\U0001D4A1\U0001D4A3-\U0001D4A4\U0001D4A7-\U0001D4A8'
  r'\U0001D4AD\U0001D4BA\U0001D4BC\U0001D4C4\U0001D506\U0001D50B-\U0001D50C'
  r'\U0001D515\U0001D51D\U0001D53A\U0001D53F\U0001D545\U0001D547-\U0001D549'
  r'\U0001D551\U0001D6A6-\U0001D6A7\U0001D7CC-\U0001D7CD\U0001DA8C-\U0001DA9A'
  r'\U0001DAA0\U0001DAB0-\U0001DFFF\U0001E007\U0001E019-\U0001E01A\U0001E022'
  r'\U0001E025\U0001E02B-\U0001E0FF\U0001E12D-\U0001E12F\U0001E13E-\U0001E13F'
  r'\U0001E14A-\U0001E14D\U0001E150-\U0001E2BF\U0001E2FA-\U0001E2FE'
  r'\U0001E300-\U0001E7FF\U0001E8C5-\U0001E8C6\U0001E8D7-\U0001E8FF'
  r'\U0001E94C-\U0001E94F\U0001E95A-\U0001E95D\U0001E960-\U0001EC70'
  r'\U0001ECB5-\U0001ED00\U0001ED3E-\U0001EDFF\U0001EE04\U0001EE20\U0001EE23'
  r'\U0001EE25-\U0001EE26\U0001EE28\U0001EE33\U0001EE38\U0001EE3A'
  r'\U0001EE3C-\U0001EE41\U0001EE43-\U0001EE46\U0001EE48\U0001EE4A\U0001EE4C'
  r'\U0001EE50\U0001EE53\U0001EE55-\U0001EE56\U0001EE58\U0001EE5A\U0001EE5C'
  r'\U0001EE5E\U0001EE60\U0001EE63\U0001EE65-\U0001EE66\U0001EE6B\U0001EE73'
  r'\U0001EE78\U0001EE7D\U0001EE7F\U0001EE8A\U0001EE9C-\U0001EEA0\U0001EEA4'
  r'\U0001EEAA\U0001EEBC-\U0001EEEF\U0001EEF2-\U0001EFFF\U0001F02C-\U0001F02F'
  r'\U0001F094-\U0001F09F\U0001F0AF-\U0001F0B0\U0001F0C0\U0001F0D0'
  r'\U0001F0F6-\U0001F0FF\U0001F1AE-\U0001F1E5\U0001F203-\U0001F20F'
  r'\U0001F23C-\U0001F23F\U0001F249-\U0001F24F\U0001F252-\U0001F25F'
  r'\U0001F266-\U0001F2FF\U0001F6D8-\U0001F6DF\U0001F6ED-\U0001F6EF'
  r'\U0001F6FD-\U0001F6FF\U0001F774-\U0001F77F\U0001F7D9-\U0001F7DF'
  r'\U0001F7EC-\U0001F7FF\U0001F80C-\U0001F80F\U0001F848-\U0001F84F'
  r'\U0001F85A-\U0001F85F\U0001F888-\U0001F88F\U0001F8AE-\U0001F8AF'
  r'\U0001F8B2-\U0001F8FF\U0001F979\U0001F9CC\U0001FA54-\U0001FA5F'
  r'\U0001FA6E-\U0001FA6F\U0001FA75-\U0001FA77\U0001FA7B-\U0001FA7F'
  r'\U0001FA87-\U0001FA8F\U0001FAA9-\U0001FAAF\U0001FAB7-\U0001FABF'
  r'\U0001FAC3-\U0001FACF\U0001FAD7-\U0001FAFF\U0001FB93\U0001FBCB-\U0001FBEF'
  r'\U0001FBFA-\U0001FFFF\U0002A6DE-\U0002A6FF\U0002B735-\U0002B73F'
  r'\U0002B81E-\U0002B81F\U0002CEA2-\U0002CEAF\U0002EBE1-\U0002F7FF'
  r'\U0002FA1E-\U0002FFFF\U0003134B-\U000E00FF\U000E01F0-\U0010FFFF]' )

nonprintable = re.compile( nonprintable, re.UNICODE )
