import os
import os.path as osp
import tempfile

from pytest import (
  raises )

from partis.pyproj import (
  ValidationError,
  PkgInfo,
  PkgInfoAuthor,
  PkgInfoURL,
  PkgInfoReq )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_default():
  pkginfo = PkgInfo(
    project = dict(
      name = 'test_pkg',
      version = '1.2.3' ) )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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
        'test' : 'pytest' },
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
