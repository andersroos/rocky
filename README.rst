.. image:: https://travis-ci.org/andersroos/rocky.svg?branch=master
    :target: https://travis-ci.org/andersroos/rocky
       
Rocky
=====

A collection of small libs for better command line programs in
production setting. This is not a framework, use a small bit or
everything.

* Traceable config, no more searching for where the config was
  set. Read them from config file, python file, plain file, command
  line, environment or somewhere you choose. Dump all config to the
  log at once or at first use.

* Handling of pid files, creating, removing and checking.

* Stop gracefully on a single sigint, but die hard when spamming them.

* Argparsing can be done by a number of other libs, not included here,
  personally I like argparse and have added a couple of useful
  functions related to it.

* Adding to sys.path, replace two lines of code with one line of code.
