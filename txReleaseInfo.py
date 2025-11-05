#!/usr/bin/python3
"""
piTelex release information
"""
__author__      = "Detlef Gerhardt"
__email__       = ""
__copyright__   = "Copyright 2025, *dg*"
__license__     = "GPL3"
__version__     = "0.0.1"

from platform import release
import txCode

#######

class ReleaseInfo:

    release_number = "002c"

    itelex_protocol_version = 1

    release_itx_version = "pi" + release_number

    release_date = ''

    @staticmethod
    def get_release_info():
        if ReleaseInfo.release_date == '':
            ReleaseInfo.release_date = ReleaseInfo.read_release_date()
        return f'{ReleaseInfo.release_number} {ReleaseInfo.release_date}'

    @staticmethod
    def read_release_date():
        try:
            file = open('release_date', 'r')
            rd = file.read()
            file.close()
            return rd.rstrip('\r\n')
        except Exception as e:
            return ''

#######
