import os, sys
sys.path.append("control_flow_analysis")
from path_tracer.main import PythonFuzz

from google.cloud import vision
import os
import sys
import io
import google.cloud
from google.cloud import language

# ==================

# ==================
@PythonFuzz
def find_dessert(image_path="API_input"):
  image_path = sys.argv[-1]
  client = vision.ImageAnnotatorClient()
  with io.open(image_path, 'rb') as image_file:
    content = image_file.read()
  image = vision.types.Image(content=content)
  response = client.label_detection(image=image)
  labels = response.label_annotations
  for l in labels:
    if "dessert" in l.description.lower():
      return True
  return False


# ==================
if __name__ == '__main__': 
  find_dessert()


find_dessert()
