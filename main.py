__author__ = 'pashkoff'

import logging
logging.basicConfig(level=logging.DEBUG)
lg = logging.getLogger(__name__)

import itertools
import re
from datetime import datetime



class Event():
    def __init__(self, level = '', time = '', line = '', thread = '', proc = '', source = '', source_line = '', msg = ''):
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
        self.r = re.compile(r'\[(?P<time>[\d:.]*)\]\{TID (?P<thread>\d*)\}(?P<msg>.*)')

    def parse_line(self, line):

        if not (line[0] == '[' or line[0] == '{'):
            raise ParseError

        m = self.r.match(line)

        if not m:
            raise ParseError

        g = m.groupdict()
        g['time'] = datetime.strptime(g['time']+'000', r'%H:%M:%S:%f')

        return Event(**g)

    pass

class Log4CplusEventParser():
    def __init__(self):
        self.r = re.compile(r'(?P<level>\w+) \[(?P<time>[\w :]+)\]\{ID (?P<thread>\d+):(?P<proc>\d+)\} (?P<source>.+?):(?P<source_line>\d+).+- (?P<msg>.*)')

    def parse_line(self, line):
        m = self.r.match(line)

        if not m:
            raise ParseError

        g = m.groupdict()
        g['time'] = datetime.strptime(g['time']+'000', r'%d %m %Y %H:%M:%S:%f')

        return Event(**g)
        pass

event_parsers = (SimpleEventParser(), Log4CplusEventParser())


def parse(lines):
    i = 0
    for line in lines:
        i += 1

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
        else:
            ev.line = i
            pass

        lg.info(ev)

        pass
    pass


def main():
    fd = open('log.txt', 'r')
    parse(fd)
    pass

if __name__ == "__main__":
    main()