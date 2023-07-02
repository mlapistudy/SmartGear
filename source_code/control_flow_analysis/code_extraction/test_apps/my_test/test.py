import sys, os
import os.path
from time import *
# import numpy as np

# ==================
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
imported_test3=True

def foo(x):
  a = 1
  return x+1

def bara(x):
  return 1

def yes(y):
  y = y+1
  foo(y)

def main():
  yes(1)
  if False:
    const_value()
  a = bara(1) + bara(1)
  b = bara(1) + bara(1)
  bara(1)

def const_value():
  return False
