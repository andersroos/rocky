import os
import unittest
from collections import namedtuple

from os.path import join, dirname

from rocky.config import Dict, as_path, Props, Env, PyFile, ConfigFile, Config, Default, FileContent


testdir = dirname(__file__)


class DictSrcTest(unittest.TestCase):

    def test_unmapped_unfiltered_get_values(self):
        s = Dict(dict(INSTALL_DIR='/dir', deep=dict(var=23)))

        self.assertEqual('/dir', s.get('INSTALL_DIR'))
        self.assertEqual('/dir', s.get(('INSTALL_DIR',)))
        self.assertEqual(dict(var=23), s.get('deep'))
        self.assertEqual(dict(var=23), s.get(('deep',)))
        self.assertEqual(None, s.get('no_key'))
        self.assertEqual(None, s.get(('no_key',)))
        self.assertEqual(23, s.get('deep__var'))
        self.assertEqual(None, s.get(('deep__var',)))
        self.assertEqual(23, s.get(['deep', 'var']))

    def test_mapped_get_values(self):
        s = Dict(dict(INSTALL_DIR='/dir'), mapping={"inst_dir": "INSTALL_DIR"})

        self.assertEqual('/dir', s.get('INSTALL_DIR'))
        self.assertEqual('/dir', s.get('inst_dir'))

        s = Dict(dict(deep=dict(var=23)), mapping={('deepu', 'varu'): ("deep", "var")})

        self.assertEqual(dict(var=23), s.get('deep'))
        self.assertEqual(23, s.get('deep__var'))
        self.assertEqual(23, s.get(['deepu', 'varu']))
        self.assertEqual(23, s.get('deepu__varu'))
        self.assertEqual(None, s.get('deepu'))
        self.assertEqual(None, s.get(['deepu', 'var']))

        s = Dict(dict(INSTALL_DIR='/dir'), mapping=lambda n: n + "_DIR")

        self.assertEqual(None, s.get('INSTALL_DIR'))
        self.assertEqual('/dir', s.get('INSTALL'))
        self.assertEqual('/dir', s.get(('INSTALL',)))

        s = Dict(dict(deep=dict(var=23)), mapping=lambda n: as_path(n) + ("var",))

        self.assertEqual(23, s.get('deep'))
        self.assertEqual(23, s.get(('deep',)))
        self.assertEqual(None, s.get('deep__var'))
        self.assertEqual(None, s.get(['deep', 'var']))  # ????

    def test_filtered_get_values(self):
        s = Dict(dict(INSTALL_DIR='/dir', deep=dict(var=23), tuple=44),
                 include=["INSTALL_DIR", ('tuple',), ('deep', 'var'), 'not_present', 'not__a_path'])

        self.assertEqual('/dir', s.get('INSTALL_DIR'))
        self.assertEqual('/dir', s.get(('INSTALL_DIR',)))
        self.assertEqual(44, s.get('tuple'))
        self.assertEqual(23, s.get('deep__var'))
        self.assertEqual(23, s.get(('deep', 'var')))
        self.assertEqual(None, s.get('not_present'))
        self.assertEqual(None, s.get('not__a_path'))
        self.assertEqual(None, s.get("not in include"))
        self.assertEqual(None, s.get(('INSTALl_DIR', 'path')))
        self.assertEqual(None, s.get(('not', 'a_path')))

    def test_filtered_mapped_get_values(self):
        ds = Dict(dict(INSTALL_DIR='/dir'), include=["inst_dir"], mapping={'inst_dir': 'INSTALL_DIR'})

        self.assertEqual('/dir', ds.get('inst_dir'))
        self.assertEqual(None, ds.get("INSTALL_DIR"))


class OtherSourcesTest(unittest.TestCase):

    def test_prop_src_specifics(self):
        s = Props(namedtuple("o1", "foo,deep")(foo=44, deep=namedtuple("o2", "val")(val=23)))

        self.assertEqual(44, s.get('foo'))
        self.assertEqual(23, s.get('deep__val'))
        self.assertEqual(None, s.get('non_existent'))
        self.assertEqual(None, s.get('too_deep__val'))

    def test_env_src_specifics(self):
        os.environ['testing_an_environment_variable'] = "23"
        os.environ['paths_separated_by__works_only_by_tuple'] = "44"

        s = Env()

        self.assertEqual("23", s.get('testing_an_environment_variable'))
        self.assertEqual(None, s.get('paths_separated_by__works_only_by_tuple',))
        self.assertEqual("44", s.get(('paths_separated_by__works_only_by_tuple',)))
        self.assertEqual(None, s.get('testing_a_hopefully_non_existent_environment_variable_4335'))

    def test_py_file_src_specifics(self):
        s = PyFile(join(testdir, "conf_python_module_for_t_e_s_t.py"))

        self.assertEqual("/dir", s.get('INSTALL_DIR'))
        self.assertEqual(27, s.get('deep__val'))
        self.assertEqual(28, s.get('IF'))
        self.assertEqual(None, s.get('not_set'))

        with self.assertRaises(FileNotFoundError): PyFile('/tmp/non_existent_file_dsaasddsagerwvwe.py')

        s = PyFile('/tmp/non_existent_file_dsaasddsagerwvwe.py', fail_on_not_found=False)

        self.assertEqual(None, s.get('INSTALL_DIR'))

    def test_config_file_src_specifics(self):
        s = ConfigFile(join(testdir, "config_t_e_s_t.ini"))

        self.assertEqual("/dir", s.get('main__INSTALL_DIR'))
        self.assertEqual("27", s.get('deep__val'))
        self.assertEqual(None, s.get('not_set'))

        with self.assertRaises(FileNotFoundError): ConfigFile('/tmp/non_existent_file_dsaasddsagerwvwe.ini')

        s = ConfigFile('/tmp/non_existent_file_dsaasddsagerwvwe.ini', fail_on_not_found=False)

        self.assertEqual(None, s.get('main__INSTALL_DIR'))

    def test_default_src_specifics(self):
        s = Default("defdef")

        self.assertEqual("defdef", s.get('sune sune'))
        self.assertEqual("defdef", s.get('deep__val'))
        self.assertEqual("defdef", s.get('not_set'))

    def test_file_contentsrc__specifics(self):
        s = FileContent(join(testdir, "content_data_t_e_s_t.txt"))

        self.assertEqual("content", s.get('any'))
        self.assertEqual("content", s.get('deep__val'))

        s = FileContent(join(testdir, "content_data_with_whitespace_t_e_s_t.txt"))

        self.assertEqual("cont ent", s.get('any'))
        self.assertEqual("cont ent", s.get('deep__val'))

        s = FileContent(join(testdir, "content_data_with_whitespace_t_e_s_t.txt"), strip=False)

        self.assertEqual("  cont ent\n  \n", s.get('any'))

        with self.assertRaises(FileNotFoundError):
            FileContent('/tmp/non_existent_file_dsaasddsagerwvwe.ini', fail_on_read_error=True)

        s = FileContent('/tmp/non_existent_file_dsaasddsagerwvwe.ini')

        self.assertEqual(None, s.get('any'))


class ConfigTest(unittest.TestCase):

    def test_get_config_as_prop_and_string(self):
        c = Config(Dict(dict(INSTALL_DIR='/dir', deep=dict(var=27))))

        self.assertEqual("/dir", c.get('INSTALL_DIR'))
        self.assertEqual("/dir", c.INSTALL_DIR)
        self.assertEqual(27, c.get("deep__var"))
        self.assertEqual(27, c.deep__var)
        self.assertEqual(None, c.get('non_existent'))
        self.assertEqual(None, c.non_existent)

    def test_get_config_is_cached(self):
        d = {'foo': 27}
        c = Config(Dict(d))

        self.assertEqual(27, c.foo)

        d['foo'] = 28

        self.assertEqual(27, c.get("foo"))

    def test_get_config_source_order(self):
        s1 = Dict({'foo': 27})
        s2 = Dict({'foo': 28, 'bar': 19})
        c = Config(s1, s2)

        self.assertEqual((27, s1), c.get_with_source('foo'))
        self.assertEqual((19, s2), c.get_with_source('bar'))

    def test_get_in_different_source_orders(self):
        s1 = Dict({'foo': 1, 'bar': 1, 'fun': 1})
        s2 = Dict({'foo': 2, 'bar': 2, 'fun': 2})
        s3 = Dict({'foo': 3, 'bar': 3, 'fun': 3})

        c = Config(s1, s2, s3)
        self.assertEqual(1, c.foo)
        self.assertEqual(2, c.get('bar', s2, s3, s1, default=1))
        self.assertEqual(3, c.get('fun', s3, s1, s2))

        self.assertEqual(1, c.foo)
        self.assertEqual(2, c.bar)
        self.assertEqual(3, c.fun)

        c._cache = {}
        self.assertEqual(1, c.foo)
        self.assertEqual(1, c.bar)
        self.assertEqual(1, c.fun)

    def test_get_chaning_default_source_order(self):
        s1 = Dict({'foo': 1, 'bar': 1, 'fun': 1})
        s2 = Dict({'foo': 2, 'bar': 2, 'fun': 2})
        s3 = Dict({'foo': 3, 'bar': 3, 'fun': 3})

        c = Config(s1, s2, s3)
        self.assertEqual(1, c.foo)
        c.sources = [s2, s3, s1]
        self.assertEqual(2, c.bar)
        c.sources = [s3, s1, s2]
        self.assertEqual(3, c.fun)

        self.assertEqual(1, c.foo)
        self.assertEqual(2, c.bar)
        self.assertEqual(3, c.fun)

    def test_get_with_default(self):
        c = Config(Dict({'foo': 1}))

        self.assertEqual(1, c.get('foo', default=23))
        self.assertEqual(23, c.get('bar', default=23))
        self.assertEqual(23, c.bar)


