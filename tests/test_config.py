# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import binascii
import shutil
import tempfile

from timebook.config import parse_config

def test_parse_config(capsys):
    seed = binascii.hexlify(os.urandom(4))
    fname = os.path.join(tempfile.gettempdir(), 'test-%s' % seed, 'test_timebook_config.ini')
    parse_config(fname)
    shutil.rmtree(os.path.dirname(fname))
