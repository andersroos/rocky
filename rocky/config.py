import os
from collections import Mapping, OrderedDict, Iterable
from configparser import ConfigParser
from logging import getLogger, NOTSET

import itertools
import sys

logger = getLogger("rocky")

__doc__ = """ Reading of config values from multiple sources, with filtering, mappings and logging of origin.

Config is read through config sources, this module have sources to read from environment, config file, python file,
dict, object properties and file content. A config source can be any obejct with a get method taking the key of a
config variable and have a property name (optional). A key can be a string or a path (iterable of strings for deep
config structures).

A key that is a path of length 1 will internally be treated as the equivalent of the string in the path (except that
it will not be split converted by splitting on __, see beklow).

When using get of a key a path can also be expressed as a string by __-separating it, it will be converted to a tuple
of strings immediatly on call to get. If this conversion is unwanted (if the key should have __ in it) a path of
length 1 can be used instead. Paths as iterables of strings will also be converted to tuples immediatly. This is what
should be used in mappings and include.

Config sources are combined through the Config class where an order between sources can be defined (globally or for
each key). The config class will keep track of the source of the config and also cache the value to make it yeld the
same result every time. It may optionally log config value and source on first use.

Mappings

Mappings can be defined for most config sources defined here. A mapping will map a key to another to make the get use
that one instead. For example a mapping {'USER': 'LOGNAME'} for a rocky.config.Env src will make src.get('USER')
return the value of the LOGNAME environment variable insated of USER. A mapping can be any collections.Mapping or
callable taking a key returning another. This does not block getting of 'LOGNAME', it is still usable.

NOTE: __-separated strings will not be converted to paths in the mapping, the conversion is only done when calling
get. For example the mapping {'deep__var': 'var__deep'} will only convert a string to another string,
after the mapping the resulting 'var__deep' will not be split into a length 2 path. The mapping {'deep__var': ('var',
'deep')} will map a string to a path of length 2, but if getting with the tuple ('deep', 'var') it will not be mapped
to ('var', 'deep'). The mapping {('deep', 'var'): ('var', 'deep')} will work as expected both when getting by
('deep', 'var') and 'deep__var', so when mapping paths it is best to use tuples only.

Filters

Sources here can also have include filters for only allowing the included keys (or allow all if None). Filters are
checked before mappings (but after converting __-separated strings to paths. Like for mappings paths should be tuples
of strings when using them in a filter or they will not work as expected. Keys of depth one can be either tuples or
strings.

If getting a key not included in the filter None will be returned.

"""


try:
    # Python 3.5 and above.
    from importlib.util import module_from_spec
    from importlib.util import spec_from_loader
    from importlib.machinery import SourceFileLoader

    def load_module_from_file(filename, modulename):
        loader = SourceFileLoader(modulename, filename)
        spec = spec_from_loader(loader.name, loader)
        module = module_from_spec(spec)
        loader.exec_module(module)
        return module

except ImportError:
    # Python 3.4 and below.
    import imp

    def load_module_from_file(filename, modulename):
        imp.load_source(modulename, filename)
        return sys.modules[modulename]


__all__ = [
    "Base",
    "Dict",
    "Props",
    "Env",
    "PyFile",
    "ConfigFile",
    "Default",
    "Config",
    "as_path",
    "as_key",
]


#
# Config sources.
#


class Base(object):
    """ Base class for config source. A config source is anything with a get method and an optional name property. """

    def __init__(self, src=None, name=None, mapping=None, include=None):
        """ Init config source.

        src -- the source of the config, depends on the source
        name -- the name of the source
        mapping -- see module doc
        include -- see module doc
        """
        self.src = src
        self.name = name
        self.mapping = mapping
        self.include = include

    def get(self, key):
        """ Get a variable from this config source. Returns None if does not exist, raises if not in include. """
        path = _key_to_path(key)
        path = _filter_map(self.include, self.mapping, path)
        if path is not None:
            val = self._get_path(path)
            if val is not None:
                return val
        return None

    def _get_path(self, path):
        """ Impleemnt in child. Used to get from full path in obj. """
        obj = self.src
        for segment in path:
            obj = self._get_segment(obj, segment)
            if obj is None:
                break
        return obj

    def _get_segment(self, obj, segment):
        """ Implement in child. Used to traverse path segments for config. """
        return None


class Dict(Base):
    """ Reads values from a dict. If using paths values can be read form any depth of dicts in dicts. """

    def __init__(self, src=None, name="dict", mapping=None, include=None):
        super().__init__(src=src, name=name, mapping=mapping, include=include)

    def _get_segment(self, obj, segment):
        return obj.get(segment, None) if isinstance(obj, Mapping) else None


class Props(Base):
    """ Reads values as properties from an object. If using paths values can be read form any depths of peroperties on
    objects. Anything supporting getattr will work, it is for example usable for reading from a python module. """

    def __init__(self, src=None, name='object', mapping=None, include=None):
        super().__init__(src=src, name=name, mapping=mapping, include=include)

    def _get_segment(self, obj, segment):
        return getattr(obj, segment, None)


class Env(Base):
    """ Reads config variables from environment. This source does not support paths. """

    def __init__(self, name='env', mapping=None, include=None):
        super().__init__(name=name, mapping=mapping, include=include)

    def _get_path(self, path):
        if len(path) != 1:
            return None
        return os.environ.get(path[0])


class PyFile(Props):
    """ Load python file as a module and read variables from it. """

    def __init__(self, filename=None, name=None, mapping=None, include=None, fail_on_not_found=True):

        basename = os.path.basename(filename)
        module_name, _ = os.path.splitext(basename)

        try:
            module = load_module_from_file(filename, module_name)
        except FileNotFoundError:
            if fail_on_not_found:
                raise
            else:
                module = None

        super().__init__(src=module, name=name or basename, mapping=mapping, include=include)

    def _get_path(self, path):
        if not self.src:
            return None
        return super()._get_path(path)


class ConfigFile(Base):
    """ Use a config file as source, only supports keys as paths of length 2. """

    def __init__(self, filename, name=None, mapping=None, include=None, fail_on_not_found=True):

        config = ConfigParser()
        try:
            with open(filename, 'r') as f:
                config.read_file(f)
        except FileNotFoundError:
            if fail_on_not_found:
                raise
            else:
                config = None

        super().__init__(src=config, name=name or os.path.basename(filename), mapping=mapping, include=include)

    def _get_path(self, path):
        if not self.src or len(path) != 2:
            return None

        return self.src.get(*path, fallback=None)


class FileContent(object):
    """ Reads the content of a file and return it as a string for all keys. """

    def __init__(self, filename, name=None, fail_on_read_error=False, strip=True, encoding='utf-8'):
        """
        Init a file content source.

        filename -- the filename to read
        name -- the name of the source
        fail_on_read_error -- raise exception if not found or permission denied or other errors
        encoding -- decode the content to a string, set to None to skip decoding
        strip -- strip the content before returning, only if encoding is set
        """
        self.name = name or os.path.basename(filename)
        try:
            with open(filename, 'rb') as f:
                value = f.read()
                if encoding:
                    value = value.decode('utf-8')
                    if strip:
                        value = value.strip()
                self.value = value
        except OSError:
            if fail_on_read_error:
                raise
            else:
                self.value = None

    def get(self, key):
        return self.value


class Default(object):
    """ Very simple config source that returns the same value for all keys. """
    
    def __init__(self, value, name='default'):
        self.value = value
        self.name = name

    def get(self, key):
        return self.value


#
# Config the main class.
#


class Config(object):
    """
    Class for reading config values from multiple sources. Can optionally log first
    use of keys and values. Will cache values for consistency.
    """

    def __init__(self, *sources, log_level=NOTSET):
        """
        Init with sources in order (optional, can be changed later.

        source -- default sources used (in order) for get, see module doc and property doc

        log_level -- log first use of each variable with name, vaule and source, logging.NOTSET for off
        """
        self._sources = sources
        self._log_level = log_level
        self._cache = OrderedDict()

    def get_sources(self):
        return self._sources

    def set_sources(self, sources):
        self._sources = sources

    sources = property(get_sources, set_sources,
                       doc='Iterable of config sources, checked in order on get, can be changed at any time,'
                           'already getted values will be cached and will not be affected.')

    def get(self, key, *sources, default=None, log_level=None, log_value=True):
        """
        Get config value for key using default sources or provided sources. A successful get (not returning None)
        will be cache value and source, subsequent get for that key will return that value regardless of other
        parameters.

        key -- the key for the value

        sources -- custom source order for this key, if no sources the sources set by constructor or source property
            will be used

        default -- return this value if all sources fail, default value will be cached and logged as specified

        log_level -- override log_level from constructor, makes get log key, value and source on first use,
            set to logging.NOTSET to turn off logging

        log_value -- set to False to prevent logging of value but still log the source for this key
        """
        value, source = self.get_with_source(key, *sources, default=default, log_level=log_level, log_value=log_value)
        return value

    def source(self, key, *sources, default=None, log_level=None, log_value=True):
        """ Same as get but return source instead of value. """
        value, source = self.get_with_source(key, *sources, default=default, log_level=log_level, log_value=log_value)
        return source

    def __getattr__(self, key):
        """ Same as get. """
        return self.get(key)

    def log_cached(self, log_level=None):
        """
        Log all cached keys, values and sources. This can be useful if setting up logging after using config.

        log_level --  override log_level from constructor, makes get log key, value and source on first use,
            set to logging.NOTSET to turn off logging
        """
        for path, (value, source, log_value) in self._cache.items():
            self._log(path, value, source, log_level, log_value)

    def get_with_source(self, key, *sources, default=None, log_level=None, log_value=True):
        """ Same as get but return a tuple <value, source>. """

        path = _key_to_path(key)

        value, source, *rest = self._cache.get(path, (None, None))
        if value is not None:
            return value, source

        if path is None:
            return None, None

        for source in itertools.chain(sources or self._sources, [] if default is None else [Default(default)]):
            value = source.get(path)
            if value is not None:
                self._cache_and_log(path, value, source, log_level, log_value)
                return value, source

        return None, None

    def _cache_and_log(self, path, value, source, log_level, log_value):
        self._cache[path] = value, source, log_value
        self._log(path, value, source, log_level, log_value)

    def _log(self, path, value, source, log_level, log_value):
        if log_level is None:
            log_level = self._log_level

        if log_level != NOTSET:
            logger.log(log_level, "config %s = %r (%s %s)" %
                       (as_key(path), value if log_value else "<not logging value>",
                        source.__class__.__name__, getattr(source, 'name', '')))


#
# Utils.
#


def as_path(key):
    """ Convert string to tuple of length 1 or other iterable to tuple. """

    if isinstance(key, str):
        return key,

    if isinstance(key, Iterable):
        return tuple(key)

    raise TypeError("bad key %r" % key)


def as_key(key):
    """ Convert path to a string of of length 1 otherwise return it. """
    if isinstance(key, tuple) and len(key) == 1:
        return key[0]

    return key


#
# Internal helpers.
#


def _key_to_path(key):
    if isinstance(key, str):
        return tuple(key.split('__'))

    return as_path(key)


def _map_path(mapping, path):
    """ Return path or mapped path if it matches a mapping. """

    if isinstance(mapping, Mapping):
        mapped = mapping.get(path)
        if mapped is not None:
            return as_path(mapped)

        mapped = mapping.get(as_key(path))
        if mapped is not None:
            return as_path(mapped)

        return path

    return as_path(mapping(as_key(path)))


def _filter_map(include, mapping, path):
    """ Check includes them map. """

    if include and not (path in include or as_key(path) in include):
        return None

    if mapping:
        return _map_path(mapping, path)

    return path


