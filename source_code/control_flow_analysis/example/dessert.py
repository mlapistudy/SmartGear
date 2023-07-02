import sys, io, os
# from src.diagnoser import Diagnoser
from google.cloud import vision
from google.cloud import language

# This file could be auto generated with tool inside ./control_flow_analysis
# We cache it for an easy usage
# info_file1 = os.path.join("execution_logs","find_dessert.json")
# @Diagnoser(info_file=info_file1)
def find_dessert(image_path):
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
  