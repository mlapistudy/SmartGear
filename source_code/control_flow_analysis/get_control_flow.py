import os
import sys
import subprocess
import json
import logging
import argparse
import collections
from pathlib import Path
import jedi

from global_vars import *
import change_code as change_code
import constraint_solving as solve
from code_extraction.extract import Extractor

logger = logging.getLogger(__name__)

def run_command(command):
  proc = subprocess.Popen(command, shell=True)
  proc.wait()

def get_line_map(input_file, test_file, If_statement_changes, func_name):
  func_def_line = -1
  line_map = {}  # test_file -> input file, only for and if statements
  # force start with line 1
  content_input = [""] + change_code.read_wholefile(input_file, preprocess=True).split("\n")
  content_test = [""] + change_code.read_wholefile(test_file, preprocess=False).split("\n")
  cur_loc = 1
  for line_no, code in enumerate(content_input):
    if code.strip().startswith("def "+func_name+"("):
      func_def_line = line_no
    if code in If_statement_changes.keys():
      revised_code = If_statement_changes[code]
      while cur_loc < len(content_test):
        if revised_code == content_test[cur_loc]:
          break
        cur_loc += 1
      if cur_loc<len(content_test):
        line_map[cur_loc] = line_no
      else:
        logging.warning("Cannot find corresponding location of code: " + code)  
  return line_map, func_def_line


def print_tuples_with_arrow(ml_keywords):
  result = ""
  for api, keyword in ml_keywords:
    result += str(api) + " -> " + str(keyword) + "; "
  return result

def print_ml_keyword(ml_keywords):
  result = []
  for api, keyword in ml_keywords:
    result.append(str(keyword))
  return " and ".join(result)

def change_code_lines(curr_line_of_code, curr_func_def_line, ori_func_def_line, ori_empty_lines):
  curr_lines_of_code = [curr_line_of_code]
  to_remove = []
  for entry in ori_empty_lines:
      if entry < ori_func_def_line:
          to_remove.append(entry)
  for entry in to_remove:
      ori_empty_lines.remove(entry)

  if ori_empty_lines == []:
      return [i - curr_func_def_line + ori_func_def_line for i in curr_lines_of_code][0]

  # change_dict stores the following information:
  # from which line -> needs to append how many new lines
  change_dict = {}
  total_empty_lines = 0
  i = 0
  while i < len(ori_empty_lines):
      if i == 0:
          curr_pos = ori_empty_lines[i] - ori_func_def_line
          total_empty_lines += 1
      # still an empty line
      elif ori_empty_lines[i] == ori_empty_lines[i - 1] + 1:
          total_empty_lines += 1
      # no longer an empty line
      else:
          change_dict[curr_pos] = total_empty_lines
          curr_pos = ori_empty_lines[i] - total_empty_lines - ori_func_def_line
          total_empty_lines += 1
      i += 1
  change_dict[curr_pos] = total_empty_lines
  logger.debug(f"change_dict computed to be {change_dict}")

  res = []
  for i in curr_lines_of_code:
      diff = i - curr_func_def_line
      upper_j = -1
      for j in change_dict:
          if diff >= j and j > upper_j:
              upper_j = j
      if upper_j == -1:
          res.append(i - curr_func_def_line + ori_func_def_line)
      else:
          res.append(i - curr_func_def_line + ori_func_def_line + change_dict[upper_j])
  return res[0]

def check_log(log_file, ml_related_vars):
  sw_context = {"conditions":{}, "exact_match": False, "exclusive": True, "loop_order": "unknown"}
  # conditions = [[str,...],...]
  # exact_match: looking for substring or an exact equal
  # exclusive: are branches exclusive with each other?
  # loop_order = "label loop first", "whitelist loop first"

  def contain_ml_output(code):
    all_names = jedi.Script(code).get_names(all_scopes=True, definitions=True, references=True)
    for name in all_names:
      if name.name in ml_related_vars:
        return True
    return False
  
  with open(log_file, "r") as read_content:
    log_info = json.load(read_content)
  Path2Keyword = collections.defaultdict(list)
  ml_apis = set()
  for execution in log_info["exe"]:
    ml_apis = execution["ML_input"].keys()
    ML_input = execution["ML_input"]
    path = execution["path"]
    path = str(sorted(set(path)))
    Path2Keyword[path].append(ML_input)
  
  for ml_api in ml_apis:
    sw_context["conditions"][ml_api] = []
    for key, value in Path2Keyword.items():
      branch_condition = [x[ml_api]["keyword"] for x in value]
      branch_condition = list(set(branch_condition))
      sw_context["conditions"][ml_api].append(branch_condition)

  # check exact match
  for i, execution in enumerate(log_info["exe"]):
    origin_path = execution["path"]
    alter_path = log_info["exe_vary"][i]["path"]
    if not origin_path==alter_path:
      sw_context["exact_match"] = True
      break
  
  # check statement is related to ML output or not
  contains_ml_for = False
  for for_state in log_info["for_lines"]:
    for_code = for_state["code"]
    for_state["ml_related"] = False
    if contain_ml_output(for_code):
      for_state["ml_related"] = True
      contains_ml_for = True
    for if_state in for_state["if_lines"]:
      if_code = if_state["code"]
      if_state["ml_related"] = False
      if contain_ml_output(if_code):
        if_state["ml_related"] = True

  # check loop priority - coarse checking
  # whitelist["loop_order"] = "label loop first"
  sw_context["loop_order"] = "unknown"
  # case1: without for ML related loop
  # e.g., Aander-ETL - any([l in L1 for l in desc])
  # e.g., only has for loop of whitelist
  if not contains_ml_for:
    sw_context["loop_order"] = "whitelist loop first"
  # case2: has for loop related to ML, check whether its inside has non-ML loop/if
  # this may fail on some complicated cases
  if sw_context["loop_order"]=="unknown":
    sw_context["loop_order"] = "label loop first"
    for for_state in log_info["for_lines"]:
      if for_state["ml_related"]:
        # print(for_state)
        for for_state_2 in log_info["for_lines"]:
          for_state_2["indent"] > for_state["indent"]
          if for_state_2["indent"] > for_state["indent"] and not for_state["ml_related"]:
            sw_context["loop_order"] = "whitelist loop first"
          if for_state_2["indent"] <= for_state["indent"]:
            break

  # a coarse check of breaking
  # only works for simple functions, and may mistakes on others outside benchmark
  sw_context["exclusive"] = True
  if sw_context["loop_order"]=="label loop first":
    for for_state in log_info["for_lines"]:
      if_states = for_state["if_lines"]
      if len(if_states)==0 or not for_state["ml_related"]:
        continue
      closest_if_state = min([x["line_no"] for x in if_states])
      # in non-otherwise case, check wether for-if executed for multiple times
      # if so, then indicating no breaks
      for execution in log_info["exe"]:
        keywords = [x["keyword"] for x in execution["ML_input"].values()]
        path = execution["path"]
        if "".join(keywords) == "":
          continue
        if path.count(for_state["line_no"])>1 and path.count(closest_if_state)>1:
          sw_context["exclusive"] = False
  if sw_context["loop_order"]=="whitelist loop first":
    # examine whether it always check every if-condition
    if_inside_loop = set()
    for for_state in log_info["for_lines"]:
      for if_state in for_state["if_lines"]:
        if contain_ml_output(if_state["code"]):
          if_inside_loop.add(if_state["line_no"])
    paths_all_ifs = 0
    for execution in log_info["exe"]:
      executed_path = set(execution["path"])
      if if_inside_loop.issubset(executed_path):
        paths_all_ifs += 1
    # we could loose the requirement
    if paths_all_ifs == len(executed_path):
      sw_context["exclusive"] = False
  
  sw_context.pop("loop_order", None) # no longer used
  sw_context["control_flow"] = log_info["for_lines"]
  return sw_context

# all code lines are start with 1
def apply_test(file_name, json_data, output_file=None):
  function_name = json_data["func_name"]
  if not os.path.exists(file_name):
    print("[Error] " + file_name + " not found.")
  file_name = os.path.abspath(file_name)

  test_file_dir = os.path.dirname(os.path.realpath(file_name))
  constraint_file = os.path.join(test_file_dir, "__constraint_solving.py")
  change_code.change(file_name, constraint_file, function_name) # comment for test only
  used_ml_api, ml_api_to_input, output_to_ml_api, If_statement_changes= solve.get_ml_api(constraint_file)

  log_file = os.path.join(test_file_dir, "__exe_path.json")
  # or use solve_precondition_full.py instead of solve_multi.py
  cmd = "python3 constraint_solving.py --m=25 --start=" +function_name+ " -o " +log_file+ " " + constraint_file
  run_command(cmd) # comment for test only

  ml_related_vars = output_to_ml_api.keys()
  test_file = os.path.join(test_file_dir, "__cov_test.py")
  line_map, func_def_line_in_extracted_function = get_line_map(file_name, test_file, If_statement_changes, json_data["func_name"])
  
  if output_file == None:
    output_file = os.path.join(test_file_dir, "output.json")

  sw_context = check_log(log_file, ml_related_vars)
  
  sw_context["func_info"] = json_data
  all_code = change_code.read_wholefile(file_name)
  for code in all_code.split("\n"):
    if code.strip().startswith("def "+json_data["func_name"]+"("):
      def_code = code
      name, params, default_value = change_code.extract_function_info(def_code)
      sw_context["func_info"]["input_param"] = params
      break

  # re-map functions to their original location
  f3_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "code_extraction", "function_mapping.json")
  f4_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "code_extraction", "empty_line.json")
  if os.path.exists(f3_filename):
    logger.info(f"found function mapping at {f3_filename}, processing")
    with open(f3_filename, "r") as f3:
      func_mapping_dict = json.load(f3)
    with open(f4_filename, "r") as f4:
      empty_line_dict = json.load(f4)

    for for_state in sw_context["control_flow"]:
      if for_state["line_no"]<0:
        continue
      for_state["line_no"] = line_map[for_state["line_no"]]
      for if_state in for_state["if_lines"]:
        origin = if_state["line_no"]
        if_state["line_no"] = line_map[if_state["line_no"]]
        fix = if_state["line_no"] - origin
        if_state["then_line"] += fix

      curr_func_name = json_data["func_name"]
      curr_func_def_line = func_def_line_in_extracted_function
      query_key = f"{curr_func_name},{curr_func_def_line}"
      if query_key in func_mapping_dict:
        logger.info(f"found {query_key} in func_mapping_dict json file, changing relevant parameters in bug output")
        ori_file_name = func_mapping_dict[query_key][0]
        ori_func_def_line = func_mapping_dict[query_key][1]
        if ori_file_name != json_data["code_file"]:
          continue        
        if ori_file_name in empty_line_dict:
          ori_line_of_code = for_state["line_no"]
          for_state["line_no"] = change_code_lines(ori_line_of_code, curr_func_def_line, ori_func_def_line, empty_line_dict[ori_file_name])
          for if_state in for_state["if_lines"]:
            ori_line_of_code = if_state["line_no"]
            if_state["line_no"] = change_code_lines(ori_line_of_code, curr_func_def_line, ori_func_def_line, empty_line_dict[ori_file_name])
            ori_line_of_code = if_state["then_line"]
            if_state["then_line"] = change_code_lines(ori_line_of_code, curr_func_def_line, ori_func_def_line, empty_line_dict[ori_file_name])
      else:
        logger.warning(f"query_key {query_key} does not exist in function mapping json file. This indicates that the functions processed by all_wrap_up.py were not properly processed by extract.py")

  
  with open(output_file, "w") as f:
    f.write(json.dumps(sw_context, sort_keys=False, indent=4))


def execute_from_json(json_file_path, output_path, log_file_path):
  """
    Wraps all processing from plugin-outputed json file
  """
  logging.basicConfig(level=logging.WARNING, filename=log_file_path, filemode="w")
  # logging.basicConfig(level=logging.DEBUG, filename=log_file_path, filemode="w")
  logging.getLogger("parso.python.diff").disabled = True
  logging.getLogger().addHandler(logging.StreamHandler())

  e = Extractor(json_file_path)

  # These are a bunch of files that could have been generated from multiple testing
  log_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testing_logs")
  if not os.path.isdir(log_folder):
    os.makedirs(log_folder)
  extracted_file_path = os.path.join(log_folder, "extracted_function.py")

  e.extract(extracted_file_path, True)
  apply_test(extracted_file_path, e.json_data, output_file=output_path)


def main():
  parser=argparse.ArgumentParser(description="schema")
  # arguments for file
  parser.add_argument("--input_json", help="plugin input json file", type=str, required=True)
  parser.add_argument("--output_json", help="tool output json file for plugin", type=str, required=True)
  parser.add_argument("--log_file", help="log file output for plugin", type=str, required=True)

  args=parser.parse_args()
  execute_from_json(args.input_json, args.output_json, args.log_file)



if __name__ == '__main__':
  main()
