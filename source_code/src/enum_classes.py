from enum import Enum

class MlTask(Enum):
  VISION_LABEL = 1
  VISION_OBJECT = 2
  VISION_FACE = 3
  VISION_TEXT = 4
  VISION_DOCUMENT = 5
  VISION_WEB = 6
  VISION_LAND = 7
  VISION_LOGO = 8

  LANG_CLASS = 101
  LANG_SENTI = 102
  LANG_ENTITY = 103
  
  SPEECH_REC = 201

  # not fully supported yet
  LANG_ENTITY_SENTI = 104
  LANG_SYNTAX = 105
  SPEECH_LONG = 202
  SPEECH_STREAM = 203


class StatusCode(Enum):
  UNKNOWN = 0
  SUCCESS = 1
  ACCURACY_FAILURE = 2
  CRASH = 5 # catches a crash

class FailureCode(Enum):
  UNKNOWN = 0
  MISMATCH_HEIR = 1
  MISMATCH_PERS = 2
  MISMATCH_FOCUS = 3 # this is a potential failure
  INCORRECT_CROSS_INPUT = 4
  INCORRECT_CROSS_API = 5
  INCORRECT_CROSS_API_SW = 6

class SolutionCode(Enum):
  CLUSTER = 1
  SEGMENT = 2
  ENSEMBLE = 3
  TEMPORAL = 4
  REPORT = 5 # not fixing suggestion, just report failure


def parse_api_to_enum(api):
  if api == "label_detection":
    return MlTask.VISION_LABEL
  elif api == "object_localization":
    return MlTask.VISION_OBJECT
  elif api == "face_detection":
    return MlTask.VISION_FACE
  elif api == "text_detection":
    return MlTask.VISION_TEXT
  elif api == "document_text_detection":
    return MlTask.VISION_DOCUMENT
  elif api == "web_detection":
    return MlTask.VISION_WEB
  elif api == "landmark_detection":
    return MlTask.VISION_LAND
  elif api == "logo_detection":
    return MlTask.VISION_LOGO

  elif api == "classify_text":
    return MlTask.LANG_CLASS
  elif api == "analyze_sentiment":
    return MlTask.LANG_SENTI
  elif api == "analyze_entities":
    return MlTask.LANG_ENTITY
  elif api == "analyze_entity_sentiment":
    return MlTask.LANG_ENTITY_SENTI
  elif api == "analyze_syntax":
    return MlTask.LANG_SYNTAX

  elif api == "recognize":
    return MlTask.SPEECH_REC
  elif api == "long_running_recognize":
    return MlTask.SPEECH_LONG
  elif api == "streaming_recognize":
    return MlTask.SPEECH_STREAM

def parse_enum_to_api(ml_task):
  if ml_task == MlTask.VISION_LABEL:
    return "label_detection"
  elif ml_task == MlTask.VISION_OBJECT:
    return "object_localization"
  elif ml_task == MlTask.VISION_FACE:
    return "face_detection"
  elif ml_task == MlTask.VISION_TEXT:
    return "text_detection"
  elif ml_task == MlTask.VISION_DOCUMENT:
    return "document_text_detection"
  elif ml_task == MlTask.VISION_WEB:
    return "web_detection"
  elif ml_task == MlTask.VISION_LAND:
    return "landmark_detection"
  elif ml_task == MlTask.VISION_LOGO:
    return "logo_detection"

  elif ml_task == MlTask.LANG_CLASS:
    return "classify_text"
  elif ml_task == MlTask.LANG_SENTI:
    return "analyze_sentiment"
  elif ml_task == MlTask.LANG_ENTITY:
    return "analyze_entities"
  elif ml_task == MlTask.LANG_ENTITY_SENTI:
    return "analyze_entity_sentiment"
  elif ml_task == MlTask.LANG_SYNTAX:
    return "analyze_syntax"

  elif ml_task == MlTask.SPEECH_REC:
    return "recognize"
  elif ml_task == MlTask.SPEECH_LONG:
    return "long_running_recognize"
  elif ml_task == MlTask.SPEECH_STREAM:
    return "streaming_recognize"

  