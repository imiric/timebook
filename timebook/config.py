# config.py
#
# Copyright (c) 2008-2009 Trevor Caira
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from configparser import ConfigParser

import os

class CustomConfigParser(ConfigParser):
    def __getitem__(self, name):
        return dict(self.items(name))

def subdirs(path):
    path = os.path.abspath(path)
    last = path.find(os.path.sep)
    while True:
        if last == -1:
            break
        yield path[:last + 1]
        last = path.find(os.path.sep, last + 1)

def parse_config(filename):
    config = CustomConfigParser()
    if not os.path.exists(os.path.dirname(filename)):
        for d in subdirs(filename):
            if os.path.exists(d):
                continue
            else:
                os.mkdir(d)
    if not os.path.exists(filename):
        f = open(filename, 'w')
        try:
            f.write('# timebook configuration file')
        finally:
            f.close()
    f = open(filename)
    try:
        config.read_file(f)
    finally:
        f.close()
    return config
