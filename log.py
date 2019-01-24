#!/usr/bin/python

_loglevel = 5

def LOG(text:str, level:int=3):
    if level <= _loglevel:
        print(text, end='', flush=True)

def set_log_level(level:int):
    global _loglevel

    _loglevel = level
