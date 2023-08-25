# -*- coding: utf-8 -*-
import re
from datetime import datetime

import pytest

from timebook.db import Database
from timebook.commands import commands

# Fixtures ###

@pytest.fixture
def patch_input(monkeypatch):
    import builtins
    monkeypatch.setattr(builtins, 'input', lambda *a: 'yes')

time_now = 1397497538.088239

@pytest.fixture
def db():
    return Database(':memory:', None)

@pytest.fixture
def cmd(request):
    cmd_name = request.function.__name__[5:]  # strip the 'test_' prefix
    return commands.get(cmd_name)

@pytest.fixture
def start(db):
    db.execute('''
    insert into entry (
        sheet, start_time, description
    ) values (?,?,?)
    ''', ('default', int(time_now), 'Working'))

@pytest.fixture
def end(start, db):
    db.execute('update entry set end_time = ?', (int(time_now + 300),))

@pytest.fixture
def entries(db):
    return db.execute('select * from entry').fetchall()

# Tests ###

def test_alter(start, cmd, db):
    cmd(db, ['Testing', 'alter'])
    assert entries(db)[0][1:5] == ('default', int(time_now), None, 'Testing alter')

def test_display(capsys, end, cmd, db):
    # Test plain
    cmd(db)
    out, err = capsys.readouterr()
    regex = re.compile(r'Apr 14, 2014.*19:45:38.*19:50:38.*Working.*')
    assert regex.search(out) is not None
    # Test CSV
    cmd(db, format='csv')
    out, err = capsys.readouterr()
    regex = re.compile(r'.*04/14/2014 19:45:38,04/14/2014 19:50:38,300,Working.*', re.M)
    assert regex.search(out) is not None

def test_in(cmd, db):
    time_in_str = datetime.fromtimestamp(time_now).strftime('%Y-%m-%d %H:%M:%S')
    cmd(db, ['Working'], at=time_in_str)
    assert entries(db)[0][1:5] == ('default', int(time_now), None, 'Working')

def test_kill(start, cmd, db, patch_input):
    assert entries(db)[0][1:5] == ('default', int(time_now), None, 'Working')
    cmd(db)
    assert entries(db) == []

def test_list(capsys, end, cmd, db):
    # Full output
    cmd(db)
    out, err = capsys.readouterr()
    regex = re.compile(r'default.*--.*0:00:00.*0:05:00')
    assert regex.search(out) is not None
    # Simple output
    cmd(db, simple=True)
    out, err = capsys.readouterr()
    assert out == 'default\n'

def test_now(capsys, end, cmd, db):
    cmd(db)
    out, err = capsys.readouterr()
    assert out == 'default: not active\n'
    cmd(db, timesheet='default')
    out, err = capsys.readouterr()
    assert out == 'default: not active\n'

def test_out(start, cmd, db):
    time_out = time_now + 300
    time_out_str = datetime.fromtimestamp(time_out).strftime('%Y-%m-%d %H:%M:%S')
    cmd(db, at=time_out_str)
    assert entries(db)[0][1:5] == ('default', int(time_now), int(time_out), 'Working')

def test_running(capsys, start, cmd, db):
    cmd(db)
    out, err = capsys.readouterr()
    regex = re.compile(r'default.*Working')
    assert regex.search(out) is not None

def test_switch(end, cmd, db):
    from timebook.dbutil import get_current_sheet
    assert get_current_sheet(db) == 'default'
    cmd(db, 'test')
    assert get_current_sheet(db) == 'test'
