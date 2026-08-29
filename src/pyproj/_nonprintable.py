from __future__ import annotations
import re
import unicodedata

#===============================================================================
# Characters kept even though the rules below would otherwise strip them.
KEEP = '\t\n'

#===============================================================================
# Unicode general categories that are stripped from package meta-data.
# NOTE: this is narrower than ``str.isprintable()``, which also excludes the
# format characters (Cf) and the non-space separators (Zs). Those are needed by
# legitimate text: e.g. U+200D ZERO WIDTH JOINER in emoji sequences, U+200C
# ZERO WIDTH NON-JOINER in Persian and Indic scripts, and U+00A0 NO-BREAK SPACE.
# A few individual Cf characters are stripped even so, see :data:`STRIP_FORMAT`.
# The categories kept here are the ones that are either un-encodable, un-typeable,
# or hazardous in an RFC 822 header:
# * Cc control characters (which are also header injection vectors)
# * Cs surrogates (not encodable as UTF-8)
# * Co private use (no meaning outside a private agreement on the font; the
#   core meta-data specification does not establish one, so glyphs that render
#   under e.g. Nerd Fonts are not interchangeable and are not kept)
# * Zl, Zp line and paragraph separators (line boundaries for ``str.splitlines``)
#
# NOTE: Cn (unassigned) is deliberately *not* stripped. Which code points are
# unassigned is a property of the Unicode version the interpreter happens to
# ship, not of the character, so stripping Cn would make the emitted meta-data
# depend on when the pattern below was written: every code point assigned by a
# later Unicode release would be silently deleted from names and descriptions
# until it was rewritten. The categories that are stripped are all immutable
# under the Unicode stability policy, so this set never changes.
# https://www.unicode.org/policies/stability_policy.html
STRIP_CATEGORIES = frozenset(['Cc', 'Cs', 'Co', 'Zl', 'Zp'])

#===============================================================================
# Noncharacters are permanently reserved and are not for interchange. They are
# Cn, but unlike the rest of Cn the set is fixed: Noncharacter_Code_Point is an
# immutable property.
NONCHARACTERS = [
  (0xFDD0, 0xFDEF),
  *[ (0x10000*plane + 0xFFFE, 0x10000*plane + 0xFFFF) for plane in range(17) ] ]

#===============================================================================
# Individual format characters (Cf) that are stripped even though the rest of
# the category is kept. Unlike the joiners and marks that legitimate text needs,
# these carry no content of their own:
# * the explicit directional embeddings, overrides and isolates re-order the
#   display of the text that follows them, so rendered meta-data can be made to
#   disagree with the source it was written from -- the "Trojan source" spoof,
#   CVE-2021-42574
# * a byte order mark is meaningful only as the first code point of a stream,
#   which a meta-data value is not, and ``str.strip`` does not remove it
# These code points are immutable, as are the categories above.
STRIP_FORMAT = [
  # U+202A-U+202E explicit directional embeddings and overrides
  (0x202A, 0x202E),
  # U+2066-U+2069 explicit directional isolates
  (0x2066, 0x2069),
  # U+FEFF zero width no-break space, i.e. a byte order mark
  (0xFEFF, 0xFEFF) ]

#===============================================================================
# Code points stripped individually, in addition to :data:`STRIP_CATEGORIES`.
STRIP_CODES = [ *NONCHARACTERS, *STRIP_FORMAT ]

#===============================================================================
# Inclusive code point ranges matched by :data:`nonprintable`. Every range is
# fixed by the Unicode stability policy, so this is written out rather than
# generated from the ``unicodedata`` of whichever interpreter is running.
STRIP_RANGES = [
  # Cc, apart from '\t' (U+0009) and '\n' (U+000A)
  (0x0000, 0x0008), (0x000B, 0x001F), (0x007F, 0x009F),
  # Zl line separator, Zp paragraph separator
  (0x2028, 0x2029),
  # Cs surrogates
  (0xD800, 0xDFFF),
  # Co private use
  (0xE000, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD),
  *STRIP_CODES ]

#===============================================================================
def _strip_char(c):
  """Reference definition of the characters removed from package meta-data.

  :data:`nonprintable` is the compiled equivalent, and is what
  :func:`partis.pyproj.norm_printable` actually applies.
  """
  return (
    c not in KEEP
    and (
      unicodedata.category(c) in STRIP_CATEGORIES
      or any( lo <= ord(c) <= hi for lo, hi in STRIP_CODES ) ) )

#===============================================================================
def _fmt(i):
  if i < 2**8:
    return rf'\x{i:02X}'

  if i < 2**16:
    return rf'\u{i:04X}'

  return rf'\U{i:08X}'

#===============================================================================
# NOTE: here new-lines '\n' and tabs '\t' are considered printable, even though
# '\n'.isprintable() returns False
nonprintable = re.compile(
  '[' + ''.join(
    _fmt(lo) if lo == hi else ( _fmt(lo) + '-' + _fmt(hi) )
    for lo, hi in STRIP_RANGES ) + ']',
  re.UNICODE )
