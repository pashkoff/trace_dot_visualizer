#!/usr/bin/env python2

__author__ = 'pashkoff'

import logging
logging.basicConfig(level=logging.DEBUG)
lg = logging.getLogger(__name__)
from util import funcname


from pygraph.classes.graph import graph
from pygraph.classes.digraph import digraph
from pygraph.readwrite.dot import write



from cStringIO import StringIO
from contextlib import closing

import xdot
import gtk

EVENTS = None
THREADS = dict()
PARENTS = dict()

from file_parser import parse

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

def main():
    
    with open('log.txt', 'r') as fd:
        global EVENTS
        EVENTS = parse(fd)

    make_graph()

#    with open('my.dot', 'wb') as fd:
#        make_mydot(fd)
        
    with closing(StringIO()) as fd:
        make_mydot(fd)
        win = xdot.DotWindow()
        win.set_dotcode(fd.getvalue())
        win.connect('destroy', gtk.main_quit)
        gtk.main()

    pass

if __name__ == "__main__":
    main()