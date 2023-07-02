from symbolic.args import *
import io
import google.cloud
import os
from google.cloud import vision
import sys
from google.cloud import language

# ==================
@symbolic(text="API_input", categories_0_="", categories_1_="", categories_2_="", categories__categories="", category__name="")
def find_food(text, categories_0_, categories_1_, categories_2_, categories__categories, category__name):
  # [Extra notation] API input from: ['text']
  # [Extra notation] Function call of classify_text
  categories = "None"
  categories = categories__categories
  categories = [categories_0_, categories_1_, categories_2_]
  for category in categories:
    if 'food' in category__name:
      return True
  return False


# ==================

# used_ml_api: classify_text
# ml_api_to_input: [['classify_text', 'document']]
# output_to_ml_api: {'categories': 'classify_text', 'categories__categories': 'classify_text', 'category': 'classify_text', 'categories_0_': 'classify_text', 'categories_1_': 'classify_text', 'categories_2_': 'classify_text', 'category__name': 'classify_text'}
# If_statement_changes: {'  for category in categories:': '  for category in categories:', "    if 'food' in category.name:": "    if 'food' in category__name:"}