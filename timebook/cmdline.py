# cmdline.py
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

"""Timebook time tracker.

Usage:
  t
  t [options] <command> [<args>...]
  t --version

where <command> is one of:
  %s

Options:
  -h --help        Show this help message and exit.
  --version        Show program's version number and exit.
  -C <file>, --config=<file>
                   Specify an alternate configuration file
                   [default: ~/.config/timebook/timebook.ini].
  -b <timebook>, --timebook=<timebook
                   Specify an alternate timebook file
                   [default: ~/.config/timebook/sheets.db].
  -e <encoding>, --encoding=<encoding>
                   Specify an alternate encoding to decode command line
                   options and arguments [default: UTF-8].

"""

import os
from docopt import docopt
from timebook.commands import commands, run_command

from timebook import get_version
from timebook.db import Database
from timebook.config import parse_config
from timebook.cmdutil import AmbiguousLookup, NoMatch

def parse_args():
    cmd_descs = ['%s - %s' % (k, commands[k].description) for k
                 in sorted(commands)]
    help_str = __doc__ % '\n  '.join(cmd_descs)
    args = docopt(help_str, options_first=True, version=get_version())
    encoding = args['--encoding']
    try:
        args.__dict__ = dict((k, v.decode(encoding)) for (k, v) in
                                args.iteritems() if isinstance(v, basestring))
    except LookupError:
        raise SystemExit, 'unknown encoding %s' % encoding

    if not args['<command>']:
        # default to ``t now``
        args['<command>'] = 'now'
    return args

def run_from_cmdline():
    args = parse_args()
    config = parse_config(os.path.expanduser(args['--config']))
    db = Database(os.path.expanduser(args['--timebook']), config)
    cmd, args = args['<command>'], args['<args>']
    try:
        run_command(db, cmd, args)
    except NoMatch, e:
        raise SystemExit, e.args[0]
    except AmbiguousLookup, e:
        raise SystemExit, '%s\n    %s' % (e.args[0], ' '.join(e.args[1]))
