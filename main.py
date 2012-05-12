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
        self.sec_parent = set()
        self.sec_child = set()
        pass
    def is_shrinkable(self):
        return False
    def get_dot_name(self):
        return None
    def get_dot_attrib(self):
        return '[]'
    def get_dot_node_name_attrib(self):
        return '{0} {1};'.format(self.get_dot_name(), self.get_dot_attrib())
    
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
    
    def set_sec_parent(self, par):
        if not par in self.sec_parent:
            self.sec_parent.add(par)
            par.set_sec_child(self)
            pass
        pass
    def set_sec_child(self, chi):
        if not chi in self.sec_child:
            self.sec_child.add(chi)
            chi.set_sec_parent(self)
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
    def get_dot_label(self):
        return r'{0}\n{1}'.format(self.event.line, self.event.time)
    def get_dot_attrib(self):
        return '[label="{0}"]'.format(self.get_dot_label())
    
    pass

class InvisibleNode(Node):
    def __init__(self, name):
        self.name = name
        super(InvisibleNode, self).__init__()
        pass
    def get_dot_name(self):
        return '"{0}"'.format(self.name)
    def get_dot_attrib(self):
        return '[style=invisible,overlap=false,label=""]'
    
    def set_parent(self, par):
        if self.parent != par:
            self.parent = par
            pass
        pass
    def set_child(self, chi):
        if self.child != chi:
            self.child = chi
            pass
        pass

class Graph():
    def __init__(self, events):
        self.raw_events = events
        
        self.events = list()
        self.invis_nodes = list()
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
        for _,v in self.raw_events.iteritems():
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
            self.events.append(ev)
            
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
        
        # set invisible nodes to fix time ranking
        for tma, tmb in pair_iter(sorted(self.times)):
            elista = self.time_events_th_uniq[tma]
            elistb = self.time_events_th_uniq[tmb]
            have_threads_a = {e.thread for e in elista}
            have_threads_b = {e.thread for e in elistb}
            lack_threads_b = self.threads - have_threads_b
            
            for th in lack_threads_b:
                if th in have_threads_a:
                    e = (e for e in elista if e.thread == th).next()
                    while e.child and e.child.time == e.time: 
                        e = e.child
                        pass
                    if e.child:
                        ie = InvisibleNode(str(th) + str(tmb) + 'invis')
                        ie.thread = th
                        ie.time = tmb
                        e.set_sec_child(ie)
                        e.child.set_sec_parent(ie)
                        ie.set_parent(e)
                        ie.set_child(e.child)
                        self.time_events_th_uniq[tmb].append(ie)
                        
                        self.invis_nodes.append(ie)
                        pass
                    pass
                pass # for th in lac_th
            pass 
        
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
        
        # invisible nodes
        for ie in self.invis_nodes:
            fd.write('{0} -> {1}[style=invisible,dir=none];\n'.format(ie.parent.get_dot_name(), ie.get_dot_name()))
            fd.write('{0} -> {1}[style=invisible,dir=none];\n'.format(ie.get_dot_name(), ie.child.get_dot_name()))
        
        # nodes attributes
        def write_attribs(lis):
            for ev in lis:
                fd.write(ev.get_dot_node_name_attrib())
                fd.write('\n')
                pass
            fd.write('\n')
            pass
        write_attribs(self.events)
        write_attribs(self.invis_nodes)
        
        
        
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