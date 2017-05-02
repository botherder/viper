#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of Viper - https://github.com/viper-framework/viper
# See the file 'LICENSE' for copying permission.

from setuptools import setup, find_packages
from viper.common.version import __version__

setup(
    name='viper',
    version=__version__,
    author='Claudio Guarnieri',
    author_email='nex@nex.sx',
    description="Binary Analysis & Management Framework",
    url='http://viper.li',
    license='BSD 3-Clause',

    scripts=['viper-cli', 'viper-api', 'viper-web', 'viper-update'],
    packages=find_packages(),
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)
