# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import sys

vi = sys.version_info
if vi.major == 3 and vi.minor < 6:  # pragma: no cover
    raise SystemError('For Python 3, Plum requires at least Python 3.6.')

from .dispatcher import *
from .function import *
from .tuple import *
from .type import *
from .resolvable import *
from .parametric import *
from .promotion import *
