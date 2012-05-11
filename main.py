#!/usr/bin/env python2

__author__ = 'pashkoff'

import logging
logging.basicConfig(level=logging.DEBUG)
lg = logging.getLogger(__name__)

import re
from datetime import datetime, timedelta

from pygraph.classes.graph import graph
from pygraph.classes.digraph import digraph
from pygraph.readwrite.dot import write

import pytz
ua_tz = pytz.timezone('Europe/Kiev')
utc_tz = pytz.utc

from cStringIO import StringIO
from contextlib import closing

import xdot
import gtk

def funcname():
    import sys
    return sys._getframe(1).f_code.co_name

class Event():
    def __init__(self, level = '', time = '', line = '', thread = '', proc = '', source = '', source_line = '', msg = ''):

        # todo
        time = time.replace(year = 2000, month = 1, day = 1)

        self.level = level
        self.time = time
        self.line = line
        self.thread = thread
        self.proc = proc
        self.source = source
        self.source_line = source_line
        self.msg = msg

        pass

    def __str__(self):
        return str((self.level, self.time, self.line, self.thread, self.proc, self.source, self.source_line, self.msg))
    pass

class ParseError(BaseException):
    pass

class SimpleEventParser():
    def __init__(self):
        self.r = re.compile(r'.*?\[(?P<time>[\d:.]*)\]\{TID (?P<thread>\d*)\}(?P<msg>.*)')

    def parse_line(self, line):

#        if not (line[0] == '[' or line[0] == '{'):
#            raise ParseError

        m = self.r.match(line)

        if not m:
            raise ParseError

        g = m.groupdict()
        t = datetime.strptime(g['time']+'000', r'%H:%M:%S:%f')
##        lg.debug(t)
#        t = ua_tz.localize(t, is_dst=True)
##        lg.debug(t)
#        t = utc_tz.normalize(t.astimezone(utc_tz))
##        lg.info(t)
        t = t - timedelta(hours = 3)
        g['time'] = t

        return Event(**g)

    pass

class Log4CplusEventParser():
    def __init__(self):
        self.r = re.compile(r'(?P<level>\w+) *\[(?P<time>[\w :]+)\]\{ID (?P<thread>\d+):(?P<proc>\d+)\} (?P<source>.+?):(?P<source_line>\d+).+- (?P<msg>.*)')

    def parse_line(self, line):
        m = self.r.match(line)

        if not m:
            raise ParseError

        g = m.groupdict()
        g['time'] = datetime.strptime(g['time']+'000', r'%d %m %Y %H:%M:%S:%f')

        return Event(**g)
        pass

event_parsers = (SimpleEventParser(), Log4CplusEventParser())
EVENTS = dict()
THREADS = dict()
PARENTS = dict()

def parse(lines):
    lg = logging.getLogger(funcname())
    lg.setLevel(logging.ERROR)

    i = 0
    skipped = 0
    for line in lines:
        i += 1
        line = line.rstrip()

        lg.info(line)
        ev = None
        for p in event_parsers:
            try:
                ev = p.parse_line(line)
                break
            except ParseError:
                pass

            pass

        if not ev:
            lg.warn('Unable to parse string')
            lg.info(line)
            skipped += 1
        else:
            ev.line = i
            EVENTS[i] = ev
            pass

        lg.info(ev)

        if i >= 200:
            break

        pass
    lg.setLevel(logging.INFO)
    lg.info('skipped lines = %d' % skipped)
    pass

def make_graph():

    for k, v in EVENTS.iteritems():
        t = v.thread
        if not t in THREADS:
            THREADS[t] = list()
        THREADS[t].append(v.line)
        pass
#    print THREADS.keys\
    pass

def make_mydot(fd):
    lg.info(funcname())

    tev = dict()
    times = set()
    for k,v in EVENTS.iteritems():
        lg.debug(v.time)
        times.add(v.time)
        if not v.time in tev:
            tev[v.time] = list()
        tev[v.time].append(v.line)
        pass

    lg.info('times and tev')

    times = sorted(times)
    timesd = dict()
    for t in times:
        timesd[t] = t.strftime('"%H:%M:%S:%f"')

    lg.info('timesd')

    for k,v in THREADS.iteritems():
        vit = iter(v)
        b = vit.next()
        PARENTS[b] = None
        for e in vit:
            PARENTS[e] = b
            b = e
            pass
        pass

    lg.info('PARENTS')

    fd.write('digraph {\n')

    fd.write('{\n')
    fd.write('node [shape=plaintext];\n')
    fd.write('past')
    for t in iter(times):
        fd.write(' -> {0}'.format(timesd[t]))
        pass
    fd.write(';\n')
    fd.write('}\n\n')

    lg.info('done timeline')

    fd.write('{\n')
    fd.write('rank = same; "past"; ')
    for t in THREADS.keys():
        fd.write('"{0}"; '.format(t))
        pass
    fd.write('\n}\n\n')

    lg.info('done THREADS')

    fd.write('node [shape=box];\n')
    for t in times:
        fd.write('{{ rank = same; {0}; '.format(timesd[t]))
        for e in tev[t]:
            fd.write('"{0}"; '.format(e))
            break
            pass
        fd.write('}\n')
        pass

    lg.info('done vertices')

    for k,v in tev.iteritems():
        fd.write('subgraph { ')
        for vv in v:
            fd.write('"{0}"; '.format(vv))
            pass
        fd.write('}\n')
        pass
    lg.info('done subgraphs')

    fd.write('\n\n')
    for k,v in EVENTS.iteritems():
        p = PARENTS[v.line]
        if p:
            fd.write('"{0}" -> "{1}";\n'.format(p, v.line))
        else:
            fd.write('"{0}" -> "{1}";\n'.format(v.thread, v.line))
        pass

    lg.info('done edges')

    fd.write('}')

    pass


def make_pygraph():
    gr = digraph()
    gr.add_nodes(EVENTS.keys())

    lg.info('add nodes done')

    lg.info('THREADS fill done')

    for k, v in THREADS.iteritems():
        vit = iter(v)
        b = vit.next()
        for e in vit:
            gr.add_edge((b, e))
            b = e
            pass
        pass

    lg.info('add_edge done')

    dot = write(gr)
    lg.info('dot write done')

    fd = open('gv.dot', 'wb')
    fd.write(dot)
    fd.close()
    lg.info('dot file write done')

    pass


def main():
    fd = open('log.txt', 'r')
    parse(fd)
    fd.close()

#    lg.info(EVENTS)
    lg.info(len(EVENTS))

    make_graph()
#    make_pygraph()

#    with open('my.dot', 'wb') as fd:
    with closing(StringIO()) as fd:
        make_mydot(fd)
        win = xdot.DotWindow()
        win.set_dotcode(fd.getvalue())
        win.connect('destroy', gtk.main_quit)
        gtk.main()

    pass

if __name__ == "__main__":
    main()