import pandas as pd
import numpy as np
from typing import Dict, Tuple
from dataclasses import dataclass

@dataclass
class SurgeryCompletionRules:
    """Defines the rules for determining surgical completeness"""
    
    # Breast surgery completeness rules
    BREAST_COMPLETE_INDICATORS = ['mastectomy']
    BREAST_PPX_MAST_INDICATORS = ['prophylactic_mastectomy']
    BREAST_CONSERVATIVE_INDICATORS = ['wle_partial_mastectomy', 'lumpectomy_ex_biopsy']
    
    # Node surgery completeness rules
    NODE_COMPLETE_INDICATORS = ['L2_ax_ln_dissect', 'L3_ax_ln_clear']
    NODE_SNB_INDICATORS = ['snb', 'L1_ax_ln_samp']
    
    # Thresholds
    MIN_NODES_FOR_ADEQUATE_SNB = 4
    MAX_POSITIVE_NODES_FOR_SNB_ONLY = 2


class LocoregionalCompletionClassifier:
    """
    Classifies surgical completeness for breast cancer cases based on restructured data.
    
    Data structure:
        workup_no: case identifier
        breast_side: 'L' or 'R' 
        first_surgery_date: date of first surgery
        All surgery types as 0/1 binary indicators
        Pathology data: node_total_removed, node_involved_count, total_lesions, max_lesion_mm
        Treatment data: adj_rad (adjuvant radiation)
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Parameters:
            df: DataFrame with restructured surgery data
        """
        self.df = df.copy()
        self.rules = SurgeryCompletionRules()
        self._validate_data()
        
    def _validate_data(self):
        """Check required columns exist"""
        required_cols = ['workup_no', 'breast_side']
        missing = [col for col in required_cols if col not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
    
    def _standardize_radiation(self, adj_rad_col: str = 'adj_rad') -> pd.Series:
        """Standardize adjuvant radiation coding to YES/NO/NA"""
        def map_rad(val):
            if pd.isna(val):
                return 'NA'
            
            val = str(val).lower().strip()
            
            if 'yes' in val:
                return 'YES'
            elif any(x in val for x in ['no', 'not referred', 'not yet', 'declined', 'unfit', 'unnecessary']):
                return 'NO'
            elif 'unknown' in val:
                return 'NA'
            else:
                return 'NA'
        
        return self.df[adj_rad_col].apply(map_rad) if adj_rad_col in self.df.columns else pd.Series('NA', index=self.df.index)
    
    def _classify_breast_surgery(self, row: pd.Series, radiation: str) -> str:
        """
        Classify breast surgery completeness for a single case.
        
        Rules:
        - COMPLETE: Mastectomy OR (Conservative + Radiation)
        - PPX_MAST: Prophylactic mastectomy
        - INCOMPLETE: Conservative without radiation
        - NO_SURG_DATA: No surgery recorded but has radiation
        - NA: No surgery data and no radiation data
        """
        
        # Check for mastectomy
        if row.get('mastectomy', 0) == 1:
            return 'COMPLETE'
        
        # Check for prophylactic mastectomy
        if row.get('prophylactic_mastectomy', 0) == 1:
            return 'PPX_MAST'
        
        # Check for conservative breast surgery (WLE, lumpectomy)
        has_conservative = any(row.get(col, 0) == 1 
                              for col in self.rules.BREAST_CONSERVATIVE_INDICATORS)
        
        if has_conservative:
            if radiation == 'YES':
                return 'COMPLETE'
            elif radiation == 'NO':
                return 'INCOMPLETE'
            elif radiation == 'NA':
                return 'INCOMPLETE'  # Missing radiation data treated as incomplete
        
        # No breast surgery recorded
        if radiation == 'YES':
            return 'NO_SURG_DATA_YES_RT'
        elif radiation == 'NO':
            return 'INCOMPLETE'
        else:
            return 'NA'
    
    def _classify_node_surgery(self, row: pd.Series) -> str:
        """
        Classify axillary (lymph node) surgery completeness.
        
        Rules:
        - COMPLETE: L2/L3 dissection OR (SNB/L1 with ≥4 nodes removed and ≤2 positive)
        - INCOMPLETE_DISSECTION: SNB/L1 with >2 positive nodes
        - INCOMPLETE_SNB: SNB/L1 with <4 nodes removed
        - INSUFFICIENT_PATH_NODE_INFO: SNB/L1 with missing node counts
        - NO_SURG_DATA: No node surgery recorded
        - NA: Missing data
        """
        
        # Check for complete axillary dissection
        has_complete_dissection = any(row.get(col, 0) == 1 
                                     for col in self.rules.NODE_COMPLETE_INDICATORS)
        
        if has_complete_dissection:
            return 'COMPLETE'
        
        # Check for SNB or L1 sampling
        has_snb_l1 = any(row.get(col, 0) == 1 
                        for col in self.rules.NODE_SNB_INDICATORS)
        
        if has_snb_l1:
            node_total = row.get('node_total_removed', np.nan)
            node_positive = row.get('node_involved_count', np.nan)
            
            # All pathology data present
            if pd.notna(node_total) and pd.notna(node_positive):
                if node_total >= self.rules.MIN_NODES_FOR_ADEQUATE_SNB:
                    if node_positive <= self.rules.MAX_POSITIVE_NODES_FOR_SNB_ONLY:
                        return 'COMPLETE'
                    else:
                        return 'INCOMPLETE_DISSECTION'
                else:
                    return 'INCOMPLETE_SNB'
            
            # Missing pathology data
            else:
                return 'INSUFFICIENT_PATH_NODE_INFO'
        
        # No node surgery recorded
        # Check if we have any node pathology data
        if pd.notna(row.get('node_involved_count', np.nan)):
            return 'NO_SURG_DATA'  # Have pathology but no recorded surgery
        else:
            return 'NA'  # No surgery and no pathology data
    
    def classify_all(self) -> pd.DataFrame:
        """
        Classify all cases in the dataframe.
        
        Returns:
            DataFrame with additional columns:
            - breast_surgery_completion: breast surgery status
            - node_surgery_completion: node surgery status
            - locoregional_completion: combined status
            - locoregional_completion_date: date of completion
        """
        
        # Standardize radiation
        self.df['adj_rad_recode'] = self._standardize_radiation()
        
        # Classify breast surgery for each case
        self.df['breast_surgery_completion'] = self.df.apply(
            lambda row: self._classify_breast_surgery(row, row['adj_rad_recode']),
            axis=1
        )
        
        # Classify node surgery for each case
        self.df['node_surgery_completion'] = self.df.apply(
            lambda row: self._classify_node_surgery(row),
            axis=1
        )
        
        # Combine into final locoregional status
        self.df['locoregional_completion'] = self.df.apply(
            self._get_combined_status,
            axis=1
        )
        
        # Get completion dates
        self.df['locoregional_completion_date'] = self.df.apply(
            lambda row: row.get('first_surgery_date', pd.NaT) 
                       if row['locoregional_completion'] in ['COMPLETE', 'PPX_MAST', 'INCOMPLETE_DISSECTION', 'INCOMPLETE_SNB']
                       else pd.NaT,
            axis=1
        )
        
        return self.df
    
    def _get_combined_status(self, row: pd.Series) -> str:
        """Combine breast and node surgery status into final locoregional status"""
        
        breast = row.get('breast_surgery_completion', 'NA')
        node = row.get('node_surgery_completion', 'NA')
        
        # Both complete
        if breast in ['COMPLETE', 'PPX_MAST'] and node == 'COMPLETE':
            return 'COMPLETE'
        
        # Breast complete but incomplete node surgery
        if breast == 'COMPLETE' and node in ['INCOMPLETE_DISSECTION', 'INCOMPLETE_SNB']:
            return 'INCOMPLETE_NODE_SURGERY'
        
        # Breast complete but missing node surgery data
        if breast == 'COMPLETE' and node in ['NO_SURG_DATA', 'INSUFFICIENT_PATH_NODE_INFO']:
            return 'COMPLETE'  # Breast complete is sufficient for PREDICT
        
        # Prophylactic mastectomy (unilateral disease likely)
        if breast == 'PPX_MAST' and node == 'COMPLETE':
            return 'COMPLETE'
        
        # Incomplete breast surgery
        if breast == 'INCOMPLETE' or (breast == 'NO_SURG_DATA_YES_RT' and node in ['NO_SURG_DATA', 'NA']):
            return 'INCOMPLETE'
        
        # No surgical data at all
        if breast == 'NA' and node == 'NA':
            return 'NA'
        
        # Default
        return 'INCOMPLETE'
    
    def get_summary(self, column: str) -> pd.Series:
        """Get value counts for a classification column"""
        if column not in self.df.columns:
            raise ValueError(f"Column '{column}' not found")
        return self.df[column].value_counts()
    
    def get_cases_by_status(self, status: str) -> pd.DataFrame:
        """Get all cases with a specific completion status"""
        return self.df[self.df['locoregional_completion'] == status]


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Example: Load and classify data
    # df = pd.read_csv("surgery_data_restructured.csv")
    
    # Initialize classifier
    # classifier = LocoregionalCompletionClassifier(df)
    
    # Run classification
    # result_df = classifier.classify_all()
    
    # Get summaries
    # print("Breast Surgery Completion:")
    # print(classifier.get_summary('breast_surgery_completion'))
    
    # print("\nNode Surgery Completion:")
    # print(classifier.get_summary('node_surgery_completion'))
    
    # print("\nLocoregional Completion:")
    # print(classifier.get_summary('locoregional_completion'))
    
    # Get incomplete cases for review
    # incomplete = classifier.get_cases_by_status('INCOMPLETE')
    # print(f"\n{len(incomplete)} incomplete cases")
    
    pass