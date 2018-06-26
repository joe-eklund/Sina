# Getting the Code
When cloning the repository, make sure to do a recursive clone so that you get
the BLT submodule.

```bash
git clone --recursive ssh://git@cz-bitbucket.llnl.gov:7999/sibo/mnoda-cpp.git
```

If you don't do a recursive clone, you can always get BLT afterwards.

```bash
cd mnoda-cpp
git submodule update --init
```

# Building

The best way to build the code is to use the create\_spconfig.sh script to
create a Spack spconfig.py file to use in place of cmake. This will
ensure all the dependencies are brought in and correctly built. The below
assumes you have "spack" in your path and have already configured spack
properly for your platform.

```bash
    cd /path/to/mnoda-cpp
    mkdir build
    cd build
    export SPACK_COMPILER=clang
    ../create_spconfig.sh
    ./spconfig.py .. -DCMAKE_TOOLCHAIN_FILE=../CMAke/Platform/your_platform_file.cmake
    make
    make test
```


# Troubleshooting

Spack requires a path to a fortran compiler (SPACK_FC=<path>) in order to run. If you get an
error relating to SPACK_FC, make sure it's set appropriately.

../create_spconfig.sh should be run with '+docs' as an argument if you intend to generate documentation.


*Important note:*
The above will build all your dependencies with Clang. If you are going to
use a different compiler, make sure to set `SPACK_COMPILER` to the right
value.
