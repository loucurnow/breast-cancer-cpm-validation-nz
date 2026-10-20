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

"""
Interpreting the results:
  [1] "h1_br_i"         
      "s.cum.all"      = Overall cumulative survival across all causes (combining both breast-cancer-specific survival and other-cause mortality).    
      "smoker.prop"    = Population or risk adjustment proportion related to smoking status if factored into the background mortality or comorbidity estimates.    
      "m.all"          = overall cumulative mortality (the inverse of overall survival, representing the total risk of death from any cause over time).   
  [5] "size.mfp"        
      "base.m.cum.oth" = baseline or underlying cumulative mortality hazards from other causes derived from demographic actuarial data
      "sc1_er0"         
      "sc1_er1"        
  [9] "s.cum.oth"      =  cumulative survival expected from other causes (non-breast-cancer deaths, based on background population mortality tables for age
      "m.oth"          =  cumulative mortality from other causes alone    
      "rx"             =  A summary record or echo of the treatment options/modalities configured for the current prediction run.    
      "age.start"      =  input, age in years of patient diagnosis
 [13] "pred.cum.all"    "ag1_er0"         "her2"            "age"            
 [17] "ag1_er1"         "h0_br_i"         "h_ot_t1"         "h_ot_t2"        
 [21] "s.cum.br"        "r.other"         "ag2_er0"         "ag2_er1"        
 [25] "her2.beta"       "nodes.mfp"       "radio"           "ag_ot_ea.beta.1"
 [29] "ag_ot_ea.beta.2" "generation"      "pred.cum.oth"    "year"           
 [33] "nodes.beta"      "pred.cum.br"     "r.oth"           "c.other"        
 [37] "smoker.rr"       "horm"            "smoker.beta"     "nd1_er0"        
 [41] "nd1_er1"         "heart.gy"        "cvd.prop"        "size"           
 [45] "pred.m.oth"      "age.beta.1"      "yr1_er0"         "age.beta.2"     
 [49] "yr1_er1"         "base.m.cum.br"   "r.base.br"       "mi"             
 [53] "c.oth"           "benefits"        "m.oth.temp"      "smoker.rr.acm"  
 [57] "m.cum.br"        "h10"             "m.cum.all"       "h0_br_t1"       
 [61] "h0_br_t2"        "time"            "m.cum.oth"       "cols"           
 [65] "b"               "sz1_er0"         "c"               "sz1_er1"        
 [69] "mi.rx"           "year.br.beta"    "size.beta"       "prop.br"        
 [73] "h"               "i"               "m.br"            "j"              
 [77] "yr_ot_ea.beta"   "grade.beta"      "r"               "age.mfp.1"      
 [81] "t"               "age.mfp.2"       "er"              "pred.m.br"      
 [85] "base.m.br"       "pr.beta"         "smoker"          "pi.rx"          
 [89] "pi"              "m.cum.oth.temp"  "gr1_er0"         "gr1_er1"        
 [93] 
 "surv"  15x47 tibble, cumulative survival probabilities at each year with different treatment approaches:
    s = surgery alone
    r = radiotherapy
    h = hormone therapy
    c = chemotherapy
    t = trastuzumab
    b = bisphosphonates
    rh = radiotherapy and hormone therapy, rc = radiotherapy and chemotherapy, same logic for other columns
    rhct = radiotherapy, hormone therapy, chemotherapy, trastuzumab
    rh10 = radiotherapy and hormone therapy, optimised for 10 year survival
    h10c = radiotherapy and chemotherapy, optimised for 10 year survival 

 "h_ot_i"          
 "traz"   input, 1 = yes traztusumab 0 = no      
 "grade"  input, 1-3 integer         
 [97] 
 "pr"  input, 1 = positive 0 = negative 9 = unknown           
 "ki67.beta" coefficient associated with ki67 value (0 if unknown)       
 "ki67"     9 = unknown            
 "nodes"    int, node count       
[101] 
"h1_br_t1"        
"h1_br_t2"        
"r.base.oth"      
"r.prop"         
[105] 
"screen.beta"   coefficient in Cox proportional hazards model for the   
"r.breast"        single decimal 0-1?
"base.m.oth"      15x values for 
"bis"    1 = yes received bisphosphonates        
[109] 
"screen"  - 1 = screening, 0 = symptomatic       
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
result = ro.r['benefits31'](**args) # type: ignore

print(type(result))

print(result)

print(result.names)