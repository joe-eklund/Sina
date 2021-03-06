Contents
========
- Overview
- Software Dependencies
- Standard Setup
- Manual Setup

    - Creating the Environment
    - Installing Software Dependencies
    - Completing the Installation

- Activating the Virtual Environment
- Deactivating the Virtual Environment
- Using the Example Notebooks
- Testing
- Supported Environments


Overview
========

Sina provides a command line interface for exploring and querying data stored
using the Mnoda schema.  Once you install the software in a virtual environment,
using the standard or manual process described below, you are ready to use the
tools.  Each time you log in you'll first need to activate the environment.
When you're done, we recommend you deactivate the virtual environment to get
back to your default environment or end your session.


Software Dependencies
=====================

We have a requirements file for setting up the initial development virtual
environment.  The file is called [development.txt](development.txt),
which resides in the python requirements subdirectory.


LC Setup
========

If you're on an LC machine, you can use a virtual environment with dependencies
already installed::

    $ source /collab/usr/gapps/wf/releases/sina/bin/activate

(The above is for bash; other activation scripts, e.g. activate.csh, can be found
in the same directory.)

Sina will now be available for use via Python virtual environment, and can be
tested with `sina -h` (which should display a help message). When you're done,
use `deactivate` to exit the virtual environment. If you run into issues,
please email us at siboka@llnl.gov.


Local Setup
===========

Standard installation, provided by the Makefile, is initiated by entering
the following at the command line::

    $ make

This command creates the virtual environment, installs \(missing\) dependencies,
and installs Sina.

You can build the documentation, which will appear in `build/docs`, using::

    $ make docs

Test are run by entering::

    $ make tests

Alternatively, you can run all of the above by entering the following::

    $ make all

This will install Sina with its default backend (SQL).

Once installation is complete, you are ready to activate the environment -- see
"Activating the Virtual Environment" -- and begin using Sina. You can also install
the optional Cassandra backend with::

    $ make cassandra

Additional command line tools (such as diffing Records) are available with::

    $ make cli-tools


Manual Setup
============

You will need to create, activate, and install software dependencies in your
environment.


Creating the Environment
------------------------
Enter the following command to set up your initial environment::

    $ python -m virtualenv venv   # venv can be any name you want

Now activate the environment \(see "Activating the Virtual Environment"\).

You need to be in the proper Sina directory before proceeding to install
dependencies, so enter the following command::

    (venv) $ cd $SINA_PYTHON

where `SINA_PYTHON` is the `python` subdirectory of the Sina source code.


Installing Software Dependencies
--------------------------------
You first need to make sure there is a requirements/links.txt file that contains
the appropriate link constraints.  There are two requirements files containing
flags and links used in our supported environments::

- requirements/lc-links.txt
- requirements/no-links.txt

The first file contains the options needed to restrict packages to those
available on the wheelhouse hosted on the Open Computing Facility (OCF) at
Lawrence Livermore National Laboratory.  The second file contains no flags.
The links.txt file is included in other requirements files to ensure the
options are consistent for the build and testing processes.

Once you have a suitable requirements/links.txt file, enter the following
command to install basic Sina dependencies::

    $(venv) pip install -r requirements/development.txt


Completing the Installation
---------------------------
The requirements file should install the package in editable mode but, if
not, you can install the package via::

    $(venv) pip install -e .


Activating the Virtual Environment
==================================
Enter the following command to enter the virtual environment::

    $ source $SINA_PYTHON/venv/bin/activate  # use activate.csh if in a [t]csh

where `SINA_PYTHON` is the python subdirectory of the Sina source code.
You will need to do this every time you want to start up a session in the named
virtual environment.


Deactivating the Virtual Environment
====================================
Enter the following command to deactivate the virtual environment::

    (venv) $ deactivate

when you are done.


Using the Example Notebooks
===========================

Sina contains Jupyter notebooks that demonstrate how to use it with
sample datasets. Files can be found in the examples directory, and are
organized by dataset, with data_overview.rst containing descriptions of each
set. To use the notebooks, you'll first need to run getting_started.ipynb
(also in the examples directory) from the LC Jupyter server at
lc.llnl.gov/jupyter. After that, you'll be ready to run the rest of the notebooks.
To clean all output from the notebooks::

    (venv) $ make clean-notebooks


Testing
=======

This package uses nosetests to run unit tests.  Enter the following while in
your virtual environment::

    (venv) $ nosetests

Additional tests, which include checks for PEP8 compliance and proper
documentation, can be run my entering the following::

    $ make tests

This command will set up and enter the necessary virtual environment.


Supported Environments
======================

Sina is regularly tested in the following environments:

- **OSX 10.13**: Primary development environment for most team members.
  If you are not on the LC network, be sure to comment out `--no-index` in the
  requirements file.
- **TOSS 3, RedHat 7.4 (quartz, rzsonar)**: Automated testing environment
- **TOSS 3, RedHat 7.5 (catalyst, rztopaz)**: Secondary development environment

Absence is not an indication that Sina will not work; please consider expanding this list!
