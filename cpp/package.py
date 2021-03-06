from spack import *


class Mnoda(CMakePackage):
    """Mnoda Library"""

    homepage = 'https://lc.llnl.gov/confluence/display/SIBO'
    url = 'https://example.com/tarballs/dummy.tgz'

    version('develop', git='ssh://git@TODO',
            submodules=True, branch='develop')

    variant('docs', default=False,
            description='Allow generating documentation')

    # Higher versions of cmake require C++14 or newer
    depends_on('cmake@3.8.0:3.9.4', type='build')
    depends_on('doxygen', type='build', when='+docs')
    depends_on('nlohmann-json -test')
