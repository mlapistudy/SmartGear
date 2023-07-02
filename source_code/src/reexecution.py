import os, io, sys
import cv2, re
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

from google.cloud import vision
from google.cloud import language
from google.cloud import speech
from google.cloud import videointelligence_v1 as videointelligence

from .global_vars import *
from .enum_classes import *
from . import helper

# =================================================
# ==================== Segment ====================
# =================================================

def segementation(ml_task, api_params, api_params_name):
  if ml_task in [MlTask.VISION_LABEL, MlTask.VISION_OBJECT, MlTask.VISION_FACE, MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT, MlTask.VISION_WEB, MlTask.VISION_LAND, MlTask.VISION_LOGO]:
    return segementation_image(ml_task, api_params, api_params_name)
  if ml_task in [MlTask.LANG_CLASS, MlTask.LANG_SENTI, MlTask.LANG_ENTITY]:
    return segementation_language(ml_task, api_params, api_params_name)
  # we do not reex speech
  return None

def segementation_image(ml_task, api_params, api_params_name):
  # print(type(api_params[0]))
  image = None
  for no in range(len(api_params_name)-1, -1, -1):
    para_name = api_params_name[no]
    if para_name == "image":
      image = api_params[len(api_params)-len(api_params_name)+no]
      break
  if image is None:
    image = api_params[0]
 
  tmp_file = os.path.join(LOG_SRC, "image_tmp.raw")
  with io.open(tmp_file, 'wb') as image_file:
    image_file.write(image.content)
  
  N = 2 # one image slide into N*N
  im_cv2 = cv2.imread(tmp_file)
  height, width, color = im_cv2.shape
  window_h = int(height/N)
  window_w = int(width/N)

  cropped_images = []
  api_results = []
  for i in range(N):
    for j in range(N):
      x = window_w*i
      y = window_h*j
      cropped = im_cv2[y:y+window_h, x:x+window_w].copy()
      cropped_image = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
      save_path = os.path.join(LOG_SRC, "tmp%d_%d.jpg"%(i,j))
      cropped_image.save(save_path) 
      cropped_images.append(save_path)

  with ThreadPoolExecutor() as executor:
    running_tasks = [executor.submit(call_image_api, path, ml_task) for path in cropped_images]
    for running_task in running_tasks:
      api_results.append(running_task.result())
  
  if len(api_results)==1:
    return api_results[0]
  
  new_result = api_results[0]
  if ml_task == MlTask.VISION_LABEL:
    for i in range(1, len(api_results)):
      new_result.label_annotations.MergeFrom(api_results[i].label_annotations)
  if ml_task == MlTask.VISION_OBJECT:
    for i in range(1, len(api_results)):
      new_result.localized_object_annotations.MergeFrom(api_results[i].localized_object_annotations)
  if ml_task == MlTask.VISION_FACE: # will never be segmented
    for i in range(1, len(api_results)):
      new_result.face_annotations.MergeFrom(api_results[i].face_annotations)
  if ml_task == MlTask.VISION_TEXT: # will never be segmented
    for i in range(1, len(api_results)):
      new_result.text_annotations.MergeFrom(api_results[i].text_annotations)
      new_result.text_annotations[0].description += "\n" + api_results[i].text_annotations[0].description
  if ml_task == MlTask.VISION_DOCUMENT: # will never be segmented
    for i in range(1, len(api_results)):
      new_result.full_text_annotation.text += "\n" + api_results[i].full_text_annotation.text
  if ml_task == MlTask.VISION_WEB:
    for i in range(1, len(api_results)):
      new_result.web_detection.best_guess_labels.MergeFrom(api_results[i].web_detection.best_guess_labels)
      new_result.web_detection.web_entities.MergeFrom(api_results[i].web_detection.web_entities)
  if ml_task == MlTask.VISION_LAND:
    for i in range(1, len(api_results)):
      new_result.landmark_annotations.MergeFrom(api_results[i].landmark_annotations)
  if ml_task == MlTask.VISION_LOGO:
    for i in range(1, len(api_results)):
      new_result.logo_annotations.MergeFrom(api_results[i].logo_annotations)

  return new_result

def call_image_api(img_path, ml_task):
  client = vision.ImageAnnotatorClient()
  with io.open(img_path, 'rb') as image_file:
      content = image_file.read()
  image = vision.types.Image(content=content)
  if ml_task == MlTask.VISION_LABEL:
    response = client.label_detection(image=image)
  if ml_task == MlTask.VISION_OBJECT:
    response = client.object_localization(image=image)
  if ml_task == MlTask.VISION_FACE:
    response = client.face_detection(image=image)
  if ml_task == MlTask.VISION_TEXT:
    response = client.text_detection(image=image)
  if ml_task == MlTask.VISION_DOCUMENT:
    response = client.document_text_detection(image=image)
  if ml_task == MlTask.VISION_WEB:
    response = client.web_detection(image=image)
  if ml_task == MlTask.VISION_LAND:
    response = client.landmark_detection(image=image)
  if ml_task == MlTask.VISION_LOGO:
    response = client.logo_detection(image=image)
  
  return response


def segementation_language(ml_task, api_params, api_params_name):
  document = None
  for no in range(len(api_params_name)-1, -1, -1):
    para_name = api_params_name[no]
    if para_name == "document":
      document = api_params[len(api_params)-len(api_params_name)+no]
      break
  if document is None:
    document = api_params[0]
  
  N = 4 # slide document into 4 pieces
  cropped_texts = split_text_by_sentence(document.content, N)
  api_results = []
  with ThreadPoolExecutor() as executor:
    running_tasks = [executor.submit(call_language_api, text, ml_task) for text in cropped_texts]
    for running_task in running_tasks:
      api_results.append(running_task.result())
  
  if len(api_results)==1:
    return api_results[0]

  new_result = api_results[0]
  if ml_task == MlTask.LANG_CLASS:
    for i in range(1, len(api_results)):
      new_result.categories.MergeFrom(api_results[i].categories)
  if ml_task == MlTask.LANG_SENTI: # will never be segmented
    score, mag = new_result.document_sentiment.score , new_result.document_sentiment.magnitude
    for i in range(1, len(api_results)):
      new_result.sentences.MergeFrom(api_results[i].sentences)
      score += api_results[i].document_sentiment.score
      mag += api_results[i].document_sentiment.magnitude
    new_result.document_sentiment.score = score/N
    new_result.document_sentiment.magnitude = mag/N
  if ml_task == MlTask.LANG_ENTITY: # will never be segmented
    for i in range(1, len(api_results)):
      new_result.entities.MergeFrom(api_results[i].entities)
  if ml_task == MlTask.LANG_ENTITY_SENTI: # will never be segmented
    for i in range(1, len(api_results)):
      new_result.entities.MergeFrom(api_results[i].entities)
  
  return new_result


def call_language_api(text, ml_task):
  client = language.LanguageServiceClient()
  document = language.types.Document(content=text, type=language.enums.Document.Type.PLAIN_TEXT)
  if ml_task == MlTask.LANG_CLASS:
    response = client.classify_text(document)
  if ml_task == MlTask.LANG_SENTI: 
    response = client.analyze_sentiment(document=document).document_sentiment
  if ml_task == MlTask.LANG_ENTITY:
    response = client.analyze_entities(document=document)
  if ml_task == MlTask.LANG_ENTITY_SENTI:
    response = client.analyze_entity_sentiment(document=document)
  return response


def split_text_by_sentence(text_content, list_num):
  text_list = []
  target_length = len(text_content) // list_num
  
  cur_string = ""
  sentences = re.split(r"([.。!！?？；;])", text_content)
  i = 0
  while i < len(sentences):
    if i+1 < len(sentences):
      sentence = sentences[i]+sentences[i+1] # add back punctuation
      i = i+1
    if (len(cur_string) + 0.25*len(sentence) >= target_length) and not len(cur_string)==0:
      text_list.append(cur_string)
      cur_string = ""
    cur_string = cur_string + sentence
    i = i+1
  if len(cur_string)>=1:
    if len(text_list)<list_num:
      text_list.append(cur_string)
    else:
      text_list[-1] = text_list[-1] + cur_string

  return text_list




# =================================================
# ==================== Video API ====================
# =================================================
VIDEO_TIMEOUT = 20

def call_video_api(ml_task, ml_inputs, ml_api_value):
  if not ml_task in [MlTask.VISION_OBJECT, MlTask.VISION_FACE, MlTask.VISION_TEXT, MlTask.VISION_DOCUMENT]: # we only do this four types
    return None
  if len(ml_inputs) == 1:
    return ml_inputs
    
  try:
    image_files = []
    for no, ml_input in enumerate(ml_inputs):
      image_path = helper.extract_ml_input_content(ml_input, id=no)
      if not image_path is None:
        image_files.append(image_path)
    video_path = os.path.join(LOG_SRC, "tmp_video.raw")
    video_path, width, height = image_to_video(image_files, video_path)
  
    copied_api_result = vision.types.AnnotateImageResponse()
    copied_api_result.CopyFrom(ml_api_value)
    
    if ml_task ==  MlTask.VISION_OBJECT:
      copied_api_result = get_object_video(video_path, copied_api_result, width, height)
    elif ml_task ==  MlTask.VISION_FACE:
      copied_api_result = get_face_video(video_path, copied_api_result, width, height)
    elif ml_task ==  MlTask.VISION_TEXT:
      copied_api_result = get_text_video(video_path, copied_api_result, width, height)
    elif ml_task ==  MlTask.VISION_DOCUMENT:
      copied_api_result = get_text_video_doc(video_path, copied_api_result, width, height)
    
    return copied_api_result
  except:
    return None

def image_to_video(image_files, video_path):
  fps=12
  frame = cv2.imread(image_files[-1]) # last is the newest
  height, width, layers = frame.shape
  video = cv2.VideoWriter(video_path, 0, fps, (width,height))
  for image in image_files:
    cv2_img = cv2.imread(image)
    cv2_img = cv2.resize(cv2_img, (width, height))
    for i in range(4):
      video.write(cv2_img)
  cv2.destroyAllWindows()
  video.release()
  return video_path, width, height

def get_text_video(video_path, ml_api_value, width, height):
  if not ml_api_value.text_annotations:
    return
  video_client = videointelligence.VideoIntelligenceServiceClient()
  features = [videointelligence.Feature.TEXT_DETECTION]
  video_context = videointelligence.VideoContext()
  

  with io.open(video_path, "rb") as file:
      input_content = file.read()

  operation = video_client.annotate_video(
      request={
          "features": features,
          "input_content": input_content,
          "video_context": video_context,
      }
  )
  result = operation.result(timeout=VIDEO_TIMEOUT)
  annotation_result = result.annotation_results[0] # first video
  

  text_list = []
  ll = len(ml_api_value.text_annotations)
  if ll==0:
    x = ml_api_value.text_annotations.add()
    x.description = ""
    x.confidence = 0.9
  for i in range(1,ll):
    ml_api_value.text_annotations.pop(-1)
      
  for text_annotation in annotation_result.text_annotations:
    text = text_annotation.text
    text_segment = text_annotation.segments[0]
    confidence = text_segment.confidence
    frame = text_segment.frames[-1]
    time_offset = frame.time_offset
    bounding_box = frame.rotated_bounding_box.vertices

    text_list.append(text)
    x = ml_api_value.text_annotations.add()
    x.description = text
    x.confidence = confidence
    x.bounding_poly.CopyFrom(bounding_box)
    # turn normalized to absolute
    for vertex in x.bounding_poly.vertices:
      vertex.x = int(vertex.x * width)
      vertex.y = int(vertex.y * height)
  ml_api_value.text_annotations[0].description = "\n".join(text_list)
  return ml_api_value

def get_text_video_doc(video_path, ml_api_value, width, height):
  if not ml_api_value.full_text_annotation:
    return

  video_client = videointelligence.VideoIntelligenceServiceClient()
  features = [videointelligence.Feature.TEXT_DETECTION]
  video_context = videointelligence.VideoContext()

  with io.open(video_path, "rb") as file:
      input_content = file.read()

  operation = video_client.annotate_video(
      request={
          "features": features,
          "input_content": input_content,
          "video_context": video_context,
      }
  )
  result = operation.result(timeout=VIDEO_TIMEOUT)
  annotation_result = result.annotation_results[0] # first video
  
  text_list = []
  for text_annotation in annotation_result.text_annotations:
    text = text_annotation.text
  # TODO: support character level
  ml_api_value.full_text_annotation.text = "\n".join(text_list)
  return ml_api_value


def get_object_video(video_path, ml_api_value, width, height):
  if not ml_api_value.localized_object_annotations:
    return

  video_client = videointelligence.VideoIntelligenceServiceClient()
  features = [videointelligence.Feature.OBJECT_TRACKING]

  with io.open(video_path, "rb") as file:
      input_content = file.read()

  operation = video_client.annotate_video(request={"features": features, "input_content": input_content})
  result = operation.result(timeout=VIDEO_TIMEOUT)
  annotation_result = result.annotation_results[0] # first video

  ll = len(ml_api_value.localized_object_annotations)
  for i in range(ll):
    ml_api_value.localized_object_annotations.pop(-1)

  for object_annotation in annotation_result.object_annotations:
    name = object_annotation.entity.description
    score = object_annotation.confidence
    if object_annotation.entity.entity_id:
      id = object_annotation.entity.entity_id
    else:
      id = None
    frame = object_annotation.frames[-1]
    bounding_box = frame.normalized_bounding_box

    x = ml_api_value.localized_object_annotations.add()
    x.name = name
    x.score = score
    x.mid = id
    x.bounding_poly.CopyFrom(bounding_box)
  return ml_api_value

def get_face_video(video_path, ml_api_value, width, height):
  if not ml_api_value.face_annotations:
    return
  video_client = videointelligence.VideoIntelligenceServiceClient()
  features = [videointelligence.Feature.FACE_DETECTION]
  config = videointelligence.FaceDetectionConfig(include_bounding_boxes=True, include_attributes=True)
  context = videointelligence.VideoContext(face_detection_config=config)
  
  with io.open(video_path, "rb") as file:
      input_content = file.read()

  operation = video_client.annotate_video(request={
            "features": features,
            "input_content": input_content,
            "video_context": context})
  result = operation.result(timeout=VIDEO_TIMEOUT)
  annotation_result = result.annotation_results[0]
  
  ll = len(ml_api_value.face_annotations)
  for i in range(0,ll):
    ml_api_value.face_annotations.pop(-1)

  for annotation in annotation_result.face_detection_annotations:
    for track in annotation.tracks:
      timestamped_object = track.timestamped_objects[0]
      bounding_box = timestamped_object.normalized_bounding_box
      descriptions = []
      for attribute in timestamped_object.attributes:
        if attribute.confidence > 0.5:
          descriptions.append(attribute.name)
      
      x = ml_api_value.face_detection_annotations.add()
      x.bounding_poly.CopyFrom(bounding_box)
      # turn normalized to absolute
      for vertex in x.bounding_poly.vertices:
        vertex.x = int(vertex.x * width)
        vertex.y = int(vertex.y * height)

      # likelihood: 0: 'UNKNOWN', 1: 'VERY_UNLIKELY', 2: 'UNLIKELY', 3: 'POSSIBLE', 4: 'LIKELY', 5: 'VERY_LIKELY')
      x.joy_likelihood = 1
      x.sorrow_likelihood = 1
      x.anger_likelihood = 1
      x.surprise_likelihood = 1
      # video face detection do not have a good emotion detection ability
      if "smiling" in descriptions:
        x.joy_likelihood = 4
        
  return ml_api_value




