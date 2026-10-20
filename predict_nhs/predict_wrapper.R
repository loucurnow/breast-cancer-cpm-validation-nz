# predict_wrapper.R

# Load the library at the top of your R script
library(predictv30r)

library(dplyr)

process_predict_batch <- function(df_input) {
  
  results_list <- apply(df_input, 1, function(row) {  
    
    # Call the model
    res <- benefits31(
      age.start.in = as.numeric(row['age.start.in']),
      screen.in    = as.numeric(row['screen.in']),
      size.in      = as.numeric(row['size.in']),
      grade.in     = as.numeric(row['grade.in']),
      nodes.in     = as.numeric(row['nodes.in']),
      er.in        = as.numeric(row['er.in']),
      pr.in        = as.numeric(row['pr.in']),
      generation.in= as.numeric(row['generation.in']),
      her2.in      = as.numeric(row['her2.in']),
      ki67.in      = as.numeric(row['ki67.in']),
      horm.in      = as.numeric(row['horm.in']),
      traz.in      = as.numeric(row['traz.in']),
      bis.in       = as.numeric(row['bis.in']),
      radio.in     = as.numeric(row['radio.in']),
      heart.gy.in  = as.numeric(row['heart.gy.in']),
      smoker.in    = as.numeric(row['smoker.in'])
    )
    
    # Clean and get the treatment string
    treat_col <- trimws(as.character(row['treatments.given']))
    
    # Helper function to safely extract values from a given matrix
    extract_metric <- function(mat) {
      if (!is.null(mat) && treat_col %in% colnames(mat)) {
        return(mat[c(5, 10, 15), treat_col])
      } else {
        return(c(NA, NA, NA))
      }
    }
    
    # Extract for all three outcomes
    val_all <- extract_metric(res$pred.cum.all)
    val_br  <- extract_metric(res$pred.cum.br)
    val_oth <- extract_metric(res$pred.cum.oth)
    
    # Combine into a single vector and assign unique names
    target_values <- c(val_all, val_br, val_oth)
    names(target_values) <- c(
      "pred_all_yr5", "pred_all_yr10", "pred_all_yr15",
      "pred_br_yr5",  "pred_br_yr10",  "pred_br_yr15",
      "pred_oth_yr5", "pred_oth_yr10", "pred_oth_yr15"
    )
    
    return(as.data.frame(as.list(target_values)))
  })
  
  # Combine rows and bind back to original input data
  final_df <- bind_rows(results_list)
  output_df <- bind_cols(df_input, final_df)
  
  return(output_df)
}