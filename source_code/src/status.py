from .enum_classes import *

class Status(object):
  def __init__(self):
    self.type = StatusCode.UNKNOWN
    self.exception = None
    self.executed_lines = None
    self.failures = []

  def __str__(self):
    has_failure = len(self.failures)>0
    execept = self.exception
    return "<Status: %s, Exception: %s, Accuracy Failure: %r, Exe_lines: %s>" % (self.type, execept, has_failure, self.executed_lines)
  def __repr__(self):
    return self.__str__()


class Failure(object):
  def __init__(self):
    self.type = None
    self.API = None
    self.fixing_suggestion = None
    self.corrected_API_output = None


  def __str__(self):
    if self.corrected_API_output is None:
      return "<Accuracy Failure: %s, ML API: %s, fixing_suggestion: %s>" % (self.type, self.API, self.fixing_suggestion)
    return "<Accuracy Failure: %s, ML API: %s, Fixing Suggestion: %s, Corrected API Output:%s>" % (self.type, self.API, self.fixing_suggestion, self.corrected_API_output)
  def __repr__(self):
    return self.__str__()