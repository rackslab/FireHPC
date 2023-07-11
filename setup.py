#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
#
# This file is part of FireHPC.
#
# FireHPC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FireHPC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with FireHPC.  If not, see <https://www.gnu.org/licenses/>.

from setuptools import setup, find_packages
from pathlib import Path

# get __version__
exec(open('firehpc/version.py').read())

setup(
    name='FireHPC',
    version=__version__,
    packages=find_packages(),
    author='Rémi Palancher',
    author_email='remi@rackslab.io',
    license='GPLv3+',
    platforms=['GNU/Linux'],
    install_requires=[
        'ansible-runner',
        'jinja2',
        'PyYAML',
    ],
    entry_points={
        'console_scripts': [
            'firehpc=firehpc.exec:FireHPCExec.run',
        ],
    },
    description='Instantly fire up container-based emulated HPC cluster',
    long_description=Path(__file__).parent.joinpath("README.md").read_text(),
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Systems Administration',
    ],
)
