import os
from setuptools import setup

setup(
    name = 'mortimer',
    author = 'Aaron Miller, Jim Walker',
    version = '2.0.0',
    author_email = 'jim@couchbase.com',
    packages = ['mortimer'],
    scripts=[os.path.join('scripts', 'mortimer')],
    include_package_data = True,
    install_requires = ['tornado', 'lepl', 'pyparsing'],
    license = 'Copyright 2014 Couchbase',
    url = 'https://github.com/couchbaselabs/mortimer',
    keywords = 'graphing analysis logs couchbase',
    description = 'Post-mortem log analysis tool for Couchbase',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: Other/Proprietary License',
        'Topic :: Database',
        'Topic :: Internet :: Log Analysis',
        'Programming Language :: Python :: 2',
    ],
    zip_safe=False,
)

