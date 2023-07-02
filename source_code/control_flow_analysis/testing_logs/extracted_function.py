import io
import google.cloud
import os
from google.cloud import vision
import sys
from google.cloud import language

# ==================

# ==================
def find_food(text="API_input"):
  client = language.LanguageServiceClient()
  document = language.types.Document(content=text,type=language.enums.Document.Type.PLAIN_TEXT)
  categories = client.classify_text(document).categories
  for category in categories:
    if 'food' in category.name.lower():
      return True
  return False


# ==================
if __name__ == '__main__': 
  find_food()

