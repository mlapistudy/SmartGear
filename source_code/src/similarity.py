import enum
from PIL import Image
import imagehash # https://pypi.org/project/ImageHash/
from rapidfuzz.distance import Levenshtein #https://maxbachmann.github.io/Levenshtein/levenshtein.html#distance
import math, os, logging

from .enum_classes import *
from .status import *
from . import knowledge_graph as kg
from . import helper

# ==========================================================
# =================== image ==========================
# ==========================================================

def get_imageHash(image_path, hash_size):
  return imagehash.average_hash(Image.open(image_path), hash_size=hash_size) 

def image_similarity(image_path1, image_path2):
  hash_size = 8 # turn image to N*N pixels
  hash1 = get_imageHash(image_path1, hash_size)
  hash2 = get_imageHash(image_path2, hash_size)
  diff = hash1 - hash2
  diff_portion = diff/(hash_size*hash_size)
  return 1-diff_portion

def is_similar_image(image_path1, image_path2):
  diff_portion = 1 - image_similarity(image_path1, image_path2)
  threshold = 0.1
  if diff_portion < threshold:
    return True
  else:
    return False

# ==========================================================
# =================== text ==========================
# ==========================================================

def get_text_sim_threshold(length, character_level):
  N = math.ceil(length*0.3)
  if character_level:
    N = max(N, 4)
  else:
    N = max(N, 1)
  N = min(length-2, N)
  return N

# The Longest Common Subsequence
def lcsequence_dp(input_x, input_y, return_seq=False):
  # input_y as column, input_x as row
  x_pos = []

  dp = [([0] * (len(input_y)+1)) for i in range(len(input_x)+1)]
  for i in range(1, len(input_x)+1):
      for j in range(1, len(input_y)+1):
          if i == 0 or j == 0: 
                  dp[i][j] = 1
          elif input_x[i-1] == input_y[j-1]:
              dp[i][j] = dp[i - 1][j - 1] + 1
              x_pos.append(i-1)
          else:
              dp[i][j] = max(dp[i - 1][j], dp[i][j -1])
  if not return_seq:
    return dp[-1][-1]
  
  if isinstance(input_x, list):
    lcs = []
    i = len(input_x)
    j = len(input_y)
    while i > 0 and j > 0:
      if input_x[i-1] == input_y[j-1]:
          lcs.append(input_x[i-1])
          # x_pos.append(i-1)
          start_x = i-1
          i -= 1
          j -= 1
      elif dp[i-1][j] > dp[i][j-1]:
          i -= 1
      else:
          j -= 1
  else:
    lcs = ""
    i = len(input_x)
    j = len(input_y)
    while i > 0 and j > 0:
      if input_x[i-1] == input_y[j-1]:
          lcs += input_x[i-1]
          # x_pos.append(i-1)
          i -= 1
          j -= 1
      elif dp[i-1][j] > dp[i][j-1]:
          i -= 1
      else:
          j -= 1
  lcs = lcs[::-1]
  return dp[-1][-1], lcs, x_pos

# The Longest Common Substring
def lcstring_dp(input_x, input_y, return_seq=False):
 
  maxLen = 0 
  endIndex = len(input_x)
  
  FIND = [[0 for x in range(len(input_y) + 1)] for y in range(len(input_x) + 1)]

  for i in range(1, len(input_x) + 1):
    for j in range(1, len(input_y) + 1):
      if input_x[i - 1] == input_y[j - 1]:
          FIND[i][j] = FIND[i - 1][j - 1] + 1
          if FIND[i][j] > maxLen:
              maxLen = FIND[i][j]
              endIndex = i
  if not return_seq:
    return maxLen
  return maxLen, input_x[endIndex - maxLen: endIndex]


def is_similar_text(input_x, input_y, character_level=True, return_dist=False):
  if not character_level:
    input_x = input_x.split()
    input_y = input_y.split()
  if len(input_x)+len(input_y)==0:
    return True
  # N = (len(input_x)+len(input_y)) * get_audio_sim_threshold()/2
  N = get_text_sim_threshold((len(input_x)+len(input_y))/2, character_level)
  edit_dist = Levenshtein.distance(input_x, input_y)
  # print(N, edit_dist)
  if return_dist:
    return edit_dist<=N, edit_dist
  return edit_dist<=N

# if substring in all_text:
def is_similar_text_substring(all_text, substring, character_level=True, return_dist=False):
  if not character_level:
    all_text = all_text.split()
    substring = substring.split()
  if len(substring)==0:
    if return_dist:
      return True, 0
    return True
  if len(all_text)==0:
    if return_dist:
      return False, len(substring)
    return False
  if substring in all_text:
    if return_dist:
      return True, 0
    return True

  # N = len(substring) * get_audio_sim_threshold()
  N = get_text_sim_threshold(len(substring), character_level)
  n, lcs, pos = lcsequence_dp(all_text, substring, return_seq=True)
  # print(">>>", lcs, N, len(substring) - n, pos)
  edit_dist = Levenshtein.distance(all_text, substring)

  i, j = 0, len(pos)-1
  target = None
  for i in range(len(pos)):
    for j in range(i, len(pos)):
      tmp = Levenshtein.distance(all_text[pos[i]:pos[j]+1], substring)
      if tmp<edit_dist:
        target = all_text[pos[i]:pos[j]+1]
        edit_dist = tmp

  if return_dist:
    return edit_dist<=N, edit_dist
  return edit_dist<=N

# Sørensen–Dice coefficient
def set_similarity(label1, label2):
  a = set(label1)
  b = set(label2)
  if len(a) + len(b) == 0:
    return 1
  return 2*len(a.intersection(b)) / (len(a)+len(b))


# ==========================================================
# =================== wrapper across_sw_API ==========================
# ==========================================================

def examine_file(transcript, filter_labels, exact_match, and_relation=False):
  flags = []
  cond = []
  for filter in filter_labels:
    if (not exact_match and filter.lower() in transcript.lower()) or (exact_match and filter == transcript):
      flags.append(True)
      cond.append(filter)
    else:
      flags.append(False)
  if (and_relation and all(flags)) or (not and_relation and any(flags)):
    return True, cond
  return False, cond

def check_close_text(transcript, examine_group, em, ar=False, return_dist=False):
  flags = []
  dists = []
  for filter in examine_group:
    if em:
      flag, dist = is_similar_text(transcript.lower(), filter.lower(), return_dist=True)
      flags.append(flag)
      dists.append(dist)
    else:
      flag, dist = is_similar_text_substring(transcript.lower(), filter.lower(), return_dist=True)
      flags.append(flag)
      dists.append(dist)
  if (ar and all(flags)) or (not ar and any(flags)):
    if return_dist:
      return True, dists
    return True
  else:
    if return_dist:
      return False, dists
    return False

def check_mismatch_failure_text(ml_output, groups, exact_match):
  if len(groups) <= 1:
    return None
  failure = Failure()

  match_others = False
  close_branches = []
  branch_dist = [9999]
  suspect_cond = []
  for no, group in enumerate(groups):
    if len(group)==1 and "default" in group:
      continue
    passed, condition_list = examine_file(ml_output, group, exact_match=exact_match)
    if passed:
      failure.type = FailureCode.INCORRECT_CROSS_API_SW
      failure.corrected_API_output = SolutionCode.CLUSTER
      failure.fixing_suggestion = condition_list
      return failure
    flag, dists = check_close_text(ml_output, group, exact_match, return_dist=True)
    if flag:
      dist = min(dists)
      cond = group[dists.index(dist)]
      if min(branch_dist)>dist:
        branch_dist = [dist]
        close_branches = [no]
        suspect_cond = [cond]
      elif min(branch_dist)==dist:
        branch_dist.append(dist)
        close_branches.append(no)
        suspect_cond.append(cond)

  if len(close_branches) == 1:
    failure.type = FailureCode.INCORRECT_CROSS_API_SW
    failure.fixing_suggestion = SolutionCode.CLUSTER
    failure.corrected_API_output = suspect_cond[0]
  elif len(close_branches) > 1:
    failure.type = FailureCode.INCORRECT_CROSS_API_SW
    failure.fixing_suggestion = SolutionCode.REPORT
    # failure.corrected_API_output = suspect_cond
  else:
    failure = None
  return failure


def check_across_sw_API(ml_result, cf_structure):
  conditions = cf_structure["conditions"]
  failures = []
  for task in [MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT, MlTask.SPEECH_REC]:
    if task in ml_result.keys() and task in conditions.keys():
      ml_output = ml_result[task]
      examine_groups = conditions[task]
      if isinstance(ml_output, list): # for MlTask.SPEECH_REC
        ml_output = " ".join(ml_output)
      exact_match = cf_structure["exact_match"]
      failure = check_mismatch_failure_text(ml_output, examine_groups, exact_match)
      if not failure is None and not failure.type is None:
        failure.API = task
        failures.append(failure)
  return failures

# ==========================================================
# =================== wrapper across_input==========================
# ==========================================================
def is_image_path(input_value):
  input_value = input_value.lower()
  if not os.path.exists(input_value):
    return False
  tmp = os.path.splitext(input_value)[-1]
  if tmp in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".raw"]:
    return True
  return False

def check_img_similarity(input_A, input_B):
  try:
    if not is_image_path(input_A) or not is_image_path(input_B):
      logging.info('Cannot detect input image of ML API')
      return False
    return is_similar_image(input_A, input_B)
  except:
    return False

def check_text_similarity(input_A, input_B):
  try:
    N = len(input_A) + len(input_B)
    if N < 100: 
      return is_similar_text(input_A, input_B)
    else: #use a faster approach
      a = input_A.split()
      b = input_B.split()
      return set_similarity(a,b)>0.9
  except:
    return False

def correspond_branch_no(ml_result, branches):
  for no, branch in enumerate(branches):
    if branch == [""]:
      continue
    for keyword in branch:
      for label in ml_result:
        if keyword in label.lower():
          return no
  return -1

def correspond_branch_items(ml_result, branches):
  result = []
  for no, branch in enumerate(branches):
    if branch == [""]:
      continue
    result.append(0)
    for label in ml_result:
      for keyword in branch:
        if keyword in label.lower():
          result[-1] += 1
          break
  return result


def check_across_input(ml_inputs, ml_results_origin, ml_results, cf_structure, history_num):
  failures = []
  num = min(history_num, len(ml_inputs), len(ml_results))
  checked_ml_inputs = ml_inputs[-num:]
  checked_ml_results = ml_results[-num:]
  checked_ml_results_origin = ml_results_origin[-num:]
  none_index = [no for no in range(len(checked_ml_results)) if checked_ml_results[no] is None]
  checked_ml_inputs = [checked_ml_inputs[no] for no in range(len(checked_ml_inputs)) if not no in none_index]
  checked_ml_results = [checked_ml_results[no] for no in range(len(checked_ml_results)) if not no in none_index]
  checked_ml_results_origin = [checked_ml_results_origin[no] for no in range(len(checked_ml_results_origin)) if not no in none_index]
  if len(checked_ml_inputs) <= 1 or len(checked_ml_results) <= 1:
    return []

  for no in range(len(checked_ml_inputs)):
    checked_ml_inputs[no] = helper.extract_ml_input_content(checked_ml_inputs[no], id=no)

  history_size = len(checked_ml_inputs)
  input_sims = [[]] * (history_size-1) #[history-1][var]
  tasks = list(ml_results[-1].keys())
  for task in tasks:
    if task in [MlTask.VISION_LABEL, MlTask.VISION_OBJECT, MlTask.VISION_FACE, MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT, MlTask.VISION_WEB, MlTask.VISION_LAND, MlTask.VISION_LOGO]:
      for no in range(history_size-1):
        similarity = check_img_similarity(checked_ml_inputs[no], checked_ml_inputs[-1])
        input_sims[no].append(similarity)
      break
  for task in tasks:
    if task in [MlTask.LANG_CLASS]:
      for no in range(history_size-1):
        similarity = check_text_similarity(checked_ml_inputs[no], checked_ml_inputs[-1])
        input_sims[no].append(similarity)
      break

  input_sims = [all(x) for x in input_sims]
  # no similar inputs
  if not any(input_sims):
    return []
  
  # filter similar ones
  tmp = []
  tmp2 = []
  similar_inputs = []
  for no in range(len(input_sims)):
    if input_sims[no]:
      tmp.append(checked_ml_results[no])
      tmp2.append(checked_ml_results_origin[no])
      similar_inputs.append(checked_ml_inputs[no])
  tmp.append(checked_ml_results[-1])
  tmp2.append(checked_ml_results_origin[-1])
  similar_inputs.append(checked_ml_inputs[-1])
  ml_results = tmp
  ml_results_origin = tmp2

   # control flow
  conditions = cf_structure["conditions"]
  control_sims = [[]] * (history_size-1) #[history-1][task]
  for task in tasks:
    if task in [MlTask.VISION_LABEL, MlTask.VISION_WEB, MlTask.VISION_LAND, MlTask.VISION_LOGO, MlTask.LANG_CLASS] and task in conditions.keys():
      branches = conditions[task]
      for no in range(history_size-1):
        similarity = correspond_branch_no(ml_results[no][task], branches) == correspond_branch_no(ml_results[-1][task], branches)
        control_sims[no].append(similarity)
    if task in [MlTask.VISION_OBJECT] and task in conditions.keys():
      branches = conditions[task]
      for no in range(history_size-1):
        similarity = correspond_branch_items(ml_results[no][task], branches) == correspond_branch_no(ml_results[-1][task], branches)
        control_sims[no].append(similarity)
  control_sims = [all(x) for x in control_sims]
  if (sum(control_sims)/len(control_sims))>=1:
    return []

  # data flow
  output_sims = [[]] * (history_size-1) #[history-1][task]
  for task in tasks:
    if task in [MlTask.VISION_FACE]:
      for no in range(history_size-1):
        similarity = len(ml_results[no][task]) == len(ml_results[-1][task])
        output_sims[no].append(similarity)
    if task in [MlTask.VISION_OBJECT]:
      for no in range(history_size-1):
        similarity = len(ml_results[no][task]) == (ml_results[-1][task])
        output_sims[no].append(similarity)
    # dataflow
    if task in [MlTask.VISION_LABEL, MlTask.VISION_OBJECT, MlTask.VISION_WEB, MlTask.VISION_LAND, MlTask.VISION_LOGO, MlTask.LANG_CLASS]:
      for no in range(history_size-1):
        similarity = set_similarity(ml_results[no][task],ml_results[-1][task]) >= 0.7
        output_sims[no].append(similarity)
    if task in [MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT]:
      for no in range(history_size-1):
        similarity = check_text_similarity(ml_results[no][task],ml_results[-1][task])
        output_sims[no].append(similarity)
  

  for no, task in enumerate(tasks):
    sims = [x[no] for x in output_sims]
    if (sum(sims)/len(sims))<=0.5:
      failure = Failure()
      failure.type = FailureCode.INCORRECT_CROSS_API
      failure.API = task
      if task in [MlTask.VISION_OBJECT, MlTask.VISION_FACE, MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT]: # or connect to camera
        failure.fixing_suggestion = SolutionCode.TEMPORAL
        failure.similar_inputs = similar_inputs
      else:
        failure.fixing_suggestion = SolutionCode.ENSEMBLE
        if task in [MlTask.VISION_LABEL, MlTask.VISION_WEB, MlTask.VISION_LAND, MlTask.VISION_LOGO, MlTask.LANG_CLASS] and task in conditions.keys():
          branches = conditions[task]
          cf_decision = []
          for no in range(history_size):
            cf_decision.append(correspond_branch_no(ml_results[no][task], branches))
          tmp_list = cf_decision.copy()
          sorted(tmp_list,key=tmp_list.count)
          correct = tmp_list[0]
          failure.corrected_API_output = ml_results_origin[cf_decision.index(correct)][task]
          # if correct is not the only most common, we do no have any way to vote
          if tmp_list.count(correct) < len(tmp_list):
            second_common = tmp_list[tmp_list.count(tmp_list[0])]
            if tmp_list.count(correct) <= tmp_list.count(second_common):
              failure.fixing_suggestion = SolutionCode.REPORT
              failure.corrected_API_output = None
          
      failures.append(failure)

  return failures

# ==========================================================
# =================== wrapper across API ==========================
# ==========================================================
def related_to_conditions(label, conditions):
  for condition in conditions:
    if condition==[""]:
      continue
    for keyword in condition:
      if keyword.lower() in label.lower() or label.lower() in keyword.lower():
        return True
  return False

def related_to_which_condition(text, conditions, exact_match):
  for condition in conditions:
    if condition==[""]:
      continue
    for keyword in condition:
      if (not exact_match and keyword.lower() in text.lower()) or (exact_match and keyword == text):
        return keyword
  return None
  
def check_across_API(ml_result, cf_structure):
  conditions = cf_structure["conditions"]
  failures = []
  performed_tasks = ml_result.keys()

  if {MlTask.VISION_LABEL, MlTask.VISION_OBJECT}.issubset(performed_tasks):
    if len(ml_result[MlTask.VISION_LABEL]) > 0:
      new_web_value = set()
      for label in ml_result[MlTask.VISION_LABEL]:
        if len(label)==0:
          continue
        if any([True for x in ml_result[MlTask.VISION_OBJECT] if (x in label or label in x)]):
          continue
        if related_to_conditions(label, conditions[MlTask.VISION_OBJECT]):
          new_web_value.add(label)
      if len(new_web_value)>0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_OBJECT
        failure.fixing_suggestion = SolutionCode.ENSEMBLE
        tmp = [x.capitalize() for x in new_web_value]
        failure.corrected_API_output = tmp #+ ml_result[MlTask.VISION_OBJECT]
        failures.append(failure)

  if {MlTask.VISION_LABEL, MlTask.VISION_FACE}.issubset(performed_tasks):
    face_list = ["person", "human face", "human eye", "human mouth", "human nose", "human beard", "human ear", "human head", "man", "woman"]
    if len(ml_result[MlTask.VISION_FACE]) > 0:
      new_object_value = set()
      for object in ml_result[MlTask.VISION_LABEL]:
        if len(object)==0:
          continue
        if not any([True for x in ml_result[MlTask.VISION_LABEL] if x.lower() in face_list]):
          new_object_value.add("person")
          new_object_value.add("human")
      if len(new_object_value)>0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_LABEL
        failure.fixing_suggestion = SolutionCode.ENSEMBLE
        tmp = [x.capitalize() for x in new_object_value]
        failure.corrected_API_output = tmp #+ ml_result[MlTask.VISION_LABEL]
        failures.append(failure)
    if any([True for x in ml_result[MlTask.VISION_LABEL] if x.lower() in face_list]):
      if len(ml_result[MlTask.VISION_FACE])==0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_FACE
        failure.fixing_suggestion = SolutionCode.REPORT
        failures.append(failure)

  if {MlTask.VISION_OBJECT, MlTask.VISION_FACE}.issubset(performed_tasks):
    face_list = ["person", "human face", "human eye", "human mouth", "human nose", "human beard", "human ear", "human head", "man", "woman"]
    if len(ml_result[MlTask.VISION_FACE]) > 0:
      new_object_value = set()
      for object in ml_result[MlTask.VISION_OBJECT]:
        if len(object)==0:
          continue
        if not any([True for x in ml_result[MlTask.VISION_OBJECT] if x.lower() in face_list]):
          new_object_value.add("person")
          new_object_value.add("human")
      if len(new_object_value)>0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_OBJECT
        failure.fixing_suggestion = SolutionCode.ENSEMBLE
        tmp = [x.capitalize() for x in new_object_value]
        failure.corrected_API_output = tmp #+ ml_result[MlTask.VISION_OBJECT]
        failures.append(failure)
    if any([True for x in ml_result[MlTask.VISION_OBJECT] if x.lower() in face_list]):
      if len(ml_result[MlTask.VISION_FACE])==0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_FACE
        failure.fixing_suggestion = SolutionCode.REPORT
        failures.append(failure)

  if {MlTask.VISION_LABEL, MlTask.VISION_LAND}.issubset(performed_tasks):
    if len(ml_result[MlTask.VISION_LAND]) > 0:
      new_label_value = set()
      for landmark in ml_result[MlTask.VISION_LAND]:
        if len(landmark)==0:
          continue
        if not any([True for x in ml_result[MlTask.VISION_LAND] if landmark in x]):
          new_label_value.add("landmark")
      if len(new_label_value)>0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_LABEL
        failure.fixing_suggestion = SolutionCode.ENSEMBLE
        tmp = [x.capitalize() for x in new_label_value]
        failure.corrected_API_output = tmp #+ ml_result[MlTask.VISION_WEB]
        failures.append(failure)
    if any([True for x in ml_result[MlTask.VISION_LABEL] if "landmark" in x.lower()]):
      if len(ml_result[MlTask.VISION_LAND])==0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_LAND
        failure.fixing_suggestion = SolutionCode.REPORT
        failures.append(failure)

  if {MlTask.VISION_WEB, MlTask.VISION_LABEL}.issubset(performed_tasks):
    if len(ml_result[MlTask.VISION_LABEL]) > 0:
      new_web_value = set()
      for label in ml_result[MlTask.VISION_LABEL]:
        if len(label)==0:
          continue
        if any([True for x in ml_result[MlTask.VISION_WEB] if (x in label or label in x)]):
          continue
        if related_to_conditions(label, conditions[MlTask.VISION_WEB]):
          new_web_value.add(label)
      # for web in ml_result[MlTask.VISION_WEB]:
      #   if any([True for x in ml_result[MlTask.VISION_LABEL] if (x in web or web in x)]):
      #     continue
      #   _, _, parents = kg.find_parents(web, return_name=True)
      #   parents.append(web)
      #   for label in ml_result[MlTask.VISION_LABEL]:
      #     if not related_to_conditions(label, conditions[MlTask.VISION_WEB]):
      #       continue
      #     if len(label)==0:
      #       continue
      #     if not any([True for x in parents if label in x]):
      #       new_web_value.add(label)
      if len(new_web_value)>0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_WEB
        failure.fixing_suggestion = SolutionCode.ENSEMBLE
        tmp = [x.capitalize() for x in new_web_value]
        failure.corrected_API_output = tmp #+ ml_result[MlTask.VISION_WEB]
        failures.append(failure)

  if {MlTask.VISION_WEB, MlTask.VISION_LOGO}.issubset(performed_tasks):
    if len(ml_result[MlTask.VISION_LOGO]) > 0:
      new_web_value = []
      for logo in ml_result[MlTask.VISION_LOGO]:
        if len(logo)==0:
          continue
        if not any([True for x in ml_result[MlTask.VISION_WEB] if logo in x]):
          new_web_value.append(logo + " logo")
      if len(new_web_value)>0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_WEB
        failure.fixing_suggestion = SolutionCode.ENSEMBLE
        tmp = [x.capitalize() for x in new_web_value]
        failure.corrected_API_output = tmp #+ ml_result[MlTask.VISION_WEB]
        failures.append(failure)
    if any([True for x in ml_result[MlTask.VISION_WEB] if "logo" in x.lower()]):
      if len(ml_result[MlTask.VISION_LOGO])==0:
        failure = Failure()
        failure.type = FailureCode.INCORRECT_CROSS_API
        failure.API = MlTask.VISION_LOGO
        failure.fixing_suggestion = SolutionCode.REPORT

  if {MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT}.issubset(performed_tasks):
    text_related = related_to_which_condition(label, conditions[MlTask.VISION_OBJECT])
    doc_related = related_to_which_condition(label, conditions[MlTask.VISION_OBJECT])
    if text_related != doc_related:
      failure = Failure()
      failure.type = FailureCode.INCORRECT_CROSS_API
      if text_related is None:
        failure.API = MlTask.VISION_TEXT
      else:
        failure.API = MlTask.VISION_DOCUMENT
      failure.fixing_suggestion = SolutionCode.REPORT
         
  return failures


if __name__ == '__main__':
  pass
