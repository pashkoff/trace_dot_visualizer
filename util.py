'''
Created on May 11, 2012

@author: pashkoff
'''

def funcname():
    import sys
    return sys._getframe(1).f_code.co_name