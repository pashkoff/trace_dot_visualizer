'''
Created on May 11, 2012

@author: pashkoff
'''

def funcname():
    """Retuns name of function form which was called
    
    Example
    >>> def fancy_func():
    ...     print funcname()
    >>> fancy_func()
    fancy_func
    
    """
    import sys
    return sys._getframe(1).f_code.co_name


def pair_iter(iterable):
    """Iteration over pairs of elements.
    
    Example 1
    >>> l = [0, 1, 2, 3]
    >>> for a, b in pair_iter(l):
    ...     print a, b 
    0 1
    1 2
    2 3
    
    Example 2
    >>> l = [0]
    >>> for a, b in pair_iter(l):
    ...     print a, b 

    It will get nothing
    
    """
    i = iter(iterable)
    a = i.next()
    
    for b in i:
        yield (a, b)
        a = b
        pass
    raise StopIteration
    
def unique_everseen(iterable, key=None):
    "List unique elements, preserving order. Remember all elements ever seen."
    # unique_everseen('AAAABBBCCDAABBB') --> A B C D
    # unique_everseen('ABBCcAD', str.lower) --> A B C D
    from itertools import ifilterfalse
    seen = set()
    seen_add = seen.add
    if key is None:
        for element in ifilterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen_add(k)
                yield element

if __name__ == "__main__":
    import doctest
    doctest.testmod()