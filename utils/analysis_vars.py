import pandas as pd


def pos_neg_unknown(val):
  if pd.isna(val):
    return "Unknown"
  
  if val == 0:
    return "Negative"
  elif val == 1:
    return "Positive"
  elif val == 9:
    return "Unknown"
  else:
    return "Mystery"
  

def screening_str_vals(val):
  if pd.isna(val):
    return "Unknown"
  
  if val == 0:
    return "Symptomatic/Other"
  elif val == 1:
    return "Screening"
  elif val == 9:
    return "Unknown"
  else:
    return "Mystery"


# Age grouping function
def bin_age(val):
  if pd.isna(val):
    return "Unknown"
  if val < 45:
    return "$<45$"
  elif 40 <= val <= 60:
    return "45-60"
  elif 61 <= val <= 75:
    return "61-75"
  else:
    return "$>$75"
  
# Diagnosis year grouping function
def bin_diag_year(val):
  if pd.isna(val):
    return "Unknown"
  if val < 2000:
    return "$<2000$"
  elif 2000 <= val <= 2009:
    return "2000-2009"
  elif 2010 <= val <= 2018:
    return "2010-2018"
  else:
    return "$>$2018"
  

# Nodes grouping function
def bin_nodes(val):
  if pd.isna(val):
    return "Unknown"
  if val == 0:
    return "0"
  elif 1 <= val <= 5:
    return "1-5"
  elif 6 <= val <= 10:
    return "6-10"
  elif 11 <= val <= 15:
    return "11-15"
  else:
    return "16+"

# tumour size grouping function
def bin_size(val):
  if pd.isna(val):
    return "Unknown"
  if val <= 10:
    return "$\\leq$10mm"
  elif 11 <= val <= 20:
    return "11-20mm"
  elif 21 <= val <= 40:
    return "21-40mm"
  else:
    return "$>$40mm"