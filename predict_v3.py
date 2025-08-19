import os

os.environ["RPY2_CFFI_MODE"] = "ABI"

import rpy2.robjects as ro
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import FloatVector, IntVector, StrVector

predictv30 = importr('predictv30r')

"""
predict R 3.1:
Calculate benefits of continuing endocrine therapy assuming survival to 5 years

#' @param age.start.in Patient age in years
#' @param screen.in Clinically detected = 0, screen detected = 1
#' @param size.in Tumour size mm
#' @param grade.in Tumour grade
#' @param nodes.in Number positive nodes
#' @param er.in ER+ = 1, ER- = 0
#' @param her2.in HER2+ = 1, HER2- = 0, missing = 9
#' @param ki67.in KI67+ = 1, KI67- = 0, missing = 9
#' @param pr.in ptogesterone satus PR+ = 1 PR- = 0
#' @param generation.in Chemo generation 0, 2 or 3 only
#' @param horm.in Hormone therapy Yes = 1, no = 0
#' @param traz.in Trastuzumab therapy Yes = 1, no = 0
#' @param bis.in Bisphosphonate therapy Yes = 1, no = 0
#' @param radio.in Radiotherapy Yes = 1, no = 0
#' @param heart.gy.in Number of grays radiation to the heart
#' @param smoker.in Never/ex = 0, current = 1
"""

# Create input named parameters
args = {
    'age.start.in': 65,
    'screen.in': 1,
    'size.in': 20,
    'grade.in': 2,
    'nodes.in': 4,
    'er.in': 1,
    'pr.in': 1,
    'generation.in': 2,  # chemo generation
    'her2.in': 9,
    'ki67.in': 9,
    'horm.in': 1,
    'traz.in': 1,
    'bis.in': 1,
    'radio.in': 1,
    'heart.gy.in': 7,
    'smoker.in': 0
}

# Call predict model version 3.0
result = ro.r['benefits31'](**args)

print(type(result))

print(result)

print(result)
