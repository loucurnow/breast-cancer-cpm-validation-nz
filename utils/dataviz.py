import graphviz
import pandas as pd
import graphviz


def cohort_flowchart(df, filepath, criteria_dict):
    dot = graphviz.Digraph(comment='Cohort Selection', format='png')
    # Use TB (Top-to-Bottom) for the main stack
    dot.attr(rankdir='TB') 
    dot.attr('node', shape='box', style='filled', fontname='Helvetica')

    current_df = df.copy()
    prev_count = len(current_df)
    
    dot.node('start', f'Total Cohort\n(n={prev_count})', color='lightpink')
    last_node = 'start'

    for label, col in criteria_dict.items():
        filtered_df = current_df[current_df[col] == True]
        current_count = len(filtered_df)
        excluded = prev_count - current_count
        
        node_name = f"node_{col}"
        dot.node(node_name, f'{label}\n(n={current_count})', color='lightpink')
        dot.edge(last_node, node_name)
        
        if excluded > 0:
            excl_name = f"excl_{col}"
            # Define subgraph to group them horizontally
            with dot.subgraph() as s: # type: ignore
                s.attr(rank='same')
                s.node(excl_name, f'Excluded: {excluded}', shape='box', color='lightgrey', fontsize='12')
            
            # Link node to exclusion to force the right-side placement
            dot.edge(last_node, excl_name)
        
        current_df = filtered_df
        prev_count = current_count
        last_node = node_name

    dot.render(filepath, cleanup=True)
    print(f"Flowchart saved to {filepath}.png")

# --- Example Usage ---
# criteria = {
#     "Female": "cohort_female",
#     "First Diagnosis": "cohort_first_diagnosis",
#     "Age 20-85": "cohort_dx_20_85",
#     "No Neoadjuvant": "cohort_no_neoadj",
#     "No Mets at Baseline": "cohort_no_mets_baseline",
#     "No DCIS": "cohort_no_dcis",
#     "Primary Surgery": "cohort_primary_surgery"
# }
# cohort_flowchart(your_df, "cohort_selection_process", criteria)