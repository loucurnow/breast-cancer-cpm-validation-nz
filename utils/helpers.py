from pathlib import Path

def check_and_prompt(func):
    """Decorator to check for file existence before running the transformation."""
    def wrapper(*args, **kwargs):
        # We assume the second argument is out_dir (based on your structure)
        # Or we can look for 'out_dir' in kwargs
        out_dir = kwargs.get('out_dir', args[1] if len(args) > 1 else Path('datasets/bcfnz/pickle/processed/strother'))
        
        # We need to know the expected filename. 
        # Assuming each function saves to a specific name, e.g., f"tidy_{func.__name__.split('_')[1]}.pkl"
        print(func.__name__)
        if func.__name__ == 'generate_strother_files':
            file_name = 'merged_breast_tables.pickle'
        elif func.__name__ == 'transform_surgery_primary':
            file_name = "tidy_surgery.pickle"
        elif func.__name__ == 'transform_followup':
            file_name = 'tidy_fu.pickle'
        elif func.__name__ == 'transform_biological_markers':
            file_name = 'tidy_biological_markers.pickle'
        else:
            file_name = f"tidy_{func.__name__.split('_')[-1]}.pickle"
        target_path = out_dir / file_name

        print("Checking target path:", target_path)
        
        if target_path.exists():
            choice = input(f"File '{target_path}' already exists. Overwrite? (Y/N) [default: N]: ").lower()
            if choice != 'y':
                print(f"Skipping transformation for {func.__name__}...")
                return None
        
        return func(*args, **kwargs)
    return wrapper