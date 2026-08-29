import os
import os.path as osp
import tempfile

from pytest import (
  raises )

from packaging.metadata import parse_email

from partis.pyproj import (
  ValidationError,
  PkgInfo,
  PkgInfoAuthor,
  PkgInfoURL,
  PkgInfoReq )

#===============================================================================
def test_base():
  assert PkgInfoAuthor('asd') == PkgInfoAuthor('asd')
  assert PkgInfoAuthor('asd') != PkgInfoAuthor('xyz')

  assert PkgInfoURL('asd', 'http://asd.com') == PkgInfoURL('asd', 'http://asd.com')
  assert PkgInfoURL('asd', 'http://asd.com') != PkgInfoURL('xyz', 'http://xyz.com')

  assert PkgInfoReq('asd') == PkgInfoReq('asd')
  assert PkgInfoReq('asd') != PkgInfoReq('xyz')

  PkgInfoReq(
    "PySide2 >= 5.14, < 5.15; python_version < '3.8'",
    extra = 'gui')

#===============================================================================
def test_default():
  pkginfo = PkgInfo(
    project = dict(
      name = 'test_pkg',
      version = '1.2.3' ) )

#===============================================================================
def test_unicode():
  # > Whenever metadata is serialised to a byte stream (for example, to save to
  # > a file), strings must be serialised using the UTF-8 encoding.
  # https://packaging.python.org/en/latest/specifications/core-metadata/
  summary = "S\xfcmmary \u2014 caf\xe9 \u2615"
  author = "\xc9mile Zola"
  license = "Copyright \xa9 2024 \xc9mile Zola\n\nAll rights reserved."
  readme = "# R\xebadme\n\nCaf\xe9 \u2615 \u2014 na\xefve \U0001f469\u200d\U0001f4bb\n"

  with tempfile.TemporaryDirectory() as tmpdir:
    readme_file = 'readme.md'

    with open(osp.join(tmpdir, readme_file), 'w', encoding = 'utf-8') as fp:
      fp.write(readme)

    pkginfo = PkgInfo(
      root = tmpdir,
      project = {
        'name': 'test_pkg',
        'version': '1.2.3',
        'description': summary,
        'readme': {'file': readme_file},
        'license': {'text': license},
        'authors': [{'name': author}],
        'keywords': ["caf\xe9", "\u65e5\u672c\u8a9e"] })

    content = pkginfo.encode_pkg_info()

    # must be UTF-8, and not RFC 2047 encoded-words, which consumers of the
    # meta-data do not decode
    assert b'=?utf-8?' not in content
    assert summary.encode('utf-8') in content

    meta, unparsed = parse_email(content)

    assert not unparsed
    assert meta['summary'] == summary
    assert meta['author'] == author
    # norm_printable strips leading and trailing whitespace
    assert meta['description'] == readme.strip()
    assert sorted(meta['keywords']) == sorted(["caf\xe9", "\u65e5\u672c\u8a9e"])

    # multi-line values are folded into RFC 822 continuation lines
    assert meta['license'].splitlines()[0] == "Copyright \xa9 2024 \xc9mile Zola"
    assert meta['license'].split()[-1] == 'reserved.'

#===============================================================================
def test_not_utf8():
  # > Tools MUST assume the file's encoding is UTF-8
  # A file that is not UTF-8 is an error in the project. Decoding it with
  # replacement characters would put content in the meta-data that the author
  # never wrote, and give no indication of where.
  for key, name in [('readme', 'readme.md'), ('license', 'license.txt')]:
    with tempfile.TemporaryDirectory() as tmpdir:
      # 'caf\xe9' as latin-1, which is not a valid utf-8 sequence
      with open(osp.join(tmpdir, name), 'wb') as fp:
        fp.write(b'first line\nsecond caf\xe9 line\n')

      with raises(ValidationError, match = 'Must be UTF-8 encoded, but line 2 column 11'):
        PkgInfo(
          root = tmpdir,
          project = {
            'name': 'test_pkg',
            'version': '1.2.3',
            key: {'file': name} })

#===============================================================================
def test_full():
  with tempfile.TemporaryDirectory() as tmpdir:

    dynamic = ['dependencies']

    authors = [
      {'name': 'asd'},
      {'email': 'asd@asd.com'},
      {'name': 'asd', 'email': 'asd@asd.com'}]

    keywords = ['axat']

    classifiers = ['asd :: asd']

    urls = {
      'home' : 'http://home.com' }

    project = {
      'name' : 'test_pkg',
      'version' : '1.2.3',
      'description' : "asd",
      # 'readme' : '',
      'authors' : authors,
      'maintainers' : authors,
      # 'license' : None,
      # 'dynamic' : dynamic,
      'requires-python' : ">= 3.6.2",
      'dependencies' : ["numpy"],
      'optional-dependencies' : {
        'test' : ['pytest'] },
      'keywords' : keywords,
      'classifiers' : classifiers,
      'urls' : urls,
      'scripts' : {
        'xyz' : 'abc.xyz:func' },
      'gui-scripts': {
        'xyz' : 'abc.xyz:func' },
      'entry-points' : {
        'plugin' : {
          'xyz' : 'abc.xyz:func' } } }

    pkginfo = PkgInfo(
      root = tmpdir,
      project = project )

    pkginfo.add_dependencies(['scipy'])

    #...........................................................................
    readme = "Test Package"

    readme_file_txt = 'readme'
    readme_file_md = 'readme.md'
    readme_file_rst = 'readme.rst'

    with open(osp.join(tmpdir, readme_file_txt), 'w') as fp:
      fp.write(readme)

    with open(osp.join(tmpdir, readme_file_md), 'w') as fp:
      fp.write(readme)

    with open(osp.join(tmpdir, readme_file_rst), 'w') as fp:
      fp.write(readme)

    #...........................................................................
    invalid_entry_points = [
      { 'scripts' : {} },
      { 'console_scripts' : {} },
      { 'gui-scripts' : {} },
      { 'gui_scripts' : {} },
      { 'nested' : {
        'toomuch' : {
          'xyz' : 'abc.xyz:func' } } } ]

    for entry_points in invalid_entry_points:
      with raises( ValidationError ):
        pkginfo = PkgInfo(
          project = {
            **project,
            'entry-points' : entry_points })

    #...........................................................................

    valid_readme = [
      { 'text' : readme },
      { 'file': readme_file_md },
      { 'file': readme_file_rst },
      { 'file': readme_file_txt } ]

    invalid_readme = [
      'junk',
      {},
      { 'text' : readme, 'file': readme_file_md },
      { 'file': 'junk' },
      { 'junk' : 'junk' } ]



    for readme in valid_readme:

      pkginfo = PkgInfo(
        root = tmpdir,
        project = {
          **project,
          'readme' : readme })

      pkginfo.encode_pkg_info()
      pkginfo.encode_entry_points()

    with raises( ValidationError ):
      pkginfo = PkgInfo(
        project = {
          **project,
          'readme' : { 'file': readme_file_md } })

    with raises( ValidationError ):
      pkginfo = PkgInfo(
        project = {
          **project,
          'readme' : readme_file_md })

    for readme in invalid_readme:
      print(readme)

      with raises( ValidationError ):
        pkginfo = PkgInfo(
          root = tmpdir,
          project = {
            **project,
            'readme' : readme })


    #...........................................................................

    valid_license = [
      { 'text' : readme, 'file': readme_file_md },
      { 'text' : readme },
      { 'file': readme_file_md } ]

    invalid_license = [
      'junk',
      {},
      { 'file': 'junk' },
      { 'junk' : 'junk' } ]


    for license in valid_license:

      pkginfo = PkgInfo(
        root = tmpdir,
        project = {
          **project,
          'license' : license })

      pkginfo.encode_pkg_info()
      pkginfo.encode_entry_points()

    with raises( ValidationError ):
      pkginfo = PkgInfo(
        project = {
          **project,
          'license' : { 'file': readme_file_md } })

    for license in invalid_license:
      print(license)

      with raises( ValidationError ):
        pkginfo = PkgInfo(
          root = tmpdir,
          project = {
            **project,
            'license' : license })
