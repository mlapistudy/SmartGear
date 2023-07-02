class DiagnoserConfig(object):
  def __init__(self, 
                diagnose=True,
                resolve_mismatch=True, 
                validate_across_input=False, 
                validate_across_API=False, 
                validate_across_sw_API = True
                ):
    self.diagnose = diagnose
    self.resolve_mismatch = resolve_mismatch
    self.validate_across_input = validate_across_input
    self.validate_across_API = validate_across_API
    self.validate_across_sw_API = validate_across_sw_API
    self.check_history_num = 3
    if not diagnose:
      self.stop_diagnose()

  def stop_diagnose(self):
    self.diagnose = False
    self.resolve_mismatch = False
    self.validate_across_input = False
    self.validate_across_API = False
    self.validate_across_sw_API = False

  def start_all_diagnose(self):
    self.diagnose = True
    self.resolve_mismatch = True
    self.validate_across_input = True
    self.validate_across_API = True
    self.validate_across_sw_API = True

  def start_resolve_mismatch(self):
    self.diagnose = True
    self.resolve_mismatch = True
  
  def start_validate_across_input(self):
    self.diagnose = True
    self.validate_across_input = True
  
  def start_validate_across_API(self):
    self.diagnose = True
    self.validate_across_API = True
  
  def start_validate_across_sw_API(self):
    self.diagnose = True
    self.validate_across_sw_API = True

  def set_history_num(self, num):
    if num<0:
      self.check_history_num = 0
    else:
      self.check_history_num = int(num)

  