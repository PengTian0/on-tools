# Copyright 2016, EMC, Inc.

import subprocess
import logging
from pyjavaproperties import Properties
import os

log_file = 'manifest-build-tools.log'
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=log_file, filemode='w', level=logging.DEBUG)

def strip_suffix(text, suffix):
    """
    Cut a set of the last characters from a provided string
    :param text: Base string to cut
    :param suffix: String to remove if found at the end of text
    :return: text without the provided suffix
    """
    if text is not None and text.endswith(suffix):
        return text[:len(text) - len(suffix)]
    else:
        return text


def strip_prefix(text, prefix):
    if text is not None and text.startswith(prefix):
        return text[len(prefix):]
    else:
        return text

def link_dir(src, dest, dir):
    cmd_args = ["ln", "-s", src, dest]
    proc = subprocess.Popen(cmd_args,
                            cwd=dir,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            shell=False)
    (out, err) = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("Failed to sync {0} to {1} due to {2}".format(src, dest, err))

def parse_property_file(filename):
    """
    parse java properties file
    :param filename: the path of the properties file
    :return: dictionary loaded from the file
    """
    if not os.path.isfile(filename):
        raise RuntimeError("No file found for parameter at {0}".format(filename))
    p = Properties()
    p.load(open(filename))
    return p

def is_executable(fpath):
    if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
        return True
    return False

def which(program):
    fpath, fname = os.path.split(program)
    if fpath:
        if is_executable(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_executable(exe_file):
                return exe_file
    return None
