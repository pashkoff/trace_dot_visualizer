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

import re

from cStringIO import StringIO
from contextlib import closing

import xdot
import gtk

EVENTS = None
THREADS = dict()
PARENTS = dict()

from file_parser import parse

class DotObject(object):
    def __init__(self):
        self.attribs = dict()
        pass
    def get_dot_attrib(self):
        a = self.attribs.items()
        b = map(lambda x: '{0}="{1}"'.format(x[0], x[1]() if hasattr(x[1], '__call__') else x[1]), a)
        return '[{0}]'.format(','.join(b))

class Node(DotObject):
    def __init__(self):
        super(Node, self).__init__()
        self.parent = None
        self.child = None
        self.sec_parent = set()
        self.sec_child = set()
        self.links = set()
        self.consumed_nodes = list()
        self.consumed = False
        pass
    
    def is_shrinkable(self):
        return False
    def get_dot_name(self):
        return None
    def get_dot_node_name_attrib(self):
        return '{0} {1};'.format(self.get_dot_name(), self.get_dot_attrib())
    
    def set_parent(self, par):
        if self.parent != par:
            self.parent = par
            if par: par.set_child(self)
            pass
        pass
    def set_child(self, chi):
        if self.child != chi:
            self.child = chi
            if chi: chi.set_parent(self)
            pass
        pass
    
    def set_sec_parent(self, par):
        if not par in self.sec_parent:
            self.sec_parent.add(par)
            if par: par.set_sec_child(self)
            pass
        pass
    def set_sec_child(self, chi):
        if not chi in self.sec_child:
            self.sec_child.add(chi)
            if chi: chi.set_sec_parent(self)
            pass
        pass
    
    def consume_child(self):
        self.consumed_nodes.append(self.child)
        if self.child: self.child.consumed = True
        self.set_child(self.child.child)
        pass
    
    pass

class ThreadNode(Node):
    def __init__(self, thread, proc):
        self.thread = '{0}:{1}'.format(thread, proc)
        self.ht = int(thread)
        self.hh = int(proc)
        self.h = self.ht * 1000000 + self.hh
        super(ThreadNode, self).__init__()
        pass
    def __hash__(self):
        return self.h
    def __eq__(self, other):
        return self.ht == other.ht and self.hh == other.hh
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
        self.attribs['label'] = self.get_dot_label
        pass
    
    def get_dot_name(self):
        return '"{0}"'.format(self.event.line)
    
    def get_dot_label(self):
        lab = r'{0}-{1} - {2}:{3}\n{4}'.format(self.event.line, self.event.level, self.event.source, self.event.source_line, self.event.msg)
        clab = r'\n'.join(map(lambda x: x.get_dot_label(), self.consumed_nodes))
        return lab + r'\n' + clab
            
    
    pass

class InvisibleNode(Node):
    def __init__(self, name):
        self.name = name
        super(InvisibleNode, self).__init__()
        self.attribs.update({'style':'invisible', 'shape':'point', 'overlap':'false', 'label':''})
        pass
    def get_dot_name(self):
        return '"{0}"'.format(self.name)
#    def get_dot_attrib(self):
#        return '[style=invisible,shape=point,overlap=false,label=""]'
    
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

class Link(DotObject):
    def __init__(self, frm, to):
        super(Link, self).__init__()
        self.frm = frm
        self.to = to
        
    def get_dot_code(self):
        return '{0} -> {1} {2}'.format(self.frm.get_dot_name(), self.to.get_dot_name(), self.get_dot_attrib())

class InvisibleLink(Link):
    def __init__(self, frm, to):
        super(InvisibleLink, self).__init__(frm, to)
        self.attribs.update({'style':'invisible', 'dir':'none'})

class IpcLink(Link):
    def __init__(self, frm, to, is_req):
        super(IpcLink, self).__init__(frm, to)
        self.is_req = is_req
        color = 'red' if is_req else 'blue'
        self.attribs.update({'color':color, 'constraint':'false'})
        
        frm.attribs.update({'color':color})
        to.attribs.update({'color':color})
        
        frm.links.add(self)
        to.links.add(self)
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
        
        self.ipc_links = list()
        
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
            
            th = ThreadNode(v.thread, v.proc)
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
        
        self.find_hor_links()
        self.shrink_graph()
        
        pass
    
    def find_hor_links(self):
        class ParseError(BaseException):pass
        
        ipc_req_sent_re  = re.compile(r"Ipc request sent addr='(?P<addr>.*)' MsgId=(?P<msgid>\d*) size=(?P<size>\d*)")
        ipc_resp_sent_re = re.compile(r"Ipc response sent addr='(?P<addr>.*)' MsgId=(?P<msgid>\d*) size=(?P<size>\d*)")
        ipc_req_got_re   = re.compile(r"Ipc got request addr='(?P<addr>.*)' MsgId=(?P<msgid>\d*) size=(?P<size>\d*)")
        ipc_resp_got_re  = re.compile(r"Ipc request done addr='(?P<addr>.*)' MsgId=(?P<msgid>\d*) size=(?P<size>\d*)")
        
        def ipc_req_sent(ev):
            if ev.event.level == 'INFO' and ev.event.source.find('CIpc.cpp') != -1:
                m = ipc_req_sent_re.match(ev.event.msg)
                if not m:
                    raise ParseError
                    
                return m.groupdict()
            else:
                raise ParseError
            pass
            
        def ipc_resp_sent(ev):
            if ev.event.level == 'INFO' and ev.event.source.find('CIpc.cpp') != -1:
                m = ipc_resp_sent_re.match(ev.event.msg)
                if not m:
                    raise ParseError
                    
                return m.groupdict()
            else:
                raise ParseError
            pass
            
        def ipc_req_got(ev, constr):
            if ev.event.level == 'INFO' and ev.event.source.find('CIpc.cpp') != -1:
                m = ipc_req_got_re.match(ev.event.msg)
                if not m:
                    raise ParseError
                d = m.groupdict()
                for k,v in d.iteritems():
                    if k in constr and constr[k] != v:
                        raise ParseError
                    pass
                                   
                return 
            else:
                raise ParseError
            pass
        
        def ipc_resp_got(ev, constr):
            if ev.event.level == 'INFO' and ev.event.source.find('CIpc.cpp') != -1:
                m = ipc_resp_got_re.match(ev.event.msg)
                if not m:
                    raise ParseError
                d = m.groupdict()
                for k,v in d.iteritems():
                    if k in constr and constr[k] != v:
                        raise ParseError
                    pass
                                   
                return 
            else:
                raise ParseError
            pass
        
        # ipc search
        
        def find_resp_target(req_frm, req_to, req, resp_from, resp):
            possible_events = filter(lambda x: x.event.time >= resp_from.event.time, self.thread_events[req_frm.thread])
            for pev in possible_events:
                try:
                    ipc_resp_got(pev, resp)
                    self.ipc_links.append(IpcLink(resp_from, pev, False))
                    break
                except ParseError:
                    pass
                pass
            pass
        
        def find_resp(ev_from, ev_to, req):
            possible_events = filter(lambda x: x.event.time >= ev_to.event.time, self.thread_events[ev_to.thread])
            for pev in possible_events:
                try:
                    resp = ipc_resp_sent(pev)
                    find_resp_target(ev_from, ev_to, req, pev, resp)
                    break
                except ParseError:
                    pass
                pass                        
            pass
        
        def find_req_target(ev, req):
            possible_events = filter(lambda x: x.event.time >= ev.event.time and x.thread != ev.thread, self.events)
            for pev in possible_events:
                try:
                    ipc_req_got(pev, req)
                    self.ipc_links.append(IpcLink(ev, pev, True))
                    find_resp(ev, pev, req)
                    break
                except ParseError:
                    pass
                pass
            pass
                
        for ev in self.events:
            try:
                req = ipc_req_sent(ev)
                find_req_target(ev, req)
            except ParseError:
                pass
            pass
        
        pass
    
    def shrink_graph(self):
        def nonshrinkable(ev):
            if len(ev.links) > 0:
                return True
            if ev in self.time_events_th_uniq[ev.time]:
                return True
            if ev.consumed:
                return False
            return False
        
        def shrink(ev):
            while ev.child and not nonshrinkable(ev.child):
                ev.consume_child()
                pass
            return ev
        
        self.events[:] = [shrink(ev) for ev in self.events if nonshrinkable(ev)]
        
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
            fd.write(InvisibleLink(ie.parent, ie).get_dot_code()); fd.write('\n')
            fd.write(InvisibleLink(ie, ie.child).get_dot_code()); fd.write('\n')
        fd.write('\n')
        
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
        
        # ipc links
        for il in self.ipc_links:
            fd.write(il.get_dot_code()); fd.write('\n')
        
        
        
        # footer
        fd.write('}')
            

def main():
    
    with open('last.log', 'r') as fd:
        global EVENTS
        EVENTS = parse(fd)
        
    
    g = Graph(EVENTS)
    g.make_graph()
    
#    make_graph()
#
##    with open('my.dot', 'wb') as fd:
##        make_mydot(fd)
#        
    with closing(StringIO()) as fd:
        g.make_dot(fd)
        with open('test.dot', 'wb') as ffd:
            ffd.write(fd.getvalue())
        win = xdot.DotWindow()
        win.set_dotcode(fd.getvalue())
        win.connect('destroy', gtk.main_quit)
        gtk.main()

    pass

if __name__ == "__main__":
    main()