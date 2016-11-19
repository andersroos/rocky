import os
import sys


def add(path_relative_to_file, _file_):
    """
    Add absolute path to sys.path if not present yet. The path to add is expressed as a relative path (the
    interesting path) to a file (__file__) at callee.
    """
    path = os.path.abspath(os.path.join(os.path.dirname(_file_), path_relative_to_file))
    if path not in sys.path:
        sys.path.append(path)
