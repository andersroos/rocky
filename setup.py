from setuptools import setup
from codecs import open
from os import path

setup_dir = path.abspath(path.dirname(__file__))

with open(path.join(setup_dir, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='rocky',
    version='0.0.0',
    description='Better command line programs in production, no need to worry, this is a lib, not a framework.',
    long_description=long_description,
    url='https://github.com/andersroos/rocky',
    author='Anders Roos',
    author_email='anders.roos@gmail.com',
    license='Apache-2.0',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Environment :: Console',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='',
    packages=["rocky"],
    install_requires=[
        'psutil',
    ],
    test_suite='test',
)
