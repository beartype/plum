class A(object):
    def __init__(self, x):
        self.x = x


class Wrap(A):
    # def __init__(self, x):#*args, **kw_args):
    #     A.__init__(self, x)#*args, **kw_args)

    def __new__(cls, x):
        return A.__new__(cls)

print(A(1).x)
print(Wrap(1).x)