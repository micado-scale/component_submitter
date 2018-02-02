#!/usr/bin/python

import sys

class Prompt(object):
	
  def __init__(self, question, default=None):
		self.question = question
		self.default = default

  
  def query_yes_no(self):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
      It must be "yes" (the default), "no" or None (meaning
      an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
               "no": False, "n": False}
    if self.default is None:
      prompt = " [y/n] "
    elif self.default == "yes":
      prompt = " [Y/n] "
    elif self.default == "no":
      prompt = " [y/N] "
    else:
      raise ValueError("invalid default answer: '%s'" % self.default)

    while True:
      sys.stdout.write(self.question + prompt)
      choice = raw_input().lower()
      if self.default is not None and choice == '':
        return valid[self.default]
      elif choice in valid:
        return valid[choice]
      else:
        sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

  def query_input(self):
    """ Ask for input via raw_input() and return their answer.
        "question" is a string that is presented to the user.
    """

    while True:
      sys.stdout.write(self.question)
      value = raw_input()
      if value == '':
        return None
      return value


