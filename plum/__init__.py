# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import platform

version = tuple(int(x) for x in platform.python_version_tuple())
if version[0] == 3 and version[1] < 6:
    raise SystemError('For Python 3, Plum requires at least Python 3.6.'
                      '')  # pragma: no cover

from .dispatcher import *
from .function import *
from .tuple import *
from .type import *
from .resolvable import *
from .parametric import *
from .promotion import *
