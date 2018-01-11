# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from setuptools import find_packages, setup

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='plum',
    version='0.1.0',
    description='Multiple dispatch in Python',
    long_description=readme,
    author='Wessel Bruinsma',
    author_email='wessel.p.bruinsma@gmail.com',
    url='https://github.com/wesselb/plum',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)
