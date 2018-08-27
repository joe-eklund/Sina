#!/bin/bash

# Full deployment script.
# Builds venvs, runs tests, builds wheel, deploys documentation

# Takes 2 arguments: where to deploy the wheel file, and where to deploy the documentation folder
# Creates(/updates) $SYM_NAME in dir specified by first arg
# Creates(/updates) $DOC_NAME folder in dir specified by second arg
# Both of these must exist, and the first (wheel folder) must have a subdirectory named "wheels".

TEMP_WHEEL_HOME=temp_whl # folder created for temp wheel storage
SYM_NAME=sina # symlink for wheel
VENV_SYM_NAME=sina # symlink for venv
DOC_NAME=sina # subfolder name in documentation directory
PERM_GROUP=wciuser  # Group that will be given access to docs, wheelfile, and venv

BASE_PYTHON=`which python`
WHEELHOUSE=/usr/gapps/python/wheelhouse

set -e
umask 027

# Location check
if [ ! -f setup.py ]
  then
    echo "Please run this deploy script from the sina root folder"
    exit 1
fi

# Arg check
if [ $# != 2 ]
  then
    echo "Script takes exactly two arguments: <wheel_deploy_dir> <doc_deploy_dir>"
    exit 1
fi

# Group check
grep "^$PERM_GROUP:" /etc/group > /dev/null || (echo "Group $PERM_GROUP doesn't exist. Update the PERM_GROUP or change machines." && exit 1)

# Converts any relative paths to absolute and ensures ending in /
DEPLOY_DIR=`readlink -f $1`/
DOC_DIR=`readlink -f $2`/
RUN_DIR=`pwd`
TEMP_WHEEL_HOME=$RUN_DIR/$TEMP_WHEEL_HOME

# Run tests (also builds docs)
$RUN_DIR/tests/run_all_tests.sh

# Tests passed, build the wheel
rm -rf $TEMP_WHEEL_HOME
mkdir $TEMP_WHEEL_HOME

# Need to source a venv so that pip install 'wheel' can be installed
# That's necessary to prevent an error when bdist_wheel gets used.
source $RUN_DIR/tests/test_venv/bin/activate
# Calling "pip" by itself results in errors from the shebang line being too long
python -m pip install wheel

python $RUN_DIR/setup.py bdist_wheel -d $TEMP_WHEEL_HOME
deactivate

WHEEL_PATH=$(find "$TEMP_WHEEL_HOME" -name "*.whl")
WHEEL_DEST="$DEPLOY_DIR"wheels/

# Deploy the wheel
mv $WHEEL_PATH $WHEEL_DEST
NEWPATH=$WHEEL_DEST`basename $WHEEL_PATH`

# Add/update wheel symlink
ln -f $NEWPATH $WHEEL_DEST$SYM_NAME

# Wheel deployed, deploy docs
DOC_PATH=$DOC_DIR$DOC_NAME
rm -rf $DOC_PATH
cd $RUN_DIR/docs/build && mv html $DOC_PATH
chown -R :$PERM_GROUP $DOC_PATH

# Wheel and docs ready, create a second venv
# Unfortunately, Python venvs can break in strange ways if moved, so we do make one from scratch
cd $RUN_DIR
VENV_PATH="$DEPLOY_DIR"`basename $WHEEL_PATH .whl`/$VENV_SYM_NAME
python -m virtualenv --clear --extra-search-dir $WHEELHOUSE $VENV_PATH
source $VENV_PATH/bin/activate
python $VENV_PATH/bin/pip install -r $RUN_DIR/requirements.txt
python $VENV_PATH/bin/pip install $NEWPATH[jupyter]
# Ensure that installed Sina is the new wheel (fixes permission issues)
python $VENV_PATH/bin/pip install --force-reinstall --no-deps $NEWPATH
deactivate
chown -R :$PERM_GROUP $DEPLOY_DIR

# Add/update venv symlink
ln -sf $VENV_PATH/bin/activate $DEPLOY_DIR$VENV_SYM_NAME