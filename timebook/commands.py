# commands.py
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

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

try:
    import __builtin__
    input = getattr(__builtin__, 'raw_input')
except (ImportError, AttributeError):
    pass

from datetime import datetime, timedelta
from functools import wraps
from gettext import ngettext
import inspect
import os
import subprocess
import sys
import time

from timebook import dbutil, cmdutil

commands = {}

def pre_hook(db, func_name):
    if hasattr(db.config, 'has_section') and db.config.has_section('hooks'):
        hook = db.config['hooks'].get(func_name)
        if hook is not None:
            __import__(hook, {}, {}, [])
            mod = sys.modules[hook]
            if hasattr(mod, 'pre'):
                return mod.pre
    return lambda db, args, kwargs: (args, kwargs)

def post_hook(db, func_name):
    if hasattr(db.config, 'has_section') and db.config.has_section('hooks'):
        hook = db.config['hooks'].get(func_name)
        if hook is not None:
            __import__(hook, {}, {}, [])
            mod = sys.modules[hook]
            if hasattr(mod, 'post'):
                return mod.post
    return lambda db, res: res

def command(name=None, aliases=()):
    def decorator(func):
        func.name = name or func.__code__.co_name
        commands[func.name] = func
        func.description = func.__doc__.split('\n')[0].strip()
        for alias in aliases:
            if alias not in commands:
                commands[alias] = func
        @wraps(func)
        def decorated(db, *args, **kwargs):
            args, kwargs = pre_hook(db, func.name)(db, args, kwargs)
            res = func(db, *args, **kwargs)
            return post_hook(db, func.name)(db, res)
        return decorated
    return decorator

def run_command(db, name, args):
    from docopt import docopt
    func_name = cmdutil.complete(commands, name, 'command')
    try:
        db.execute('begin')
        cmd = commands[func_name]
        cmd_help = inspect.getdoc(cmd)
        args = docopt(cmd_help, argv=[func_name] + args)
        cmd_argspec = inspect.getargspec(cmd)[0]
        call_args = {}
        # Used for stripping reserved characters from the command-line
        # argument, in order to pass the correct argument name to the command
        # function.
        trans_table = dict((ord(c), None) for c in '-<>')
        for arg in args.keys():
            a = arg.translate(trans_table)
            if a in cmd_argspec:
                call_args[a] = args[arg]
        cmd(db, **call_args)
    except:
        db.execute('rollback')
        raise
    else:
        db.execute('commit')

# Commands

@command(aliases=('shell',))
def backend(db):
    """Open the backend's interactive shell

    Usage: t (backend | shell)

    Run an interactive database session on the timebook database.
    Requires the sqlite3 command.
    """
    subprocess.call(('sqlite3', db.path))

@command(name='in', aliases=('start',))
def in_(db, description='', switch=None, out=False, at=None, resume=False,
        extra=None):
    """Start the timer for the current timesheet

    Usage: t (in | start) [options] [<description>...]

    Start the timer for the current timesheet. Must be called before out.
    Notes may be specified for this period. This is exactly equivalent to
    `t in; t alter`.

    Options:
      -s <timesheet>, --switch <timesheet>
                    Switch to another timesheet before starting the timer.
      -o, --out     Clock out before clocking in.
      -a <time>, --at <time>
                    Set time of clock-in.
      -r, --resume  Clock in with description of last active period.
    """
    sheet = switch
    if sheet:
        commands['switch'](db, timesheet=sheet)
    else:
        sheet = dbutil.get_current_sheet(db)
    if resume and description:
        raise SystemExit('"--resume" already sets a description')
    timestamp = cmdutil.parse_date_time_or_now(at)
    if out:
        clock_out(db, timestamp=timestamp)
    running = dbutil.get_active_info(db, sheet)
    if running is not None:
        raise SystemExit('error: timesheet already active')
    most_recent_clockout = dbutil.get_most_recent_clockout(db, sheet)
    description = ' '.join(description) or None
    if most_recent_clockout:
        (previous_timestamp, previous_description) = most_recent_clockout
        if timestamp < previous_timestamp:
            raise SystemExit('error: time periods could end up overlapping')
        if resume:
            description = previous_description
    db.execute('''
    insert into entry (
        sheet, start_time, description, extra
    ) values (?,?,?,?)
    ''', (sheet, timestamp, description, extra))

@command(aliases=('delete',))
def kill(db, timesheet=None):
    """Delete a timesheet

    Usage: t (kill | delete) [<timesheet>]

    Delete a timesheet. If no timesheet is specified, delete the current
    timesheet and switch to the default timesheet.
    """
    if timesheet:
        to_delete = timesheet
        switch_to_default = False
    else:
        to_delete = dbutil.get_current_sheet(db)
        switch_to_default = True
    try:
        yes_answers = ('y', 'yes')
        # Use print to display the prompt since it intelligently decodes
        # unicode strings.
        print(('delete timesheet %s?' % to_delete), end=' ')
        confirm = input('').strip().lower() in yes_answers
    except (KeyboardInterrupt, EOFError):
        confirm = False
        print()
    if not confirm:
        print('canceled')
        return
    db.execute('delete from entry where sheet = ?', (to_delete,))
    if switch_to_default:
        switch(db, timesheet='default')

@command(aliases=('ls',))
def list(db, simple=False):
    """Show the available timesheets

    Usage: t (list | ls) [-s, --simple]

    Options:
      -s, --simple  Only display the names of the available timesheets.
    """
    if simple:
        db.execute(
        '''
        select
            distinct sheet
        from
            entry
        order by
            sheet asc;
        ''')
        print('\n'.join(r[0] for r in db.fetchall()))
        return

    table = [[' Timesheet', 'Running', 'Today', 'Total time']]
    db.execute('''
    select
        e1.sheet as name,
        e1.sheet = meta.value as is_current,
        ifnull((select
            strftime('%s', 'now') - e2.start_time
         from
            entry e2
         where
            e1.sheet = e2.sheet and e2.end_time is null), 0
        ) as active,
        (select
            ifnull(sum(ifnull(e3.end_time, strftime('%s', 'now')) -
                       e3.start_time), 0)
            from
                entry e3
            where
                e1.sheet = e3.sheet and
                e3.start_time > strftime('%s', date('now'))
        ) as today,
        ifnull(sum(ifnull(e1.end_time, strftime('%s', 'now')) -
                   e1.start_time), 0) as total
    from
        entry e1, meta
    where
        meta.key = 'current_sheet'
    group by e1.sheet
    order by e1.sheet asc;
    ''')
    sheets = db.fetchall()
    if len(sheets) == 0:
        print('(no sheets)')
        return
    for (name, is_current, active, today, total) in sheets:
        cur_name = '%s%s' % ('*' if is_current else ' ', name)
        active = str(timedelta(seconds=active)) if active != 0 \
                                                else '--'
        today = str(timedelta(seconds=today))
        total_time = str(timedelta(seconds=total))
        table.append([cur_name, active, today, total_time])
    cmdutil.pprint_table(table)

@command()
def switch(db, timesheet, verbose=False):
    """Switch to a new timesheet

    Usage: t switch [options] <timesheet>

    Switch to a new timesheet. This causes all future operation (except switch)
    to operate on that timesheet. The default timesheet is called
    "default".

    Options:
      -v, --verbose  Print the name and number of entries of the timesheet.
    """
    # optimization: check that the given timesheet is not already
    # current. updates are far slower than selects.
    if dbutil.get_current_sheet(db) != timesheet:
        db.execute('''
        update
            meta
        set
            value = ?
        where
            key = 'current_sheet'
        ''', (timesheet,))

    if verbose:
        entry_count = dbutil.get_entry_count(db, timesheet)
        if entry_count == 0:
            print('switched to empty timesheet "%s"' % timesheet)
        else:
            print(ngettext(
                'switched to timesheet "%s" (1 entry)' % timesheet,
                'switched to timesheet "%s" (%s entries)' % (
                    timesheet, entry_count), entry_count))

@command(aliases=('stop',))
def out(db, at=None, verbose=False):
    """Stop the timer for the current timesheet

    Usage: t (out | stop) [options]

    Must be called after in.

    Options:
      -v, --verbose  Show the duration of the period that the out command ends.
      -a <time>, --at=<time>
                     Set time of clock-out.
    """
    clock_out(db, at, verbose)

def clock_out(db, at=None, verbose=False, timestamp=None):
    if not timestamp:
        timestamp = cmdutil.parse_date_time_or_now(at)
    active = dbutil.get_current_start_time(db)
    if active is None:
        raise SystemExit('error: timesheet not active')
    active_id, start_time = active
    active_time = timestamp - start_time
    if verbose:
        print(timedelta(seconds=active_time))
    if active_time < 0:
        raise SystemExit("Error: Negative active time")
    db.execute('''
    update
        entry
    set
        end_time = ?
    where
        entry.id = ?
    ''', (timestamp, active_id))

@command(aliases=('write',))
def alter(db, description):
    """Alter the description of the active period

    Usage: t (alter | write) <description>...

    Inserts a note associated with the currently active period in the
    timesheet. For example, ``t alter Documenting timebook.``
    """
    active = dbutil.get_current_active_info(db)
    if active is None:
        raise SystemExit('error: timesheet not active')
    entry_id = active[0]
    db.execute('''
    update
        entry
    set
        description = ?
    where
        entry.id = ?
    ''', (' '.join(description), entry_id))

@command(aliases=('active',))
def running(db):
    """Show all running timesheets

    Usage: t (running | active)

    Print all active sheets and any messages associated with them.
    """
    db.execute('''
    select
        entry.sheet,
        ifnull(entry.description, '--')
    from
        entry
    where
        entry.end_time is null
    order by
        entry.sheet asc;
    ''')
    cmdutil.pprint_table([('Timesheet', 'Description')] + db.fetchall())

@command(aliases=('info',))
def now(db, timesheet=None, simple=False, notes=False):
    """Show the status of the current timesheet

    Usage: t (now | info) [options] [<timesheet>]

    Print the current sheet, whether it's active, and if so, how long it
    has been active and what notes are associated with the current
    period.

    If a specific timesheet is given, display the same information for that
    timesheet instead.

    Options:
      -s, --simple  Only display the name of the current timesheet.
      -n, --notes   Only display the notes associated with the current period.
    """
    if simple:
        print(dbutil.get_current_sheet(db))
        return

    if timesheet:
        sheet = cmdutil.complete(dbutil.get_sheet_names(db), timesheet,
                                 'timesheet')
    else:
        sheet = dbutil.get_current_sheet(db)

    entry_count = dbutil.get_entry_count(db, sheet)
    if entry_count == 0:
        raise SystemExit('%(prog)s: error: sheet is empty. For program \
usage, see "%(prog)s --help".' % {'prog': os.path.basename(sys.argv[0])})

    running = dbutil.get_active_info(db, sheet)
    _notes = ''
    if running is None:
        active = 'not active'
    else:
        duration = str(timedelta(seconds=running[0]))
        if running[1]:
            _notes = running[1].rstrip('.')
            active = '%s (%s)' % (duration, _notes)
        else:
            active = duration
    if notes:
        print(_notes)
    else:
        print('%s: %s' % (sheet, active))

@command(aliases=('export', 'format', 'show'))
def display(db, timesheet=None, format='plain', start=None, end=None):
    """Display a timesheet, by default the current one

    Usage: t (display | export | format | show) [options] [<timesheet>]

    Display the data from a timesheet in the range of dates specified, either
    in the normal timebook fashion (using --format=plain) or as
    comma-separated value format spreadsheet (using --format=csv), which
    ignores the final entry if active.

    If a specific timesheet is given, display the same information for that
    timesheet instead.

    Options:
      -s <date>, --start <date>
                        Show only entries starting after 00:00 on this date.
                        The date should be of the format YYYY-MM-DD.
      -e <date>, --end <date>
                        Show only entries ending before 00:00 on this date.
                        The date should be of the format YYYY-MM-DD.
      -f (plain|csv), --format=(plain|csv)
                        Select whether to output in the normal timebook style
                        (--format=plain) or CSV (--format=csv) [default: plain].

    """
    # grab correct sheet
    if timesheet:
        sheet = cmdutil.complete(dbutil.get_sheet_names(db), timesheet,
                                 'timesheet')
    else:
        sheet = dbutil.get_current_sheet(db)

    #calculate "where"
    where = ''
    if start is not None:
        start_date = cmdutil.parse_date_time(start)
        where += ' and start_time >= %s' % start_date
    if end is not None:
        end_date = cmdutil.parse_date_time(end)
        where += ' and end_time <= %s' % end_date
    if format == 'plain':
        format_timebook(db, sheet, where)
    elif format == 'csv':
        format_csv(db, sheet, where)
    else:
        raise SystemExit('Invalid format: %s' % format)

def format_csv(db, sheet, where):
    import csv

    writer = csv.writer(sys.stdout)
    writer.writerow(('Start', 'End', 'Length', 'Description'))
    db.execute('''
    select
       start_time,
       end_time,
       ifnull(end_time, strftime('%%s', 'now')) -
           start_time,
       description
    from
       entry
    where
       sheet = ? and
       end_time is not null%s
    ''' % where, (sheet,))
    format = lambda t: datetime.fromtimestamp(t).strftime(
        '%m/%d/%Y %H:%M:%S')
    rows = db.fetchall()
    writer.writerows([(
        format(row[0]), format(row[1]), row[2], row[3]) for row in rows])
    total_formula = '=SUM(C2:C%d)/3600' % (len(rows) + 1)
    writer.writerow(('Total', '', total_formula, ''))

def format_timebook(db, sheet, where):
    db.execute('''
    select count(*) > 0 from entry where sheet = ?%s
    ''' % where, (sheet,))
    if not db.fetchone()[0]:
        print('(empty)')
        return

    displ_time = lambda t: time.strftime('%H:%M:%S', time.localtime(t))
    displ_date = lambda t: time.strftime('%b %d, %Y',
                                         time.localtime(t))
    displ_total = lambda t: \
            cmdutil.timedelta_hms_display(timedelta(seconds=t))

    last_day = None
    table = [['Day', 'Start      End', 'Duration', 'Notes']]
    db.execute('''
    select
        date(e.start_time, 'unixepoch', 'localtime') as day,
        ifnull(sum(ifnull(e.end_time, strftime('%%s', 'now')) -
                   e.start_time), 0) as day_total
    from
        entry e
    where
        e.sheet = ?%s
    group by
        day
    order by
        day asc;
    ''' % where, (sheet,))
    days = db.fetchall()
    days_iter = iter(days)
    db.execute('''
    select
        date(e.start_time, 'unixepoch', 'localtime') as day,
        e.start_time as start,
        e.end_time as end,
        ifnull(e.end_time, strftime('%%s', 'now')) - e.start_time as
            duration,
        ifnull(e.description, '') as description
    from
        entry e
    where
        e.sheet = ?%s
    order by
        e.start_time asc;
    ''' % where, (sheet,))
    entries = db.fetchall()
    for i, (day, start, end, duration, description) in \
            enumerate(entries):
        date = displ_date(start)
        diff = displ_total(duration)
        if end is None:
            trange = '%s -' % displ_time(start)
        else:
            trange = '%s - %s' % (displ_time(start), displ_time(end))
        if last_day == day:
            # If this row doesn't represent the first entry of the
            # day, don't display anything in the day column.
            table.append(['', trange, diff, description])
        else:
            if last_day is not None:
                # Use day_total set (below) from the previous
                # iteration. This is skipped the first iteration,
                # since last_day is None.
                table.append(['', '', displ_total(day_total), ''])
            cur_day, day_total = next(days_iter)
            assert day == cur_day
            table.append([date, trange, diff, description])
            last_day = day

    db.execute('''
    select
        ifnull(sum(ifnull(e.end_time, strftime('%%s', 'now')) -
                   e.start_time), 0) as total
    from
        entry e
    where
        e.sheet = ?%s;
    ''' % where, (sheet,))
    total = displ_total(db.fetchone()[0])
    table += [['', '', displ_total(day_total), ''],
              ['Total', '', total, '']]
    cmdutil.pprint_table(table, footer_row=True)
