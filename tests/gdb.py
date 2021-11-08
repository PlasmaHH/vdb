
from enum import Enum

TYPE_CODE_PTR = None
TYPE_CODE_ARRAY = None
TYPE_CODE_PTR = None
TYPE_CODE_ARRAY = None
TYPE_CODE_STRUCT = None
TYPE_CODE_UNION = None
TYPE_CODE_ENUM = None
TYPE_CODE_FLAGS = None
TYPE_CODE_FUNC = None
TYPE_CODE_INT = None
TYPE_CODE_FLT = None
TYPE_CODE_VOID = None
TYPE_CODE_SET = None
TYPE_CODE_RANGE = None
TYPE_CODE_STRING = None
TYPE_CODE_BITSTRING = None
TYPE_CODE_ERROR = None
TYPE_CODE_METHOD = None
TYPE_CODE_METHODPTR = None
TYPE_CODE_MEMBERPTR = None
TYPE_CODE_REF = None
TYPE_CODE_RVALUE_REF = None
TYPE_CODE_CHAR = None
TYPE_CODE_BOOL = None
TYPE_CODE_COMPLEX = None
TYPE_CODE_TYPEDEF = None
TYPE_CODE_NAMESPACE = None
TYPE_CODE_DECFLOAT = None
TYPE_CODE_INTERNAL_FUNCTION = None

class Parameter:
     def __init__( self, a,b,c ):
         pass

PARAM_INTEGER = None
PARAM_BOOLEAN = None
PARAM_STRING = None

class Command:

    def __init__( self, a, b ):
        pass

    def dont_repeat( self ):
        pass


COMMAND_SUPPORT = None
COMMAND_DATA = None

COMPLETE_EXPRESSION = None

class error(BaseException):
    pass

def execute(a,b=None,c=None):
    pass
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
