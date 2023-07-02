import json
import logging

import os, io, sys

from google.cloud import vision
from google.cloud import language
from google.cloud import speech
from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

from .enum_classes import *
from .global_vars import *

# ==========================================================
# =================== tool functions ====================
# ==========================================================

def load_json(filename):
  with open(filename, 'r', encoding='utf8') as file_obj:
    json_data = file_obj.read()
  return json.loads(json_data)

def list2str(a):
  b = [str(x) for x in a]
  return '\t'.join(b)

def print_long_list_values(data):
  str_value = []
  for element in data:
    str_value.append(">> " + str(element).replace("\n"," ")[:100])
  return "\n".join(str_value)

# ==========================================================
# ===================   reading  logs   ====================
# ==========================================================

def read_structure_from_json(filename):
  cf_structure = load_json(filename)
  new_conditions = {}
  ml_tasks = []
  if "conditions" in cf_structure.keys():
    apis = cf_structure["conditions"].keys()
    for api in apis:
      ml_task = parse_api_to_enum(api)
      if not ml_task is None:
        ml_tasks.append(ml_task)
        new_conditions[ml_task] = cf_structure["conditions"][api]
  cf_structure["conditions"] = new_conditions
  return ml_tasks, cf_structure

def read_func_data_from_json(filename):
  cf_structure = load_json(filename)
  input_params, ml_input = [], []
  if "func_info" in cf_structure.keys():
    input_params = cf_structure["func_info"]["input_param"]
    ml_input = cf_structure["func_info"]["API_param"]
  return input_params, ml_input

# ==========================================================
# =================== execution related ====================
# ==========================================================

# extract executed lines from sys.trace(). we currently only track one file
# if not specifying which examined_file, it would be the file contains function definition
# trace result looks like: {'counts': {('execution.py', 30): 1, ('execution.py', 31): 1, ('execution.py', 34): 1}, 'counter': {('execution.py', 30): 1, ('execution.py', 31): 1, ('execution.py', 34): 1}, 'calledfuncs': {}, 'callers': {}, 'infile': None, 'outfile': None}
def extract_executed_lines(trace_result, examined_file=None):
  if trace_result is None:
    return None
  lines = []
  for c in trace_result.counts:
    file, line_no = c
    if examined_file is None:
      examined_file = file
    if file == examined_file:
      lines.append(line_no)
  return lines


def fulfill_ml_branch_cond(cf_structure, ml_task, ml_result):
  # control_flow = cf_structure["control_flow"]
  contains_cond = False
  fulfill = False
  if not ml_task in ml_result.keys():
    return contains_cond, fulfill

  if ml_task in cf_structure["conditions"].keys():
    contains_cond = True
    condition = cf_structure["conditions"][ml_task]
    for branch in condition:
      if len(branch)==0 or (len(branch)==1 and branch[0]==""):
        continue
      for keyword in branch:
        if ml_task in [MlTask.VISION_LABEL, MlTask.VISION_OBJECT, MlTask.VISION_WEB, MlTask.VISION_LAND, MlTask.VISION_LOGO, MlTask.LANG_CLASS, MlTask.SPEECH_REC]:
          for label in ml_result[ml_task]:
            if (not cf_structure["exact_match"] and keyword.lower() in label.lower()) \
                or (cf_structure["exact_match"] and keyword.lower() == label.lower()):
              fulfill = True
              break
        if ml_task in [MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT]:
          if (not cf_structure["exact_match"] and keyword.lower() in ml_result[ml_task].lower()) \
                or (cf_structure["exact_match"] and keyword.lower() == ml_result[ml_task].lower()):
            fulfill = True
        if ml_task in [MlTask.LANG_ENTITY, MlTask.LANG_ENTITY_SENTI]:
          for res_tuple in ml_result[ml_task]:
            name = res_tuple[0]
            type_ = res_tuple[1]
            if (not cf_structure["exact_match"] and (keyword in name)) \
                or (cf_structure["exact_match"] and keyword == name) \
                or (keyword == type_):
              fulfill = True
              break
        if ml_task in [MlTask.VISION_FACE, MlTask.LANG_SENTI]:
          pass
    
  return contains_cond, fulfill
  


# ==========================================================
# =================== ML API related ====================
# ==========================================================

# whether it is the result of an ml api
# https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse
# https://googleapis.dev/python/language/latest/language_v1/types.html?highlight=language%20types#module-google.cloud.language_v1.types
# https://googleapis.dev/python/speech/latest/speech_v1/types.html?highlight=types#module-google.cloud.speech_v1.types
def is_ml_api_result(variable_value):
  if isinstance(variable_value, vision.types.AnnotateImageResponse):
    return True
  if isinstance(variable_value, language.types.AnalyzeEntitiesResponse) or isinstance(variable_value, language.types.AnalyzeEntitySentimentResponse) or isinstance(variable_value, language.types.AnalyzeSentimentResponse) or isinstance(variable_value, language.types.AnalyzeSyntaxResponse) or isinstance(variable_value, language.types.AnnotateTextResponse) or isinstance(variable_value, language.types.ClassifyTextResponse):
    return True
  if isinstance(variable_value, speech.RecognizeResponse) or isinstance(variable_value, speech.LongRunningRecognizeResponse) or isinstance(variable_value, speech.StreamingRecognizeResponse):
    return True

  if isinstance(variable_value, RepeatedCompositeFieldContainer):
    if len(variable_value) > 0:
      value2 = variable_value[0]
      if isinstance(value2, vision.types.FaceAnnotation) or isinstance(value2, vision.types.EntityAnnotation) or isinstance(value2, vision.types.LocalizedObjectAnnotation) or isinstance(value2, vision.types.TextAnnotation) or isinstance(value2, vision.types.WebDetection):
        return True
      if isinstance(value2, language.types.Entity) or isinstance(value2, language.types.Sentiment) or isinstance(value2, language.types.Sentence) or isinstance(value2, language.types.ClassificationCategory):
        return True
      if isinstance(variable_value, speech.SpeechRecognitionResult) or isinstance(variable_value, speech.SpeechRecognitionResult) or isinstance(variable_value, speech.StreamingRecognitionResult):
        return True
  

# extract ml api result from all variables get in one run
# https://cloud.google.com/vision/docs/
# https://cloud.google.com/natural-language/docs/
# https://cloud.google.com/speech-to-text/docs/
def extract_ml_api_result(returned_value, ml_apis):
  ml_value = {}
  for ml_api in ml_apis:
    ml_value[ml_api] = None

  value = returned_value
  if isinstance(value, vision.types.AnnotateImageResponse):
    if MlTask.VISION_LABEL in ml_apis and value.label_annotations:
      ml_value[MlTask.VISION_LABEL] = value.label_annotations
    if MlTask.VISION_OBJECT in ml_apis and value.localized_object_annotations:
      ml_value[MlTask.VISION_OBJECT] = value.localized_object_annotations
    if MlTask.VISION_FACE in ml_apis and value.face_annotations:
      ml_value[MlTask.VISION_FACE] = value.face_annotations
    if MlTask.VISION_TEXT in ml_apis and value.text_annotations:
      ml_value[MlTask.VISION_TEXT] = value.textAnnotations
    if MlTask.VISION_DOCUMENT in ml_apis and value.full_text_annotation:
      ml_value[MlTask.VISION_DOCUMENT] = value.full_text_annotation
    if MlTask.VISION_WEB in ml_apis and value.web_detection:
      ml_value[MlTask.VISION_WEB] = value.web_detection
    if MlTask.VISION_LAND in ml_apis and value.landmark_annotations:
      ml_value[MlTask.VISION_LAND] = value.landmark_annotations
    if MlTask.VISION_LOGO in ml_apis and value.logo_annotations:
      ml_value[MlTask.VISION_LOGO] = value.logo_annotations

  elif isinstance(value, language.types.AnalyzeEntitiesResponse) or isinstance(value, language.types.AnalyzeEntitySentimentResponse) or isinstance(value, language.types.AnalyzeSentimentResponse) or isinstance(value, language.types.AnalyzeSyntaxResponse) or isinstance(value, language.types.AnnotateTextResponse) or isinstance(value, language.types.ClassifyTextResponse):
    if MlTask.LANG_CLASS in ml_apis and isinstance(value, language.types.ClassifyTextResponse):
      ml_value[MlTask.LANG_CLASS] = value.categories
    if MlTask.LANG_SENTI in ml_apis and isinstance(value, language.types.AnalyzeSentimentResponse):
      ml_value[MlTask.LANG_SENTI] = value.document_sentiment
    if MlTask.LANG_ENTITY in ml_apis and isinstance(value, language.types.AnalyzeEntitiesResponse):
      ml_value[MlTask.LANG_ENTITY] = value.entities
    if MlTask.LANG_ENTITY_SENTI in ml_apis and isinstance(value, language.types.AnalyzeEntitySentimentResponse):
      ml_value[MlTask.LANG_ENTITY_SENTI] = value.entities

  elif isinstance(value, speech.SpeechRecognitionResult) or isinstance(value, speech.SpeechRecognitionResult) or isinstance(value, speech.StreamingRecognitionResult):
    if MlTask.SPEECH_REC in ml_apis:
      ml_value[MlTask.SPEECH_REC] = value.results

  elif isinstance(value, RepeatedCompositeFieldContainer): # a rescue, not precise
    if len(value) > 0:
      value2 = value[0]
      if isinstance(value2, vision.types.EntityAnnotation) and MlTask.VISION_LABEL in ml_apis and not MlTask.VISION_LABEL in ml_value.keys():
        ml_value[MlTask.VISION_LABEL] = value
      elif isinstance(value2, vision.types.LocalizedObjectAnnotation) and MlTask.VISION_OBJECT in ml_apis and not MlTask.VISION_OBJECT in ml_value.keys():
        ml_value[MlTask.VISION_OBJECT] = value
      elif isinstance(value2, vision.types.FaceAnnotation) and MlTask.VISION_FACE in ml_apis and not MlTask.VISION_FACE in ml_value.keys():
        ml_value[MlTask.VISION_FACE] = value
      elif isinstance(value2, vision.types.EntityAnnotation) and MlTask.VISION_TEXT in ml_apis and not MlTask.VISION_TEXT in ml_value.keys():
        ml_value[MlTask.VISION_TEXT] = value
      elif isinstance(value2, vision.types.TextAnnotation) and MlTask.VISION_DOCUMENT in ml_apis and not MlTask.VISION_DOCUMENT in ml_value.keys():
        ml_value[MlTask.VISION_DOCUMENT] = value
      elif isinstance(value2, vision.types.WebDetection) and MlTask.VISION_WEB in ml_apis and not MlTask.VISION_WEB in ml_value.keys():
        ml_value[MlTask.VISION_TEXT] = value
      if isinstance(value2, vision.types.EntityAnnotation) and MlTask.VISION_LAND in ml_apis and not MlTask.VISION_LAND in ml_value.keys():
        ml_value[MlTask.VISION_LAND] = value
      if isinstance(value2, vision.types.EntityAnnotation) and MlTask.VISION_LOGO in ml_apis and not MlTask.VISION_LOGO in ml_value.keys():
        ml_value[MlTask.VISION_LOGO] = value

      elif isinstance(value2, language.types.ClassificationCategory) and MlTask.LANG_CLASS in ml_apis:
        ml_value[MlTask.LANG_CLASS] = value
      elif isinstance(value2, language.types.Sentiment) and MlTask.LANG_SENTI in ml_apis:
        ml_value[MlTask.LANG_SENTI] = value
      elif isinstance(value2, language.types.Entity) and MlTask.LANG_ENTITY in ml_apis:
        ml_value[MlTask.LANG_ENTITY] = value

      elif isinstance(value2, speech.SpeechRecognitionResult) and MlTask.SPEECH_REC in ml_apis:
        ml_value[MlTask.SPEECH_REC] = value

  return ml_value

def parse_ml_value(ml_value):
  if MlTask.VISION_LABEL in ml_value.keys():
    if ml_value[MlTask.VISION_LABEL] is None:
      ml_value[MlTask.VISION_LABEL] = []
    else:
      ml_value[MlTask.VISION_LABEL] = [x.description for x in ml_value[MlTask.VISION_LABEL]]
  if MlTask.VISION_OBJECT in ml_value.keys():
    if ml_value[MlTask.VISION_OBJECT] is None:
      ml_value[MlTask.VISION_OBJECT] = []
    else:
      ml_value[MlTask.VISION_OBJECT] = [x.name for x in ml_value[MlTask.VISION_OBJECT]]
  if MlTask.VISION_FACE in ml_value.keys():
    if ml_value[MlTask.VISION_FACE] is None:
      ml_value[MlTask.VISION_FACE] = []
    else:
      ml_value[MlTask.VISION_FACE] = ml_value[MlTask.VISION_FACE]
  if MlTask.VISION_TEXT in ml_value.keys():
    if ml_value[MlTask.VISION_TEXT] is None:
      ml_value[MlTask.VISION_TEXT] = ""
    else:
      ml_value[MlTask.VISION_TEXT] = ml_value[MlTask.VISION_TEXT][0].description
  if MlTask.VISION_DOCUMENT in ml_value.keys():
    if ml_value[MlTask.VISION_DOCUMENT] is None:
      ml_value[MlTask.VISION_DOCUMENT] = ""
    else:
      ml_value[MlTask.VISION_DOCUMENT] = ml_value[MlTask.VISION_DOCUMENT].text
  if MlTask.VISION_WEB in ml_value.keys():
    if ml_value[MlTask.VISION_WEB] is None:
      ml_value[MlTask.VISION_WEB] = []
    else:
      desc_list = [x.label for x in ml_value[MlTask.VISION_WEB].best_guess_labels]
      desc_list += [x.description for x in ml_value[MlTask.VISION_WEB].web_entities]
      ml_value[MlTask.VISION_WEB] = desc_list
  if MlTask.VISION_LAND in ml_value.keys():
    if ml_value[MlTask.VISION_LAND] is None:
      ml_value[MlTask.VISION_LAND] = []
    else:
      ml_value[MlTask.VISION_LAND] = [x.description for x in ml_value[MlTask.VISION_LAND]]
  if MlTask.VISION_LOGO in ml_value.keys():
    if ml_value[MlTask.VISION_LOGO] is None:
      ml_value[MlTask.VISION_LOGO] = []
    else:
      ml_value[MlTask.VISION_LOGO] = [x.description for x in ml_value[MlTask.VISION_LOGO]]

  if MlTask.LANG_CLASS in ml_value.keys():
    if ml_value[MlTask.LANG_CLASS] is None:
      ml_value[MlTask.LANG_CLASS] = []
    else:
      ml_value[MlTask.LANG_CLASS] = [x.name for x in ml_value[MlTask.LANG_CLASS]]
  if MlTask.LANG_SENTI in ml_value.keys():
    if ml_value[MlTask.LANG_SENTI] is None:
      ml_value[MlTask.LANG_SENTI] = [0,0]
    else:
      ml_value[MlTask.LANG_SENTI] = [ml_value[MlTask.LANG_SENTI].score, ml_value[MlTask.LANG_SENTI].magnitude]
  if MlTask.LANG_ENTITY in ml_value.keys():
    if ml_value[MlTask.LANG_ENTITY] is None:
      ml_value[MlTask.LANG_ENTITY] = []
    else:
      ml_value[MlTask.LANG_ENTITY] = [(x.name, x.type_) for x in ml_value[MlTask.LANG_ENTITY]]
  if MlTask.LANG_ENTITY_SENTI in ml_value.keys():
    if ml_value[MlTask.LANG_ENTITY_SENTI] is None:
      ml_value[MlTask.LANG_ENTITY_SENTI] = []
    else:
      ml_value[MlTask.LANG_ENTITY_SENTI] = [(x.name, x.type_, x.salience, x.sentiment) for x in ml_value[MlTask.LANG_ENTITY_SENTI]]

  if MlTask.SPEECH_REC in ml_value.keys():
    if ml_value[MlTask.SPEECH_REC] is None:
      ml_value[MlTask.SPEECH_REC] = []
    else:
      ml_value[MlTask.SPEECH_REC] = [x.alternatives[0].transcript for x in ml_value[MlTask.SPEECH_REC]]

  return ml_value

def change_api_result(ml_task, ml_api_value, added_values):
  value = ml_api_value
  logging.debug("[change_api_result]: Task:{}, Added values:{}".format(ml_task, added_values))

  if ml_task == MlTask.VISION_LABEL and value.label_annotations:
    labels = value.label_annotations
    for add_v in added_values:
      x = labels.add()
      x.description = add_v
      x.confidence = labels[0].confidence
      labels.insert(0, labels[-1])
      labels.pop(-1)
  if ml_task == MlTask.VISION_OBJECT and value.localized_object_annotations:
    labels = value.localized_object_annotations
    for add_v in added_values:
      x = labels.add()
      x.name = add_v
      x.score = labels[0].score
      labels.insert(0, labels[-1])
      labels.pop(-1)
  if ml_task == MlTask.VISION_WEB and value.web_detection:
    labels = value.web_detection
    for add_v in added_values:
      x = labels.best_guess_labels.add()
      x.label = add_v
      labels.best_guess_labels.insert(0, labels[-1])
      labels.best_guess_labels.pop(-1)
      x = labels.web_entities.add()
      x.description = add_v
      x.score = labels[0].score
      labels.web_entities.insert(0, labels[-1])
      labels.web_entities.pop(-1)
  if ml_task == MlTask.VISION_LAND and value.landmark_annotations:
    labels = value.landmark_annotations
    for add_v in added_values:
      x = labels.add()
      x.description = add_v
      labels.insert(0, labels[-1])
      labels.pop(-1)
  if ml_task == MlTask.VISION_LOGO and value.logo_annotations:
    labels = value.logo_annotations
    for add_v in added_values:
      x = labels.add()
      x.description = add_v
      labels.insert(0, labels[-1])
      labels.pop(-1)
    

  if ml_task in [MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT]:
    if ml_task == MlTask.VISION_TEXT and value.text_annotations:
      labels = value.text_annotations
      if len(labels)>0:
        labels[0].description = labels[0].description + "\n" + "\n".join(added_values)
      else:
        x = labels.add()
        x.description = "\n".join(added_values)
        x.confidence = 0.9
      for add_v in added_values:
        x = labels.add()
        x.description = add_v
        x.confidence = labels[0].confidence
        labels.insert(1, labels[-1])
        labels.pop(-1)
    if ml_task == MlTask.VISION_DOCUMENT and value.full_text_annotation:
      # TODO: support charater level updation
      labels = value.full_text_annotation
      labels.text = labels.text + "\n" + "\n".join(added_values)

  if ml_task == MlTask.SPEECH_REC:
    labels = value.results
    for add_v in added_values:
      x = labels.add()
      x.alternatives.add()
      x.alternatives[0].transcript = add_v
      x.alternatives[0].confidence = labels[0].alternatives[0].confidence
      labels.insert(0, labels[-1])
      labels.pop(-1)
      
  if ml_task in [MlTask.VISION_FACE, MlTask.LANG_SENTI, MlTask.LANG_ENTITY]:
    pass

  return value

def extract_ml_input_content(ml_input, id=None):
  if isinstance(ml_input, vision.types.Image):
    tmp_file = os.path.join(LOG_SRC, "image_{}.raw".format(id))
    with io.open(tmp_file, 'wb') as image_file:
      image_file.write(ml_input.content)
    return tmp_file
  if isinstance(ml_input, language.types.Document):
    return ml_input.content
  if isinstance(ml_input, speech.RecognitionAudio):
    tmp_file = os.path.join(LOG_SRC, "audio_{}.raw".format(id))
    with io.open(tmp_file, 'wb') as audio_file:
      audio_file.write(ml_input.content)
    return tmp_file
  
  logging.debug("[extract_ml_input_content] Cannot identify ml_input")
  return None

def extract_ml_input_content_exact_value(ml_input):
  if isinstance(ml_input, vision.types.Image):
    return ml_input.content
  if isinstance(ml_input, language.types.Document):
    return ml_input.content
  if isinstance(ml_input, speech.RecognitionAudio):
    return ml_input.content
  logging.debug("[extract_ml_input_content_exact_value] Cannot identify ml_input")
  return None

