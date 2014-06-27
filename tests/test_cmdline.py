# -*- coding: utf-8 -*-
import re

def test_cmdline(capsys):
    from timebook.cmdline import run_from_cmdline
    try:
        run_from_cmdline(['--help'])
    except SystemExit:
        pass
    out, err = capsys.readouterr()
    regex = re.compile(r'^Timebook time tracker.*')
    assert regex.search(out) is not None
