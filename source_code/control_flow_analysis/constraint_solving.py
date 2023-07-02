import os
import sys
import logging
import json
import operator
from optparse import OptionParser
import math
import subprocess


from symbolic.loader import *
from symbolic.explore import ExplorationEngine

from global_vars import *

logger = logging.getLogger(__name__)

def get_ml_api(filename):
  used_ml_api = []
  ml_api_to_input = []
  output_to_ml_api = {}
  If_statement_changes = {}
  with open(filename, 'r', encoding='utf8') as file_obj:
    text = file_obj.read()
  for line in text.split("\n")[::-1]:
    if line.startswith("# used_ml_api:"):
      used_ml_api = line.replace("# used_ml_api:","").strip().split(", ")
    if line.startswith("# ml_api_to_input:"):
      ml_api_to_input = eval(line.replace("# ml_api_to_input:","").strip())
    if line.startswith("# output_to_ml_api:"):
      output_to_ml_api = eval(line.replace("# output_to_ml_api:","").strip())
    if line.startswith("# If_statement_changes:"):
      If_statement_changes = eval(line.replace("# If_statement_changes:","").strip())
    
  return used_ml_api, ml_api_to_input, output_to_ml_api, If_statement_changes

def find_default_value(fields, var):
  while "___" in var:
    var = var.replace("___","__")
  tmp = var.split("__")[-1]
  for tuples in fields:
    field, value = tuples
    if value == "\"\"":
      value = ""
    if tmp == field:
      return value
  return 0

def get_fields_name(fields):
  field_names = []
  for tuples in fields:
    field, value = tuples
    field_names.append(field)
  return field_names

def find_value_in_solution(outputs, param):
  for output in outputs:
    name, value = output
    if name == param:
      return value
  return None

def get_search_keyword(outputs, api_set, output_to_ml_api):
  labels = {}
  scores = {}
  for output in outputs:
    name, value = output
    if not name in output_to_ml_api.keys():
      continue
    if not output_to_ml_api[name] in api_set:
      continue
    if output_to_ml_api[name] == "face_detection" or output_to_ml_api[name] == "text_detection":
      continue
    if name.endswith("__description"):
      if not value == find_default_value(API_Fields["label_detection"], name):
        labels[name.replace("__description","")] = value
    if name.endswith("__name"):
      if not value == find_default_value(API_Fields["object_localization"], name):
        labels[name.replace("__name","")] = value
    if name.endswith("__score"):
      if not value == find_default_value(API_Fields["label_detection"], name):
        scores[name.replace("__score","")] = value
  if "face_detection" in api_set:
    face_label = parse_face(outputs)
    if len(face_label)>0:
      labels["face_label_from_api"] = face_label

  if len(labels)==0:
    return ""

  search_keyword = ""
  for var in labels.keys():
    label = labels[var]
    if label in scores.keys():
      score = scores[var]
      if score < 0.5:
        continue
    if len(search_keyword)>0 and len(label)>0:
      if not label in search_keyword:
        search_keyword += " " + label
    else:
      search_keyword = label
  return search_keyword

def find_text(outputs, output_to_ml_api):
  fields = API_Fields["text_detection"]

  text = ""
  for output in outputs:
    name, value = output
    if not name in output_to_ml_api.keys():
      continue
    if not output_to_ml_api[name] == "text_detection":
      continue
    if name.endswith("___description"):
      if len(value.strip()) > 0:
        text += value.strip() + " "
  return text.strip()

# TODO: work on multiple faces
def parse_face(outputs):
  fields = API_Fields["face_detection"]
  field_names = get_fields_name(fields)
  faces = {}

  for output in outputs:
    name, value = output
    for i in range(len(field_names)):
      field = field_names[i]
      if "likelihood" in field and name.endswith("__"+field):
        var_name = name.replace("__"+field,"")
        if not var_name in faces.keys():
          faces[var_name] = [None, None, None, None] #anger, joy, surprise, sorrow
        faces[var_name][i] = value
  if len(faces)==0:
    return ""

  files = []
  for var in faces.keys():
    face = faces[var]
    # normailize to 1,2,3,4
    minimum = find_min_list(face)
    if minimum == None:
      continue

    face2 = [minimum-1 if i==None else i for i in face]
    indexs = norm_list(face2)
    anger_index, joy_index, surprise_index, sorrow_index = indexs
    highest_index = indexs.index(max(indexs))
    if anger_index<=2 and joy_index<=2 and surprise_index<=2 and sorrow_index<=2:
      return "serious human face"
    if highest_index == 0:
      return "angry human face"
    if highest_index == 1:
      return "joyful human face"
    if highest_index == 2:
      return "surprise human face"
    else:
      return "sad human face"
  return ""

def get_label_list(is_label=True):
  label_to_mid = {}
  mid_to_label = {}
  if is_label:
    f = open(LABEL_SRC,'r')
  else:
    f = open(OBJECT_SRC,'r')
  for line in f.readlines():
    label = line.replace("\n","").split(",")
    if len(label) == 2:
      label[1] = label[1].lower()
      mid_to_label[label[0]] = label[1]
      label_to_mid[label[1]] = label[0]
  f.close()
  return label_to_mid, mid_to_label

# TODO: support score
def solve_vision_keyword(outputs, fields, desc_name, score_name):
  labels = {}
  scores = {}
  mid_name = "__mid"
  for output in outputs:
    name, value = output
    if name.endswith(desc_name):
      if not value == find_default_value(fields, name):
        labels[name.replace(desc_name,"")] = value
    if name.endswith(score_name):
      if not value == find_default_value(fields, name):
        scores[name.replace(score_name,"")] = value
    if name.endswith(mid_name):
      if not value == find_default_value(fields, name):
        label_to_mid, mid_to_label = get_label_list(is_label=True)
        if value in mid_to_label.keys():
          labels[name.replace(mid_name,"")] = mid_to_label[value]
  if len(labels)==0:
    return ""

  search_keyword = ""
  for var in labels.keys():
    label = labels[var]
    if label in scores.keys():
      score = scores[var]
      if score < 0.5:
        continue
    if len(search_keyword)>0 and len(label)>0:
      if not label in search_keyword:
        search_keyword += " " + label
    else:
      search_keyword = label
  return search_keyword

def solve_label(outputs, find_keyword=False):
  search_keyword = solve_vision_keyword(outputs, API_Fields["label_detection"], "__description", "__score")
  if find_keyword:
    if len(search_keyword) > 0:
      return ("label_detection", "image of [" + str(search_keyword)+"]")
    else:
      return ("label_detection", "any type of image")
  return search_keyword

def solve_object(outputs, find_keyword=False):
  search_keyword = solve_vision_keyword(outputs, API_Fields["object_localization"], "__name", "__score")
  if find_keyword:
    if len(search_keyword) > 0:
      return ("object_localization", "image of [" + str(search_keyword)+"]")
    else:
      return ("object_localization", "any type of image")
  return search_keyword

def solve_landmark(outputs, find_keyword=False):
  search_keyword = solve_vision_keyword(outputs, API_Fields["landmark_detection"], "__description", "__score")
  if find_keyword:
    if len(search_keyword) > 0:
      return ("landmark_detection", "image of [" + str(search_keyword)+"]")
    else:
      return ("landmark_detection", "any type of image")
  return search_keyword

def solve_web(outputs, find_keyword=False):
  search_keyword = solve_vision_keyword(outputs, API_Fields["web_detection"], "__description", "__score")
  if find_keyword:
    if len(search_keyword) > 0:
      return ("web_detection", "image of [" + str(search_keyword)+"]")
    else:
      return ("web_detection", "any type of image")
  return search_keyword

def solve_text_detection(outputs, find_keyword=False):
  fields = API_Fields["text_detection"]

  text = ""
  break_flag = [False, False, False, False] # space, line break, hyphen, sure space
  type_flag = True
  cares_type = False
  for output in outputs:
    name, value = output
    if name.endswith("__description") or name.endswith("__text"):
      if len(value) > 0:
        text += value + " "
    if (name.endswith("__SPACE")) and value==True:
      break_flag[0] = True
    if name.endswith("__LINE_BREAK") and value==True:
      break_flag[1] = True
    if name.endswith("__HYPHEN") and value==True:
      break_flag[2] = True
    if (name.endswith("__SURE_SPACE") or name.endswith("__EOL_SURE_SPACE")) and value==True:
      break_flag[3] = True
    if name.endswith("__type"):
      type_flag = value
      cares_type = True
  text = text[:-1].strip()
  if cares_type:
    if not type_flag:
      break_flag = list(map(operator.not_, break_flag))
    if break_flag[0]:
      text += " "
    if break_flag[1]:
      text += "\n"
    if break_flag[2]:
      text += "-"
    if break_flag[3]:
      text += "      "
    # make sure space and newline will be detected
    if len(text) > 0:
      if text.startswith(" ") or text.startswith("\n"):
        text = "@" + text
      if text.endswith(" ") or text.endswith("\n"):
        text = text + "@"
  
  if find_keyword:
    return ("text_detection","image with text [" +text+ "]")
  return text

# find min, ignore None
def find_min_list(list):
  minimum = None
  for a in list:
    if a == None:
      continue
    if minimum == None:
      minimum = a
    else:
      minimum = min(minimum, a)
  return minimum

# turn list to 1234, while remaing > < relationship
def norm_list(list):
  list2 = [0] * len(list)
  for i in range(len(list)):
    for j in range(len(list)):
      if list[i] >= list[j]:
        list2[i] += 1
  return list2


def face_detection_face_type(likelihood_tuple):  
  likelihoods = ('UNKNOWN', 'VERY_UNLIKELY', 'UNLIKELY', 'POSSIBLE', 'LIKELY', 'VERY_LIKELY')
  
  if len(likelihood_tuple)!=4:
    return "unknown type of face"

  anger_index = likelihoods.index(likelihood_tuple[0])
  joy_index = likelihoods.index(likelihood_tuple[1])
  surprise_index = likelihoods.index(likelihood_tuple[2])
  sorrow_index = likelihoods.index(likelihood_tuple[3])
  
  if anger_index<=2 and joy_index<=2 and surprise_index<=2 and sorrow_index<=2:
    return "serious human face"

  indexs = (anger_index, joy_index, surprise_index, sorrow_index)
  high_index = max(indexs)

  if indexs[0] == high_index:
    return "angry human face"
  if indexs[1] == high_index:
    return "joyful human face"
  if indexs[2] == high_index:
    return "surprise human face"
  if indexs[3] == high_index:
    return "sad human face"
  
  return "unknown type of face"

# TODO: support face location, multiple faces
# currently, we only care about the relative relationship of feelings
def solve_face(outputs, find_keyword=False):
  fields = API_Fields["face_detection"]
  field_names = get_fields_name(fields)
  faces = {}

  for output in outputs:
    name, value = output
    for i in range(len(field_names)):
      field = field_names[i]
      if "likelihood" in field and name.endswith("__"+field):
        var_name = name.replace("__"+field,"")
        if not var_name in faces.keys():
          faces[var_name] = [None, None, None, None] #anger, joy, surprise, sorrow
        faces[var_name][i] = value

  if len(faces)==0:
    # empty file
    if find_keyword:
      return ("face_detection","blank image")
    return ""

  face_desc = ""
  for var in faces.keys():
    face = faces[var]
    # normailize to 1,2,3,4
    minimum = find_min_list(face)
    if minimum == None:
      continue
    face2 = [minimum-1 if i==None else i for i in face]
    face2 = norm_list(face2)
    for i in range(len(face2)):
      if face[i] == None:
        face2[i] = "UNKNOWN"
      elif face2[i] <= 1:
        face2[i] = "VERY_UNLIKELY"
      elif face2[i] == 2:
        face2[i] = "UNLIKELY"
      elif face2[i] == 3:
        face2[i] = "POSSIBLE"
      elif face2[i] == 4:
        face2[i] = "VERY_LIKELY"
      else:
        face2[i] = "UNKNOWN"
    if find_keyword:
      return ("face_detection","image with [" +face_detection_face_type(tuple(face2))+ "]")
    face_desc += face_detection_face_type(tuple(face2))+", "

  return face_desc


def solve_stt(outputs, find_keyword=False):
  transcript = ""
  for output in outputs:
    name, value = output
    if name.endswith("__transcript"):
      # if default value, then it has no constraint
      if len(value.strip()) == 0:
        continue
      else:
        transcript += value.strip() + ". "
  transcript = transcript[:-2]
  if find_keyword:
    if len(transcript)==0:
      return ("recognize","audio with script ["+str(transcript)+"]")
    else:
      return ("recognize","audio without script")
  return transcript

def round_up(n, decimals=0): 
  multiplier = 10 ** decimals 
  return math.ceil(n * multiplier) / multiplier
def round_down(n, decimals=0): 
  multiplier = 10 ** decimals 
  return math.floor(n * multiplier) / multiplier

Potential_entity_types = ['UNKNOWN', 'PERSON', 'LOCATION', 'ORGANIZATION', 'EVENT', 'WORK_OF_ART', 'CONSUMER_GOOD', 'OTHER', 'PHONE_NUMBER', 'ADDRESS', 'DATE', 'NUMBER', 'PRICE']
def solve_entity(outputs, find_keyword=False):
  global Potential_entity_types
  fields = API_Fields["analyze_entities"]
  names = {}
  types = {}
  for output in outputs:
    name, value = output
    if name.endswith("__name") and isinstance(value, str):
      if value in Entity_Types: # type.name
        types[name.replace("__name","")] = value
      elif len(value)>0: # entity.name
        names[name.replace("__name","")] = value
    if name.endswith("__type"):
      if not value == find_default_value(fields, name):
        if isinstance(value, int): 
          value = Entity_Types[value]
        types[name.replace("__type","")] = value
  if len(names)==0 and len(types)==0:
    if find_keyword:
      return ("analyze_entities", "any kind of text")
    return ""
  for var in (names.keys() | types.keys()):
    # set default value
    entity_name = None
    entity_type = None
    if var in names.keys():
      entity_name = names[var]
    if var in types.keys():
      entity_type = types[var]
      Potential_entity_types = [x for x in Potential_entity_types if not entity_type==x]
    if find_keyword:
      return ("analyze_entities","text containing entity ["+str([entity_name, entity_type])+"]")
    return str((entity_name, entity_type))
  return ""

def solve_entity_sentiment(outputs, find_keyword=False):
  return solve_entity(outputs, find_keyword)

Potential_syntax_types = Syntax_Types.copy()
def solve_analyze_syntax(outputs, find_keyword=False):
  global Potential_syntax_types
  fields = API_Fields["analyze_syntax"]
  types = {}
  for output in outputs:
    name, value = output
    if name.endswith("__tag"):
      if not value == find_default_value(fields, name):
        if isinstance(value, int): 
          value = Syntax_Types[value]
        types[name.replace("__tag","")] = value
  if len(types)==0:
    if find_keyword:
      return ("analyze_syntax", "any kind of text")
    return ""
  for var in types.keys():
    syntax_type = types[var]
    Potential_syntax_types = [x for x in Potential_syntax_types if not syntax_type==x]
    if find_keyword:
      return ("analyze_syntax", "text containing syntax ["+str(syntax_type)+"]")
    return str(syntax_type)
  return ""

Potential_text_types = ["art", "beauty", "business", "computer", "finance", "food", "game", "pet"]
def solve_text_classify(outputs, find_keyword=False):
  global Potential_text_types
  fields = API_Fields["classify_text"]
  labels = {}
  scores = {}
  for output in outputs:
    name, value = output
    if name.endswith("__name"):
      if not value == find_default_value(fields, name):
        labels[name.replace("__name","")] = value
    if name.endswith("__score"):
      if not value == find_default_value(fields, name):
        scores[name.replace("__confidence","")] = value
  if len(labels)==0:
    if find_keyword:
      return ("classify_text", "any kind of text")
    return ""

  for var in labels.keys():
    label = labels[var]
    if label in scores.keys():
      score = scores[var]
      if score < 0.5:
        continue
    if len(label) == 0:
      if find_keyword:
        return ("classify_text", "any kind of text")
      return ""
    else:
      if find_keyword:
        return ("classify_text", "text of ["+str(label)+"]")
      return label
  return ""

# group ml api with same inputs
def group_ml_api(ml_api_to_input):
  input_to_api = {}
  for item in ml_api_to_input:
    api, var = item
    if not var in input_to_api.keys():
      input_to_api[var] = []
    input_to_api[var].append(api)
  return input_to_api.values()

def read_wholefile(filename):
  with open(filename, 'r', encoding='utf8') as file_obj:
    text = file_obj.read()
  return text

def extract_indent(line):
  indent_pos = len(line) - len(line.lstrip())
  indent = line[:indent_pos]
  return indent

# for If_statement_changes
def search_value_to_key(dictionary, target_value):
  if not target_value in dictionary.values():
    return None
  for key, value in dictionary.items():
    if value == target_value:
      if key in dictionary.values():
        if key == dictionary[key]:
          return key
        return search_value_to_key(dictionary, key)
      else:
        return key

def read_coverage(cur_dir):
  f2 = open(cur_dir+"/tmp", 'r', encoding='utf8')
  lines = f2.readlines()
  f2.close()
  run_command("rm "+cur_dir+"/tmp")
  for line in reversed(lines):
    if line.strip().startswith(">>"):
      start = line.index("[")
      end = line.index("]")+1
      return eval(line[start:end])
  return set()

def run_command(command, timeout=None):
  if timeout is None:
    proc = subprocess.Popen(command, shell=True)
    proc.wait()
  else:
    proc = subprocess.Popen(command, shell=True)
    try:
      # if this returns, the process completed
      proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
      proc.terminate()

def get_exe_path(generated_inputs, cov_test_filename, base_code_file, import_fix_code, entry_func, vary=False, ml_output=None):
  vary_vars = []
  with open(cov_test_filename, 'w') as f:
    f.write(import_fix_code+'\n')
    for no, code in enumerate(base_code_file):
      if code.strip().startswith("#"):
        continue
      f.write(code+'\n')
      if code.strip().replace("  ", " ").startswith("def "+entry_func):
        no2 = no+1 # no+1 usually is an empty line
        while len(base_code_file[no2].strip())==0 and no2+1<len(base_code_file):
          no2 += 1
        indent = extract_indent(base_code_file[no2])
        for name, value in generated_inputs:
          if vary and not ml_output is None:
            if name in ml_output:
              # apply variation
              if isinstance(value, str):
                if len(value)>0:
                  value += "__varying!@#"
                  vary_vars.append((name, value))
              if isinstance(value, int):
                if value != 0:
                  value = (value + 100) * 100
                  vary_vars.append((name, value))
              if isinstance(value, float):
                if abs(value-0.1)>0.000001:
                  value = (value + 100) * 100
                  vary_vars.append((name, value))
          if isinstance(value, str):
            value = "\"" + value + "\""
          f.write(indent + str(name) +" = "+ str(value) +'\n')
    f.write(entry_func+"()\n")
  
  command = "python3 "+ cov_test_filename +" --rss-limit-mb=20480 --loc_file="+ cov_test_filename
  run_command(command +" > "+test_file_dir+"/tmp", timeout=2)
  covered_lines = read_coverage(test_file_dir)
  if vary:
    return covered_lines, vary_vars
  return covered_lines

if __name__ == '__main__':
  # logger.info("PyExZ3 (Python Exploration with Z3)")

  sys.path = [os.path.abspath(os.path.join(os.path.dirname(__file__)))] + sys.path

  usage = "usage: %prog [options] <path to a *.py file>"
  parser = OptionParser(usage=usage)

  parser.add_option("-l", "--log", dest="logfile", action="store", help="Save log output to a file", default="")
  parser.add_option("-s", "--start", dest="entry", action="store", help="Specify entry point", default="")
  parser.add_option("-m", "--max-iters", dest="max_iters", type="int", help="Run specified number of iterations", default=0)
  parser.add_option("-o", "--output-file", dest="output_file", type="string", help="Place where save generated files", default=0)
  # parser.add_option("-t", "--test-file", dest="test_file", type="string", help="File for running python fuzz", default=0)
  # parser.add_option("-f", "--func-params", dest="func_params", type="string", help="If the tested function contains multiple inputs, specify them. E.g. func(buf, a) -> 'API_input a'", default="")

  (options, args) = parser.parse_args()

  if not (options.logfile == ""):
    logging.basicConfig(filename=options.logfile,level=logging.WARNING)
    logging.getLogger().addHandler(logging.StreamHandler())
  else:
    logging.basicConfig(level=logging.WARNING)


  if len(args) == 0 or not os.path.exists(args[0]):
    parser.error("Missing app to execute")
    sys.exit(1)

  solver = "cvc"

  filename = os.path.abspath(args[0])
  

  # Get the object describing the application
  app = loaderFactory(filename,options.entry)
  if app == None:
    sys.exit(1)

  logger.info ("Exploring " + app.getFile() + "." + app.getEntry())
  used_ml_api, ml_api_to_input, output_to_ml_api, If_statement_changes = get_ml_api(filename)
  logger.info(f"Testing API {used_ml_api}")

  try:
    engine = ExplorationEngine(app.createInvocation(), solver=solver, print_info=False)
    generatedInputs, returnVals, path = engine.explore(options.max_iters)
    
    # logging information
    Log_Info = {"for_lines":[],"exe":[],"exe_vary":[]}

    # ==================================================
    # find covered path of each generatedInputs
    Solution_2_Path = [None] * len(generatedInputs)
    Solution_vary_2_Path = [None] * len(generatedInputs)
    
    test_file_dir = os.path.dirname(os.path.realpath(filename))
    cov_test_filename = os.path.join(test_file_dir, "__cov_test.py")
    python_fuzz_path = os.path.dirname(os.path.realpath(__file__))
    import_fix_code = f'import os, sys\nsys.path.append("{python_fuzz_path}")'
    base_code_file = read_wholefile(filename).split("\n")
    for no, code in enumerate(base_code_file):
      if code.startswith("@symbolic"):
        base_code_file[no] = "@PythonFuzz"
      if "from symbolic.args import *" in code:
        base_code_file[no] = "from path_tracer.main import PythonFuzz"
      if code.strip().replace("  ", " ").startswith("def "+options.entry):
        base_code_file[no] = "def " + options.entry + "(buf):"

    for i in range(len(generatedInputs)):
      Solution_2_Path[i] = get_exe_path(generatedInputs[i], cov_test_filename, base_code_file, import_fix_code, options.entry, vary=False, ml_output=None)
      Solution_vary_2_Path[i], vary_vars = get_exe_path(generatedInputs[i], cov_test_filename, base_code_file, import_fix_code, options.entry, vary=True, ml_output=output_to_ml_api.keys())
      Log_Info["exe"].append({"ML_input":None, "path": Solution_2_Path[i]})
      Log_Info["exe_vary"].append({"ML_input":None, "path": Solution_vary_2_Path[i], "vary_vars":vary_vars})


    
    # ==================================================
    # find if and fors
    Log_Info["for_lines"].append({"line_no":-1, "if_lines":[], "indent":-1, "code":""}) # outside any for loop

    base_code_file = [""] + read_wholefile(cov_test_filename).split("\n")
    Branches = {} # base_code_file -> test_code_file
    for no, code in enumerate(base_code_file):
      if "if __name__ == '__main__':" in code or "if __name__ == \"__main__\":" in code:
        break
      tmp = code.strip().replace("}","").replace("]","").replace(")","")
      if len(tmp) == 0:
        continue

      if tmp.startswith("for ") or tmp.startswith("while "):
        Log_Info["for_lines"].append({"line_no":no, "if_lines":[], "indent":len(extract_indent(base_code_file[no])), "code": code})
      
      if tmp.startswith("if ") or tmp.startswith("elif "):
        indent = len(extract_indent(base_code_file[no]))
        belongs_for = None
        for for_line in Log_Info["for_lines"]:
          if for_line["line_no"]>0 and for_line["indent"]<indent and for_line["line_no"]<no:
            flag = True
            for line_no in range(for_line["line_no"]+1, no):
              if len(base_code_file[line_no].strip()) > 0:
                if len(extract_indent(base_code_file[line_no])) > indent:
                  flag = False
            if flag:
              belongs_for = for_line
        if belongs_for is None:
          belongs_for = Log_Info["for_lines"][0] # not belonging to any
        
        then_line = no+1
        while (len(base_code_file[then_line].strip())==0 or base_code_file[then_line].strip().startswith("#")) and then_line+1<len(base_code_file):
          then_line += 1

        belongs_for["if_lines"].append({"line_no":no, "indent":len(extract_indent(base_code_file[no])), "code": code, "then_line":then_line})

      
        # 
        #   # because we removed this substring when reading the file in change_code.py
        #   for no_test, code_test in enumerate(test_code_file):
        #     if code_test.replace(".lower()","") == origin_code:
        #       Branches[no] = no_test
        #       break

    # ==================================================
    # looking for keywords
    if not options.output_file:
      sys.exit(0)
    output_file = os.path.abspath(options.output_file)
    
    for i in range(len(generatedInputs)):
      logger.info(str(generatedInputs[i]) + "\t-->\t" + str(returnVals[i]))

      keywords = {}
      for ml_api in used_ml_api:
        if ml_api == "label_detection":
          keyword = solve_label(generatedInputs[i])
          description = solve_label(generatedInputs[i], find_keyword=True)
        elif ml_api == "face_detection":
          keyword = solve_face(generatedInputs[i])
          description = solve_face(generatedInputs[i], find_keyword=True)
        elif ml_api == "text_detection" or used_ml_api[0] == "document_text_detection":
          keyword = solve_text_detection(generatedInputs[i])
          description = solve_text_detection(generatedInputs[i], find_keyword=True)
        elif ml_api == "web_detection":
          keyword = solve_web(generatedInputs[i])
          description = solve_web(generatedInputs[i], find_keyword=True)
        elif ml_api == "object_localization":
          keyword = solve_object(generatedInputs[i])
          description = solve_object(generatedInputs[i], find_keyword=True)
        elif ml_api == "recognize":
          keyword = solve_stt(generatedInputs[i])
          description = solve_stt(generatedInputs[i], find_keyword=True)
        elif ml_api == "classify_text":
          keyword = solve_text_classify(generatedInputs[i])
          description = solve_text_classify(generatedInputs[i], find_keyword=True)
        elif ml_api == "analyze_entities":
          keyword = solve_entity(generatedInputs[i])
          description = solve_entity(generatedInputs[i], find_keyword=True)
        elif ml_api == "analyze_entity_sentiment":
          keyword = solve_entity_sentiment(generatedInputs[i])
          description = solve_entity_sentiment(generatedInputs[i], find_keyword=True)
        elif ml_api == "analyze_syntax":
          keyword = solve_analyze_syntax(generatedInputs[i])
          description = solve_analyze_syntax(generatedInputs[i], find_keyword=True)
        else:
          logger.info("API reverse not supported: " + used_ml_api[0])
          sys.exit(1)
        keywords[ml_api] = {"keyword":keyword, "description":description}

      logger.info("=======================\n\n")
      Log_Info["exe"][i]["ML_input"] = keywords
      Log_Info["exe_vary"][i]["ML_input"] = keywords
    
    with open(output_file, "w") as f:
      f.write(json.dumps(Log_Info, sort_keys=False, indent=4))
      
    run_command("rm crash-*")
    run_command("rm timeout-*")


  except ImportError as e:
    # createInvocation can raise this
    logging.error(e)
    sys.exit(1)
  sys.exit(0)
