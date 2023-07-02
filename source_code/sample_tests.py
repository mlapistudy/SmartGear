import os
from sample_functions import *


# Example of accuracy failure
image_path = os.path.join("test_data", "cake.jpg")
Diagnoser.config.stop_diagnose()
result = find_dessert(image_path)
print("Function original result:", result)
Diagnoser.config.start_all_diagnose()
result = find_dessert(image_path)
print("Function revised result:", result)