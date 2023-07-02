from bytecode import Bytecode, Instr
from collections import deque

import logging, trace, sys, os

from . import helper as helper
from .enum_classes import *
from .status import *
from .diagnoser_config import *
from .global_vars import *
from . import knowledge_graph as kg
from . import similarity as sim
from . import reexecution as reex

logging.basicConfig(level=logging.WARNING)
# logging.basicConfig(level=logging.DEBUG)
    
# Refer to
# https://copypaste.guru/WhereIsMyPythonModule/how-to-fix-modulenotfounderror-no-module-named-bytecode
class Diagnoser(object):
  """
  Decorator that takes a list of variable names as argument. Everytime
  the decorated function is called, the final states of the listed
  variables are logged and can be read any time during code execution.
  """
  _variable_values = {} # func -> value history (list of tuples)
  config = DiagnoserConfig()


  def __init__(self, ml_input=None, info_file=None):
    self.input_params = None # a list of string
    self.ml_input_params = ml_input # a list of string
    # control flow structure. info_file should be auto generated with tool inside ./control_flow_analysis
    if info_file is None:
      self.ml_tasks, self.cf_structure = None, None
    else:
      self.ml_tasks, self.cf_structure = helper.read_structure_from_json(info_file)
      self.input_params, self.ml_input_params = helper.read_func_data_from_json(info_file)
    self.history = {}

  def __call__(self, func):
    self.func = func
    if self.input_params is None:
      self.input_params = func.__code__.co_varnames[:func.__code__.co_argcount]
    if self.ml_input_params is None:
      if len(self.input_params) == 1:
        self.ml_input_params = self.input_params
      else:
        self.ml_input_params = []

    if self.ml_tasks is None:
      Diagnoser.config.stop_diagnose()
    elif len(self.ml_tasks)==0:
      Diagnoser.config.stop_diagnose()
    
    self.add_variable_inspector(func)
    
    def wrapper(*args, **kwargs):
      status = Status()
      try:
        logging.debug("============= Execution Info ============")
        res = func(*args, **kwargs)
        logging.debug("Result:" + str(res))
        logging.debug("============= After execution ============")
      except Exception as e:
        logging.warning("Function <{}> has an exception: {}".format(func.__name__, str(e)))
        status.exception = str(e)
        status.type = StatusCode.CRASH
        return None
      # res = func(*args, **kwargs)

      return res

    return wrapper
  
  def add_variable_inspector(self, func):
    # Refer to https://stackoverflow.com/questions/52313851/how-can-i-track-the-values-of-a-local-variable-in-python

    TRACKED_ML_APIS = Vision_API + Speech_API + Language_API

    c = Bytecode.from_code(func.__code__)
    
    def get_inspect_code(origin_var, c_status):
      if origin_var is None:
        return []
      record_vars = [origin_var] + c_status["params"] + self.ml_input_params
      extra_code = [Instr('STORE_FAST', origin_var)]+ \
        [ Instr('LOAD_FAST', name) for name in record_vars]+ \
        [
          Instr('BUILD_TUPLE', len(record_vars)),
          Instr('STORE_FAST', '_debug_tuple'),
          Instr('LOAD_CONST', self),
          Instr('LOAD_CONST', c_status["api_name"]),
          Instr('LOAD_CONST', c_status["lineno"]),
          Instr('LOAD_CONST', c_status["params"]),
          Instr('LOAD_CONST', c_status["params_name"]),
          Instr('LOAD_FAST', '_debug_tuple'),
          Instr('BUILD_TUPLE', 6),
          Instr('STORE_FAST', '_result_tuple'),
          
          Instr('LOAD_GLOBAL', 'Diagnoser'),
          Instr('LOAD_METHOD', 'check_failure'),
          Instr('LOAD_FAST', '_result_tuple'),
          Instr('CALL_FUNCTION', 1),
          Instr('STORE_FAST', '_res'),
          Instr('LOAD_FAST', '_res'),
        ]
      return extra_code
    
    no = 0
    code_status = {"ml_api": False, "api_name": None, "params": [], "params_name": [], "lineno": -1}
    while no < len(c):
      c_line = c[no]
      # print(c_line)
      if isinstance(c_line, Instr):
        if code_status["lineno"] != c_line.lineno:
          code_status = {"ml_api": False, "api_name": None, "params": [], "params_name": [], "lineno": c_line.lineno}
        
        if c_line.name == "LOAD_ATTR" and c_line.arg in TRACKED_ML_APIS:
          code_status["ml_api"] = True
          code_status["api_name"] = c_line.arg
        if c_line.name == "LOAD_FAST" or c_line.name == "LOAD_CONST":
          if code_status["ml_api"]:
            if isinstance(c_line.arg, tuple):
              code_status["params_name"].append(c_line.arg[0])
            else:
              code_status["params"].append(c_line.arg)

        if c_line.name == "CALL_FUNCTION_KW":
          if code_status["ml_api"]:
            if no+1<len(c) and c[no+1].name == "STORE_FAST":
              # print("here", code_status)
              extra_code = get_inspect_code(c[no+1].arg, code_status)
              c[no+1:no+1]= extra_code
              no += len(extra_code)
      no += 1
    func.__code__=c.to_code()
    return

  
  @staticmethod
  def check_failure(values):
    diagnoser, api_name, line_no, api_params_var, api_params_name, results = values
    ml_api_value = results[0]
    api_params = results[1:len(api_params_var)+1]
    func_params = results[len(api_params_var)+1:]
    ml_task = parse_api_to_enum(api_name)
    if not line_no in diagnoser.history.keys():
      diagnoser.history[line_no] = deque(maxlen=Diagnoser.config.check_history_num)
    results_structured = API_INVOKE_INFO(ml_api_value=ml_api_value, api_params=api_params, func_params=func_params, ml_task=ml_task, api_params_var=api_params_var, api_params_name=api_params_name)
    diagnoser.history[line_no].append(results_structured)
 
    ml_results_origin, ml_results = Diagnoser.get_ml_result(diagnoser.history[line_no], ml_task)
    status = Status()
    if not ml_results is None and len(ml_results)>=1 and not ml_results[-1] is None:
      ml_result = ml_results[-1]
      contains_cond, fulfill = helper.fulfill_ml_branch_cond(diagnoser.cf_structure, ml_task, ml_result)
      if Diagnoser.config.resolve_mismatch:
        if contains_cond and not fulfill:
          failures = kg.check_mismatch_failure(ml_result, diagnoser.cf_structure)
          if len(failures) > 0:
            status.type = StatusCode.ACCURACY_FAILURE
            status.failures += failures
            for failure in failures:
              if failure.API == ml_task:
                if failure.fixing_suggestion == SolutionCode.CLUSTER and not failure.corrected_API_output is None:
                  ml_api_value = helper.change_api_result(ml_task, ml_api_value, failure.corrected_API_output)
                elif failure.fixing_suggestion == SolutionCode.SEGMENT:
                  new_result = reex.segementation(ml_task, api_params, api_params_name)
                  if not new_result is None:
                    ml_api_value = new_result
                elif failure.fixing_suggestion == SolutionCode.REPORT:
                  logging.warning("[Failure warning] In Function <{}>, ML API <{}> is not able to perfom the recognition task in the same perspective as software".format(diagnoser.func.__name__, api_name))

      if Diagnoser.config.validate_across_input and Diagnoser.config.check_history_num>1:
        ml_inputs = Diagnoser.get_ml_input(diagnoser.history[line_no])
        failures = sim.check_across_input(ml_inputs, ml_results_origin, ml_results, diagnoser.cf_structure, Diagnoser.config.check_history_num)
        if len(failures) > 0:
          status.type = StatusCode.ACCURACY_FAILURE
          status.failures += failures
          for failure in failures:
            if failure.API == ml_task:
              if failure.fixing_suggestion == SolutionCode.ENSEMBLE and not failure.corrected_API_output is None:
                ml_api_value = helper.change_api_result(ml_task, ml_api_value, failure.corrected_API_output)
              elif failure.fixing_suggestion == SolutionCode.TEMPORAL:
                new_result = reex.call_video_api(ml_task, failure.similar_inputs, ml_api_value)
                if not new_result is None:
                  ml_api_value = new_result
              elif failure.fixing_suggestion == SolutionCode.REPORT:
                logging.warning("[Failure warning] In Function <{}>, ML API <{}> probably provides an incorrect result".format(diagnoser.func.__name__, api_name))

      if Diagnoser.config.validate_across_API and len(diagnoser.history.keys())>1:
        ml_result_current_run = Diagnoser.get_ml_result_current_run(diagnoser.history, results_structured)
        failures = sim.check_across_API(ml_result_current_run, diagnoser.cf_structure)
        if len(failures) > 0:
          status.type = StatusCode.ACCURACY_FAILURE
          status.failures += failures
          for failure in failures:
            failure_api_name = helper.parse_enum_to_api(failure.API)
            if failure.fixing_suggestion == SolutionCode.ENSEMBLE and not failure.corrected_API_output is None:
              if failure.API == ml_task:
                ml_api_value = helper.change_api_result(ml_task, ml_api_value, failure.corrected_API_output)
              else:
                logging.warning("[Failure warning] In Function <{}>, ML API <{}> probably provides an incorrect result. Consider call ML API <{}> earlier than ML API <{}>, so SmartGear could automatically fix it.".format(diagnoser.func.__name__, failure_api_name, api_name, failure_api_name))
            elif failure.fixing_suggestion == SolutionCode.REPORT:
              logging.warning("[Failure warning] In Function <{}>, ML API <{}> probably provides an incorrect result".format(diagnoser.func.__name__, failure_api_name))

      if Diagnoser.config.validate_across_sw_API:
        if contains_cond and not fulfill:
          failures = sim.check_across_sw_API(ml_result, diagnoser.cf_structure)
          if len(failures) > 0:
            status.type = StatusCode.ACCURACY_FAILURE
            status.failures += failures
            for failure in failures:
              if failure.API == ml_task:
                if failure.fixing_suggestion == SolutionCode.CLUSTER and not failure.corrected_API_output is None:
                  ml_api_value = helper.change_api_result(ml_task, ml_api_value, failure.corrected_API_output)
                elif failure.fixing_suggestion == SolutionCode.REPORT:
                  logging.warning("[Failure warning] In Function <{}>, ML API <{}> probably provides an incorrect result".format(diagnoser.func.__name__, api_name))

    return ml_api_value

  
  @staticmethod
  def get_ml_result(values, ml_api):
    ml_values = []
    ml_values_origin = []
    for i, value in enumerate(values):
      ml_api_value = value.ml_api_value
      ml_value = helper.extract_ml_api_result(ml_api_value, [ml_api])
      ml_values_origin.append(ml_api_value)
      ml_values.append(helper.parse_ml_value(ml_value))
    return ml_values_origin, ml_values

  @staticmethod
  def get_ml_input(values):
    if len(values)==0:
      return []
    main_input_index = None
  
    ml_task = values[0].ml_task
    api_params_var = values[0].api_params_var
    api_params_name = values[0].api_params_name

    if ml_task in [MlTask.VISION_LABEL, MlTask.VISION_OBJECT, MlTask.VISION_FACE, MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT, MlTask.VISION_WEB, MlTask.VISION_LAND, MlTask.VISION_LOGO]:
      for no in range(len(api_params_name)-1, -1, -1):
        para_name = api_params_name[no]
        if para_name == "image":
          main_input_index = len(api_params_var)-len(api_params_name)+no
          break
      if main_input_index is None:
        main_input_index = 0
    elif ml_task in [MlTask.LANG_CLASS, MlTask.LANG_SENTI, MlTask.LANG_ENTITY]:
      for no in range(len(api_params_name)-1, -1, -1):
        para_name = api_params_name[no]
        if para_name == "document":
          main_input_index = len(api_params_var)-len(api_params_name)+no
          break
      if main_input_index is None:
        main_input_index = 0
    elif ml_task in [MlTask.SPEECH_REC, MlTask.SPEECH_LONG, MlTask.SPEECH_STREAM]:
      for no in range(len(api_params_name)-1, -1, -1):
        para_name = api_params_name[no]
        if para_name == "audio":
          main_input_index = len(api_params_var)-len(api_params_name)+no
          break
      if main_input_index is None:
        main_input_index = 1

    ml_inputs = []
    for i, value in enumerate(values):
      api_params = value.api_params
      ml_inputs.append(api_params[main_input_index])
    return ml_inputs
  
  @staticmethod
  def get_ml_result_current_run(execution_history, results_structured):
    ml_value = {}
    ml_input_value = helper.extract_ml_input_content_exact_value(Diagnoser.get_ml_input([results_structured])[0])
    for line_no, values in execution_history.items():
      if len(values) == 0:
        continue
      this_value = values[-1]
      this_ml_input_value = helper.extract_ml_input_content_exact_value(Diagnoser.get_ml_input([this_value])[0])
      this_ml_api_value = this_value.ml_api_value
      if ml_input_value==this_ml_input_value:
        this_ml_value_tmp = helper.extract_ml_api_result(this_ml_api_value, [this_value.ml_task])
        ml_value[this_value.ml_task] = helper.parse_ml_value(this_ml_value_tmp)[this_value.ml_task]
    return ml_value



class API_INVOKE_INFO(object):
  def __init__(self, 
                ml_api_value=None,
                api_params=None,
                func_params=None,
                ml_task=None,
                api_params_var=None,
                api_params_name=None,
                ):
    self.ml_api_value = ml_api_value
    self.api_params = api_params
    self.func_params = func_params
    self.ml_task = ml_task
    self.api_params_var = api_params_var
    self.api_params_name = api_params_name
