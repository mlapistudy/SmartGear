import os, sys
sys.path.append("control_flow_analysis")
from path_tracer.main import PythonFuzz
import io
import google.cloud
import os
from google.cloud import vision
import sys
from google.cloud import language

@PythonFuzz
def find_food(buf):
  text = "API_input"
  categories_0_ = ""
  categories_1_ = ""
  categories_2_ = ""
  categories__categories = ""
  category__name = "food__varying!@#"
  categories = "None"
  categories = categories__categories
  categories = [categories_0_, categories_1_, categories_2_]
  for category in categories:
    if 'food' in category__name:
      return True
  return False



find_food()
