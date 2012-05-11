#!/usr/bin/env python2
from gtk import FALSE

__author__ = 'pashkoff'

import logging
logging.basicConfig(level=logging.DEBUG)
lg = logging.getLogger(__name__)
from util import funcname, pair_iter, unique_everseen


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

class Node(object):
    def __init__(self):
        self.parent = None
        self.child = None
        pass
    def is_shrinkable(self):
        return False
    def get_dot_name(self):
        return None
    
    def set_parent(self, par):
        if self.parent != par:
            self.parent = par
            par.set_child(self)
            pass
        pass
    def set_child(self, chi):
        if self.child != chi:
            self.child = chi
            chi.set_parent(self)
            pass
        pass
    

class ThreadNode(Node):
    def __init__(self, thread):
        self.thread = thread
        self.h = int(thread)
        super(ThreadNode, self).__init__()
        pass
    def __hash__(self):
        return self.h
    def __eq__(self, other):
        return self.h == other.h
    def __str__(self):
        return str(self.thread)
    def get_dot_name(self):
        return '"{0}"'.format(self.thread)
    pass

class TimeNode(Node):
    def __init__(self, time):
        self.time = time
        self.is_past = time == 'past'
        super(TimeNode, self).__init__()
        pass
    def __hash__(self):
        return self.time.__hash__()
    def __cmp__(self, other):
        if other.is_past:
            return 0 if self.is_past else 1
        elif self.is_past:
            return 0 if other.is_past else -1
        else:
            if self.time > other.time:   return  1
            elif other.time > self.time: return -1
            else: return 0
    def __str__(self):
        return str(self.time)
    def get_dot_name(self):
        if self.is_past:
            return '"past"'
        else:
            return self.time.strftime('"%H:%M:%S:%f"')
    pass

class EventNode(Node):
    def __init__(self, time, thread, event):
        self.time = time
        self.thread = thread
        self.event = event
        super(EventNode, self).__init__()
        pass
    
    def get_dot_name(self):
        return '"{0}"'.format(self.event.line)
    
    pass

class Graph():
    def __init__(self, events):
        self.events = events
        
        self.times = set()
        self.time_events = dict()
        self.time_events_th_uniq = dict()
        self.threads = set()
        self.thread_events = dict()
        
        past = TimeNode('past')
        self.times.add(past)
        self.time_events[past] = list()
        
    def make_graph(self):
        lg.info(funcname())
        
        # parse all events and fill base structures
        for _,v in self.events.iteritems():
            tm = TimeNode(v.time)
            if not tm in self.times:
                self.times.add(tm)
                self.time_events[tm] = list()
                pass
            
            th = ThreadNode(v.thread)
            if not th in self.threads:
                self.threads.add(th)
                self.thread_events[th] = list()
                pass
            
            ev = EventNode(tm, th, v)
            self.thread_events[th].append(ev)
            self.time_events[tm].append(ev)
            pass
        
        # build the linked list of event and thread nodes
        for th, elist in self.thread_events.iteritems():
            elist[0].set_parent(th)
            elist[0].first = True
            
            for a,b in pair_iter(elist):
                b.set_parent(a)
                pass
            pass
        
        # build time events list unique by thread
        for tm, elist in self.time_events.iteritems():
            self.time_events_th_uniq[tm] = list(unique_everseen(elist, lambda x: x.thread))
        
        pass
    
    def make_dot(self, fd):
        lg.info(funcname())

        # header        
        fd.write('digraph {\n')
        
        # timeline
        fd.write('{\n')
        fd.write('node [shape=plaintext];\n')
        fd.write(' -> '.join(map(lambda x: x.get_dot_name(), sorted(self.times))))
        fd.write(';\n')
        fd.write('}\n\n')
        
        # threads list
        fd.write('{\n')
        fd.write('rank = same; "past"; ')
        fd.write('; '.join(map(lambda x: x.get_dot_name(), self.threads)))
        fd.write('\n}\n\n')
        
        # time ranking
        fd.write('node [shape=box];\n')
        for tm, elist in self.time_events_th_uniq.iteritems():
            fd.write('{{ rank = same; {0}; '.format(tm.get_dot_name()))
            fd.write('; '.join(map(lambda x: x.get_dot_name(), elist)))
            fd.write('}\n')
        fd.write('\n')
        
        # events
        def node_list(node): 
            while node:
                yield node
                node = node.child
            raise StopIteration
        for th in self.threads:
            for a, b in pair_iter(node_list(th)):
                fd.write('{0} -> {1};\n'.format(a.get_dot_name(), b.get_dot_name()))
                pass
            pass
        
        
        # footer
        fd.write('}')
            

def main():
    
    with open('log.txt', 'r') as fd:
        global EVENTS
        EVENTS = parse(fd)
        
    
    g = Graph(EVENTS)
    g.make_graph()
    
    with open('test.dot', 'wb') as fd:
        g.make_dot(fd)

#    make_graph()
#
##    with open('my.dot', 'wb') as fd:
##        make_mydot(fd)
#        
    with closing(StringIO()) as fd:
        g.make_dot(fd)
        win = xdot.DotWindow()
        win.set_dotcode(fd.getvalue())
        win.connect('destroy', gtk.main_quit)
        gtk.main()

    pass

if __name__ == "__main__":
    main()