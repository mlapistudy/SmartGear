from cgi import test
from curses import meta
import io, os
import json
import requests
import random, string
import cv2
import math
from bs4 import BeautifulSoup

from .global_vars import *
from .enum_classes import *
from .status import *


SYNONYM = {}
KNOWLEDGE_P = {} # wikidata node -> parent
KNOWLEDGE_N = {} # wikidata node -> neightbor
KNOWLEDGE_W = {} # wikidata node -> whole (opposite to part-of)
wiki_to_name, name_to_wiki = {}, {}
wiki_to_mid, mid_to_wiki = {}, {}
label_to_mid, mid_to_label = {}, {}
object_to_mid, mid_to_object = {}, {}

TEXT_CLASS_P = {} # text classification categories. child -> parent


# ==========================================================
# ================= Intial environemnt =====================
# ==========================================================

def initial_values():
  global SYNONYM, KNOWLEDGE_P, KNOWLEDGE_N, KNOWLEDGE_W
  def read_knowledge(file_path):
    map = {}
    if os.path.exists(file_path):
      f = open(file_path, 'r')
      for line in f.readlines():
        splits = line.strip().split("\t")
        if len(splits) != 2:
          continue
        node, connected = splits
        map[node] = eval(connected)
      f.close()
    return map
  KNOWLEDGE_P = read_knowledge(KGP_SRC)
  KNOWLEDGE_N = read_knowledge(KGN_SRC)
  KNOWLEDGE_W = read_knowledge(KGW_SRC)

  global wiki_to_mid, mid_to_wiki, wiki_to_name, name_to_wiki
  f = open(MAP_SRC,'r')
  for line in f.readlines():
    label = line.strip().split(",")
    if len(label) == 2:
      mid_to_wiki[label[0]] = label[1]
      wiki_to_mid[label[1]] = label[0]
  f.close()
  if os.path.exists(WIKINAME_SRC):
    f = open(WIKINAME_SRC,'r')
    for line in f.readlines():
      label = line.strip().split("\t")
      if len(label) == 2:
        if label[0] == "None":
          name_to_wiki[label[1]] = None
        else:
          wiki_to_name[label[0]] = label[1]
          name_to_wiki[label[1]] = label[0]
      if len(label) == 1 and label[0].startswith("Q"):
         wiki_to_name[label[0]] = ""
    f.close()

  def get_label_list(file_name):
    text_to_mid = {}
    mid_to_text = {}
    f = open(file_name,'r')
    for line in f.readlines():
      label = line.strip().split(",")
      if len(label) == 2:
        label[1] = label[1].lower()
        mid_to_text[label[0]] = label[1]
        text_to_mid[label[1]] = label[0]
    f.close()
    return text_to_mid, mid_to_text
  
  global label_to_mid, mid_to_label, object_to_mid, mid_to_object
  label_to_mid, mid_to_label = get_label_list(LABEL_SRC)
  object_to_mid, mid_to_object = get_label_list(OBJECT_SRC)

  global TEXT_CLASS_P
  f = open(TEXT_CLASS_SRC,'r')
  for line in f.readlines():
    categories = line.strip().split("/")
    categories = [x for x in categories if len(x)>0]
    if len(categories) == 1:
      TEXT_CLASS_P[categories[0]] = "ALL"
    elif len(categories) >= 2:
      TEXT_CLASS_P[categories[-1]] = categories[-2]
  f.close()

initial_values()

# ==========================================================
# =================== vision APIs ==========================
# ==========================================================

def update_kg(node, parent=None, neighbors=None, whole=None):
  global KNOWLEDGE_P, KNOWLEDGE_N
  if (not parent is None) and (not node in KNOWLEDGE_P):
    KNOWLEDGE_P[node] = parent
    f = open(KGP_SRC, 'a')
    f.write("%s\t%s\n" % (node, str(parent)))
    f.close()
  if (not neighbors is None) and (not node in KNOWLEDGE_N):
    KNOWLEDGE_N[node] = neighbors
    f = open(KGN_SRC, 'a')
    f.write("%s\t%s\n" % (node, str(neighbors)))
    f.close()
  if (not whole is None) and (not node in KNOWLEDGE_W):
    KNOWLEDGE_W[node] = whole
    f = open(KGW_SRC, 'a')
    f.write("%s\t%s\n" % (node, str(whole)))
    f.close()
  
def query_kg(node):
  global KNOWLEDGE_P, KNOWLEDGE_N, KNOWLEDGE_W
  if node is None:
    return None, None, None
  if not node in KNOWLEDGE_P.keys() or not node in KNOWLEDGE_N.keys():
    try:
      parents, neighbors, wholes = search_wikidata(node)
    except:
      parents, neighbors, wholes = None, None, None
    update_kg(node, parents, neighbors, wholes)
  else:
    parents, neighbors = KNOWLEDGE_P[node], KNOWLEDGE_N[node], KNOWLEDGE_W[node]
  return parents, neighbors, wholes

def query_parent(node):
  global KNOWLEDGE_P
  if node is None:
    return None
  if not node in KNOWLEDGE_P.keys():
    try:
      parents, _, _ = search_wikidata(node)
    except:
      parents = None
    update_kg(node, parents, None)
  else:
    parents = KNOWLEDGE_P[node]
  if parents is None:
    return []
  return parents

def query_neighbor(node):
  global KNOWLEDGE_N
  if node is None:
    return None
  if not node in KNOWLEDGE_N.keys():
    try:
      _, neighbors, _ = search_wikidata(node)
    except:
      neighbors = None
    update_kg(node, None, neighbors)
  else:
    neighbors = KNOWLEDGE_N[node]
  if neighbors is None:
    return []
  return neighbors

def query_whole(node):
  global KNOWLEDGE_W
  if node is None:
    return None
  if not node in KNOWLEDGE_W.keys():
    try:
      _, _, wholes = search_wikidata(node)
    except:
      wholes = None
    update_kg(node, None, None, wholes)
  else:
    wholes = KNOWLEDGE_W[node]
  if wholes is None:
    return []
  return wholes

# return wiki data id
def search_wikidata(wiki_id):
  from wikidata.client import Client
  global wiki_to_mid, mid_to_wiki, label_to_mid, mid_to_label

  client = Client()
  entity = client.get(wiki_id, load=True)
  # for key, value in entity.__dict__.items():
  #   print(key, value)

  # very likely to be a useless one
  if len(entity.data["sitelinks"])==0 and len(entity.data["descriptions"])<=1:
    return [],[],[]

  related_items = set()
  parents, wholes = [], []
  claims = entity.data["claims"]
  
  for key, value in claims.items():
    if key == "P279": # subclass of
      for item in value:
        try:
          item = item["mainsnak"]["datavalue"]["value"]["id"]
          if item.startswith("Q"):
            parents.append(item)
        except:
          pass
    if key == "P361": # part of
      for item in value:
        try:
          item = item["mainsnak"]["datavalue"]["value"]["id"]
          if item.startswith("Q"):
            wholes.append(item)
        except:
          pass
      
    for item in value:
      try:
        # print(item ["mainsnak"]["datavalue"])
        item = item["mainsnak"]["datavalue"]["value"]
        if isinstance(item, dict):
          item = item["id"]
          if item.startswith("Q"):
            related_items.add(item)
        elif isinstance(item, str):
          item = item.lower()
          if not item in label_to_mid.keys():
            continue
          mid = label_to_mid[item]
          if not mid in mid_to_wiki.keys():
            continue
          related_items.add(mid_to_wiki[mid])
      except:
        pass
  return parents, related_items, wholes


def get_wikidata_name(wiki_id):
  global wiki_to_name, name_to_wiki
  if wiki_id in wiki_to_name:
    return wiki_to_name[wiki_id]

  from wikidata.client import Client
  client = Client()
  entity = client.get(wiki_id, load=True)
  try:
    name = entity.data["labels"]["en"]["value"]
  except:
    name = ""

  wiki_to_name[wiki_id] = name
  name_to_wiki[name] = wiki_id
  f = open(WIKINAME_SRC, 'a')
  f.write("%s\t%s\n" % (wiki_id, name))
  f.close()

  return name


def is_in_label_set(keyword, is_label=True):
  keyword = keyword.lower()
  if is_label:
    return keyword in label_to_mid.keys()
  else:
    return keyword in object_to_mid.keys()

def search_wikidata_id_from_name(item_name):
  global name_to_wiki, wiki_to_name
  if item_name in name_to_wiki.keys():
    return name_to_wiki[item_name]
  url = "https://www.wikidata.org/w/index.php?search="+str(item_name)
  A = ("Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.1 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36",
        )
  Agent = A[random.randrange(len(A))]
  headers = {'user-agent': Agent}
  r = requests.get(url, headers=headers)
  soup = BeautifulSoup(r.text, 'lxml')
  for item in soup.find_all("div", class_="mw-search-result-heading"):
    # print(item)
    links = item.findAll('a')
    for a in links:
      if a['href'].startswith("/wiki/Q"):
        wiki_id = a['href'][len("/wiki/"):]

        wiki_to_name[wiki_id] = item_name
        name_to_wiki[item_name] = wiki_id
        f = open(WIKINAME_SRC, 'a')
        f.write("%s\t%s\n" % (wiki_id, item_name))
        f.close()
        return wiki_id
  name_to_wiki[item_name] = None
  f = open(WIKINAME_SRC, 'a')
  f.write("%s\t%s\n" % ("None", item_name))
  f.close()
  return None
    

def name_to_wikidata_id(item_name):
  item_name = item_name.lower()
  # a trick
  if item_name == "can":
    item_name = "tin can"

  wiki_id = None
  if item_name in label_to_mid.keys():
    mid = label_to_mid[item_name]
    if mid in mid_to_wiki.keys():
      wiki_id = mid_to_wiki[mid]
  if wiki_id is None:
    wiki_id = search_wikidata_id_from_name(item_name)
  return wiki_id


def find_synonyms(keyword, is_label=True, depth=2):
  global SYNONYM
  keyword = keyword.lower()
  if keyword in SYNONYM.keys():
    return SYNONYM[keyword]

  wiki_id = name_to_wikidata_id(keyword)
  related_items = set(query_neighbor(wiki_id))
  if related_items is None:
    return []
  
  tmp_set = related_items
  for i in range(1,depth):
    extra_set = set()
    for item in tmp_set:
      tmp_set2 = query_neighbor(item)
      for element in tmp_set2:
        if not element in related_items:
          extra_set.add(element)
    related_items.update(extra_set)
    tmp_set = extra_set

  related_items2 = set() # translate to labels
  related_items2.add(keyword)
  for item in related_items:
    if not item in wiki_to_mid.keys():
      continue
    mid = wiki_to_mid[item]
    if not mid in mid_to_label.keys():
      continue
    related_items2.add(mid_to_label[mid])
  if keyword in related_items2:
    related_items2.remove(keyword)
  # adhoc fix
  if keyword=="fire":
    related_items2.add("flame")
  SYNONYM[keyword] = list(related_items2)
  return list(related_items2)

# find parent nodes
def find_parents(keyword, return_name=False):
  metaclass_id = ["Q35120" , "Q27043864", "Q35459920"]
  # entity, xxx, three-dimensional object

  wiki_id = name_to_wikidata_id(keyword)
  parents_id = query_parent(wiki_id)
  if parents_id is None:
    if return_name:
      return None, [], []
    return None, []
  
  parents_id = [x for x in parents_id if not x in metaclass_id]
  
  tmp_set = parents_id
  while len(tmp_set)>0:
    extra_set = set()
    for item in tmp_set:
      tmp_set2 = query_parent(item)
      for element in tmp_set2:
        if not element in parents_id and not element in metaclass_id:
          extra_set.add(element)
    parents_id += list(extra_set)
    tmp_set = extra_set

  parents_name = []
  parents_id2 = []
  for parent_id in parents_id:
    name = get_wikidata_name(parent_id)
    if len(name)>0 and not name.endswith(" object") and not name.endswith(" entity"):
      parents_name.append(name)
      parents_id2.append(parent_id)
  
  if not return_name:
    return wiki_id, parents_id2
  return wiki_id, parents_id2, parents_name

# find perspectives
def find_parents_second_level(keyword, return_name=False):
  highlight_class_id = ["Q735", "Q488383", "Q35120"]
  # art, object, entity
  goods_class_id = ["Q2424752", "Q28877"] # goods and services
  #  product, good
  metaclass_id = ["Q35120" , "Q27043864", "Q35459920"]
  # entity, xxxm three-dimensional object

  wiki_id = name_to_wikidata_id(keyword)
  parents_id = query_parent(wiki_id)
  if parents_id is None:
    return None, [], []

  tmp_set = [x for x in parents_id if not x in metaclass_id]
  final_set = {}
  while len(tmp_set)>0:
    extra_set = set()
    for item in tmp_set:
      tmp_set2 = query_parent(item)
      for element in tmp_set2:
        if not element in parents_id and not element in metaclass_id:
          extra_set.add(element)
        if element in highlight_class_id or element in goods_class_id:
          if not element in final_set.keys():
            final_set[element] = set()
          final_set[element].add(item)
    parents_id += list(extra_set)
    tmp_set = extra_set
  
  parent_candidates = set()
  for element in highlight_class_id:
    if element in final_set.keys():
      parent_candidates = final_set[element]
      break
  if "Q2897903" in parent_candidates: # goods and services
    for id in goods_class_id:
      if id in final_set.keys(): 
        parent_candidates.update(final_set[id])

  parents_name = []
  parents_id2 = []
  for parent_id in parent_candidates:
    name = get_wikidata_name(parent_id)
    if len(name)>0:
      parents_name.append(name)
      parents_id2.append(parent_id)

  if not return_name:
    return wiki_id, parents_id2
  return wiki_id, parents_id2, parents_name

# find inverse relation of part-of
def find_wholes(keyword, return_name=False):
  metaclass_id = ["Q35120" , "Q27043864", "Q35459920", "Q1", "Q221392"]
  # entity, xxxm three-dimensional object, universe, observable universe

  wiki_id = name_to_wikidata_id(keyword)
  wholes_id = query_whole(wiki_id)
  if wholes_id is None:
    if return_name:
      return None, [], []
    return None, []
    
  wholes_id = [x for x in wholes_id if not x in metaclass_id]
  
  tmp_set = wholes_id
  while len(tmp_set)>0:
    extra_set = set()
    for item in tmp_set:
      tmp_set2 = query_whole(item)
      for element in tmp_set2:
        if not element in wholes_id and not element in metaclass_id:
          extra_set.add(element)
    wholes_id += list(extra_set)
    tmp_set = extra_set
    

  wholes_name = []
  wholes_id2 = []
  for whole_id in wholes_id:
    name = get_wikidata_name(whole_id)
    if len(name)>0:
      wholes_name.append(name)
      wholes_id2.append(whole_id)
  
  if not return_name:
    return wiki_id, wholes_id2
  return wiki_id, wholes_id2, wholes_name

# =============================
# =============================
# =============================
def parent_distance(file_label, whitelist):
  whitelist = [x.lower() for x in whitelist]
  for i, label in enumerate(file_label):
    for condition in whitelist:
      if condition in label.lower():
        return 0

  whitelist_id = [name_to_wikidata_id(x) for x in whitelist]
  whitelist_id = [x for x in whitelist_id if len(x)>0]
  def dist_to_whitelist(keyword):
    metaclass_id = ["Q35120" , "Q27043864", "Q35459920"]
    wiki_id = name_to_wikidata_id(keyword)
    parents_id = query_parent(wiki_id)
    if parents_id is None:
      return 99999
    
    parents_id = [x for x in parents_id if not x in metaclass_id]
    count_dist = 0
    tmp_set = parents_id
    while len(tmp_set)>0 and count_dist<=30:
      count_dist += 1
      for id_p in tmp_set:
        if id_p in whitelist_id:
          return count_dist
      extra_set = set()
      for item in tmp_set:
        tmp_set2 = query_parent(item)
        for element in tmp_set2:
          if not element in parents_id and not element in metaclass_id:
            extra_set.add(element)
      tmp_set = extra_set
    return 99999


  def dist_to_label(target_label, keyword):
    metaclass_id = ["Q35120" , "Q27043864", "Q35459920"]
    wiki_id_keyword = name_to_wikidata_id(keyword)
    wiki_id_label = name_to_wikidata_id(target_label)
    parents_id = query_parent(wiki_id_label)
    if parents_id is None:
      return 99999
    
    parents_id = [x for x in parents_id if not x in metaclass_id]
    count_dist = 0
    tmp_set = parents_id
    while len(tmp_set)>0:
      count_dist += 1
      for id_p in tmp_set:
        if id_p == wiki_id_keyword:
          return count_dist
      extra_set = set()
      for item in tmp_set:
        tmp_set2 = query_parent(item)
        for element in tmp_set2:
          if not element in parents_id and not element in metaclass_id:
            extra_set.add(element)
      tmp_set = extra_set
    return 99999


  min_dist = 99999
  for i, label in enumerate(file_label):
    dist = dist_to_whitelist(label)
    if dist < min_dist:
      min_dist = dist
    for white in whitelist:
      dist = dist_to_label(white, label)
      if dist < min_dist:
        min_dist = dist
  return min_dist

def is_granularity_mismatch(file_label, whitelist):
  whitelist = [x.lower() for x in whitelist]
  for i, label in enumerate(file_label):
    for condition in whitelist:
      if condition in label.lower():
        return "Matches", [condition]
  
  g_mismatch = set()
  for i, label in enumerate(file_label):
    label_id, parents_l = find_parents(label.lower(), return_name=False)
    parents_l.append(label_id)
    _, wholes_l = find_wholes(label.lower(), return_name=False)
    for condition in whitelist:
      wiki_id, parents = find_parents(condition, return_name=False)
      _, wholes = find_wholes(condition, return_name=False)
      if (label_id in (parents+wholes)) or (wiki_id in (parents_l+wholes_l)):
        g_mismatch.add(condition)
  if len(g_mismatch)>0:
    return "Granularity mismatch", list(g_mismatch)
        
  return "Not granularity mismatch", None

  
def which_perspective(keyword):
  perspectives = []

  keyword_id, parents_id, parents_name = find_parents_second_level(keyword, return_name=True)
  for name in parents_name:
    if name.endswith(" entity") or name.endswith(" object"):
      continue
    perspectives.append(name)
  if "goods and services" in perspectives and len(perspectives)>1:
    perspectives.remove("goods and services")
  if len(perspectives)==0:
    perspectives = parents_name
  
  # adhoc fix
  if any([x  for x in perspectives if x.startswith("human ") or x.startswith("facial ")]): 
    perspectives.append("agent")
  if "agent" in perspectives:
    perspectives.append("spatio-temporal entity")
    perspectives.append("concrete object")
    perspectives.append("natural object")
  if "phenomenon" in perspectives:
    perspectives.append("natural object")
  return perspectives

def is_perspective_mismatch(file_label, whitelist):
  whitelist = [x.lower() for x in whitelist]
  for i, label in enumerate(file_label):
    for condition in whitelist:
      if condition in label.lower():
        return "Matches"
  
  cond_pers = set()
  for condition in whitelist:
    perspectives = which_perspective(condition)
    cond_pers.update(perspectives)

  result_pers = set()
  for i, label in enumerate(file_label):
    perspectives = which_perspective(label)
    result_pers.update(perspectives)
  
  shared_pers = cond_pers.intersection(result_pers)
  # print(shared_pers, cond_pers, result_pers)
  if len(cond_pers)==0 or len(result_pers)==0:
    return "Do not know"
  if len(shared_pers)==0:
    return "Perspective mismatch"
  return "Not perspective mismatch"

  
def check_image_mismatch(ml_output, examine_group):
  tmp, cond = is_granularity_mismatch(ml_output, examine_group)
  if tmp.startswith("Matches"):
    return True, False, False, False, False, cond
  match = False
  G_mis = tmp.startswith("Granularity mismatch")
  if G_mis:
    F_mis, P_mis = False, False
  else:
    result = is_perspective_mismatch(ml_output, examine_group)
    if result.startswith("Do not know"):
      F_mis, P_mis = False, False
    else:
      P_mis = result.startswith("Perspective mismatch")
      F_mis = not P_mis

  close_to = False
  for keyword in examine_group:
    neighbors = find_synonyms(keyword)
    for i, label in enumerate(ml_output):
      if label.lower() in neighbors:
        close_to = True
        return match, G_mis, F_mis, P_mis, close_to, cond
  return match, G_mis, F_mis, P_mis, close_to, cond

# ==========================================================
# =================== language APIs ==========================
# ==========================================================
def find_parents_text(label, exact_match=False):
  parents = set()
  for key, value in TEXT_CLASS_P.items():
    if value == "ALL": # highest level
      continue
    if (not exact_match and key.lower() in label.lower()) or (exact_match and key == label):
      parents.add(value)
      tmp = value
      while tmp in TEXT_CLASS_P.keys():
        if TEXT_CLASS_P[tmp] == "ALL":
          break
        tmp = TEXT_CLASS_P[tmp]
        parents.add(tmp)
  return parents


def is_granularity_mismatch_text(text_classes, whitelist, exact_match=False, input_text=None):
  for i, label in enumerate(text_classes):
    for condition in whitelist:
      if (not exact_match and condition.lower() in label.lower()) or (exact_match and condition == label):
        return "Matches", [condition]
  
  g_mismatch = set()
  for i, label in enumerate(text_classes):
    text_cat = label.split("/")[-1]
    parents_l = find_parents_text(text_cat, exact_match=True)
    for condition in whitelist:
      parents = find_parents_text(condition, exact_match=exact_match)
      flag = False
      for parent in parents_l:
        if (not exact_match and condition.lower().split("/")[-1] in parent) or (exact_match and condition.split("/")[-1] == parent):
          flag = True
          break
      if (text_cat in parents) or flag:
        g_mismatch.add(condition)

  if len(g_mismatch)>0:
    # additional checking of input_text
    # if not input_text is None:
    #   for mismatch in g_mismatch:
    #     api_result, cond = mismatch
    #     words = cond.translate(str.maketrans('', '', string.punctuation))
    #     if any([x in words for x in input_text]):
    #       return "Granularity mismatch: %s" % (g_mismatch)
    # else:
    #   return "Granularity mismatch", list(g_mismatch)
    return "Granularity mismatch", list(g_mismatch)
        
  return "Not granularity mismatch", None

def is_focus_mismatch_text(text_classes, whitelist, exact_match=False):
  for i, label in enumerate(text_classes):
    for condition in whitelist:
      if (not exact_match and condition.lower() in label.lower()) or (exact_match and condition == label):
        return "Matches"
  def top_level_class(label, em=exact_match):
    top_level = set()
    for key, value in TEXT_CLASS_P.items():
      if value == "ALL": # highest level
        if (not em and key.lower() in label.lower()) or (em and key == label):
          top_level.add(key)
        continue
      if (not em and key.lower() in label.lower()) or (em and key == label):
        tmp = value
        while tmp in TEXT_CLASS_P.keys():
            if TEXT_CLASS_P[tmp] == "ALL":
              break
            tmp = TEXT_CLASS_P[tmp]
        top_level.add(tmp)
    return top_level
  
  cond_pers = set()
  for condition in whitelist:
    perspectives = top_level_class(condition.split("/")[-1])
    cond_pers.update(perspectives)

  result_pers = set()
  for i, label in enumerate(text_classes):
    perspectives = top_level_class(label.split("/")[-1])
    result_pers.update(perspectives)
  # print(whitelist, [x for x in text_classes], cond_pers,result_pers)

  shared_pers = cond_pers.intersection(result_pers)
  if len(cond_pers)==0 or len(result_pers)==0:
    return "Do not know"
  if len(shared_pers)==0:
    return "Not focus mismatch"
  return "Focus mismatch"
  
def check_text_mismatch(ml_output, examine_group, em=False):
  tmp, cond = is_granularity_mismatch_text(ml_output, examine_group, exact_match=em)
  if tmp.startswith("Matches"):
    return True, False, False, False, False, cond
  match = False
  G_mis = tmp.startswith("Granularity mismatch")
  if G_mis:
    F_mis, P_mis = False, False
  else:
    result = is_focus_mismatch_text(ml_output, examine_group, exact_match=em)
    if result.startswith("Do not know"):
      F_mis, P_mis = False, False
    else:
      F_mis = result.startswith("Focus mismatch")
      P_mis = not F_mis # acutally means unknown error
  return match, G_mis, F_mis, P_mis, cond

# ==========================================================
# =================== wrapper ==========================
# ==========================================================

def check_mismatch_failure_image(ml_output, groups, task):
  if len(groups) <= 1:
    return None
  # G_mis, F_mis, P_mis = check_image_mismatch(ml_output, examine_group)
  failure = Failure()
  branch_status = [0,0,0,0]
  suspect_branches = [[],[],[]]
  suspect_cond = {}
  all_examined_groups = 0
  for no, group in enumerate(groups):
    if len(group)==1 and "" in group: # else branch
      continue
    all_examined_groups += 1
    matches, G_mis, F_mis, P_mis, close_to, condition_list = check_image_mismatch(ml_output, group)
    if matches:
      failure.type = FailureCode.MISMATCH_HEIR
      failure.fixing_suggestion = SolutionCode.CLUSTER
      tmp = [x.capitalize() for x in condition_list]
      failure.corrected_API_output = tmp #+ ml_output
      return failure
    if G_mis:
      branch_status[0] += 1
      suspect_branches[0].append(no)
      suspect_cond[no] = condition_list
    if F_mis:
      branch_status[1] += 1
      suspect_branches[1].append(no)
    if P_mis and close_to:
      branch_status[2] += 1
      suspect_branches[2].append(no)
    if F_mis and close_to:
      branch_status[3] += 1

  if branch_status[0]==1:
    failure.type = FailureCode.MISMATCH_HEIR
    failure.API = task
    failure.fixing_suggestion = SolutionCode.CLUSTER
    tmp = [x.capitalize() for x in suspect_cond[suspect_branches[0][0]]]
    failure.corrected_API_output = tmp #+ ml_output
  elif branch_status[0]>1:
    failure.type = FailureCode.MISMATCH_HEIR
    failure.API = task
    failure.fixing_suggestion = SolutionCode.SEGMENT
  elif branch_status[3]>=1:
    failure.type = FailureCode.MISMATCH_FOCUS
    failure.API = task
    failure.fixing_suggestion = SolutionCode.SEGMENT
  elif branch_status[2]==all_examined_groups:
    failure.type = FailureCode.MISMATCH_PERS
    failure.API = task
    failure.fixing_suggestion = SolutionCode.REPORT
  else:
    failure = None
  return failure    

def check_mismatch_failure_text(ml_output, groups, task):
  if len(groups) <= 1:
    return None
  failure = Failure()
  branch_status = [0,0,0,0]
  suspect_branches = [[],[],[]]
  suspect_cond = {}
  all_examined_groups = 0
  for no, group in enumerate(groups):
    if len(group)==1 and "" in group: # else branch
      continue
    all_examined_groups += 1
    matches, G_mis, F_mis, P_mis, condition_list = check_text_mismatch(ml_output, group)
    if matches:
      failure.type = FailureCode.MISMATCH_HEIR
      failure.corrected_API_output = SolutionCode.CLUSTER
      failure.fixing_suggestion = condition_list
      return failure
    if G_mis:
      branch_status[0] += 1
      suspect_branches[0].append(no)
      suspect_cond[no] = condition_list
    if F_mis:
      branch_status[1] += 1
      suspect_branches[1].append(no)
    if P_mis: # it is always False
      branch_status[2] += 1
      suspect_branches[2].append(no)

  if branch_status[0]==1:
    failure.type = FailureCode.MISMATCH_HEIR
    failure.API = task
    failure.fixing_suggestion = SolutionCode.CLUSTER
    tmp = [x.capitalize() for x in suspect_cond[suspect_branches[0][0]]]
    failure.corrected_API_output = tmp #+ ml_output
  elif branch_status[0]>1:
    failure.type = FailureCode.MISMATCH_HEIR
    failure.API = task
    failure.fixing_suggestion = SolutionCode.SEGMENT
  elif branch_status[3]>=1:
    failure.type = FailureCode.MISMATCH_FOCUS
    failure.API = task
    failure.fixing_suggestion = SolutionCode.SEGMENT
  else:
    failure = None
  return failure    

def check_mismatch_failure(ml_result, cf_structure):
  conditions = cf_structure["conditions"]
  failures = []
  for task in [MlTask.VISION_LABEL, MlTask.VISION_OBJECT, MlTask.VISION_WEB]:
    if task in ml_result.keys() and task in conditions.keys():
      ml_output = ml_result[task]
      examine_groups = conditions[task]
      failure = check_mismatch_failure_image(ml_output, examine_groups, task)
      if not failure is None and not failure.type is None:
        failures.append(failure)
  for task in [MlTask.LANG_CLASS]:
    if task in ml_result.keys() and task in conditions.keys():
      ml_output = ml_result[task]
      examine_groups = conditions[task]
      failure = check_mismatch_failure_text(ml_output, examine_groups, task)
      if not failure is None and not failure.type is None:
        failures.append(failure)
  return failures




if __name__ == '__main__':
  pass
  