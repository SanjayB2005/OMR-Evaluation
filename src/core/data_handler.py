import pandas as pd
import cv2
import numpy as np
import os
import re
from typing import Dict, List, Tuple, Optional

class OMRDataHandler:
    """Handles loading and processing of OMR datasets and answer keys"""
    
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self.answer_keys = {}
        self.datasets = {}
        
    def load_answer_keys(self) -> Dict[str, List[int]]:
        """
        Load answer keys from Excel files and convert to numerical format
        Reads answers column-wise from Excel sheets
        Returns: Dictionary with set names as keys and answer lists as values
        """
        answer_key_path = os.path.join(self.base_path, "AnswerKey")
        
        for file_name in os.listdir(answer_key_path):
            if file_name.endswith('.xlsx') and not file_name.startswith('~'):
                set_name = file_name.replace('.xlsx', '').replace(' ', '_')
                file_path = os.path.join(answer_key_path, file_name)
                
                try:
                    df = pd.read_excel(file_path)
                    # Remove empty rows if they exist
                    df = df.dropna(how='all')
                    
                    # Extract answers column-wise
                    answers = []
                    
                    # Process each column (subject)
                    for col in df.columns:
                        if col.strip():  # Skip empty column names
                            column_answers = []
                            
                            for _, row in df.iterrows():
                                cell_value = row[col]
                                if pd.notna(cell_value):
                                    # Extract letter from format like "1 - a", "21 - a", "81. a"
                                    cell_str = str(cell_value).lower().strip()
                                    # Look for patterns like "1 - a", "21 - a", "81. a"
                                    match = re.search(r'[abcd]', cell_str)
                                    if match:
                                        # Convert letter to number (a=0, b=1, c=2, d=3)
                                        letter = match.group()
                                        answer_num = ord(letter) - ord('a')
                                        column_answers.append(answer_num)
                            
                            # Add this column's answers to the main answer list
                            answers.extend(column_answers)
                            print(f"  Column '{col}': {len(column_answers)} answers")
                    
                    self.answer_keys[set_name] = answers
                    print(f"Loaded {len(answers)} total answers for {set_name}")
                    
                    # Debug: Show first 10 answers
                    if answers:
                        first_10 = answers[:10]
                        first_10_letters = [chr(ord('A') + ans) for ans in first_10]
                        print(f"  First 10 answers: {first_10_letters}")
                    
                except Exception as e:
                    print(f"Error loading {file_name}: {e}")
                    import traceback
                    traceback.print_exc()
        
        return self.answer_keys
    
    def load_datasets(self) -> Dict[str, List[str]]:
        """
        Load image paths from dataset folders
        Returns: Dictionary with set names as keys and image path lists as values
        """
        datasets_path = os.path.join(self.base_path, "DataSets")
        
        for set_folder in os.listdir(datasets_path):
            set_path = os.path.join(datasets_path, set_folder)
            if os.path.isdir(set_path):
                set_name = set_folder.replace(' ', '_')
                image_paths = []
                
                for img_file in os.listdir(set_path):
                    if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        img_path = os.path.join(set_path, img_file)
                        image_paths.append(img_path)
                
                self.datasets[set_name] = sorted(image_paths)
                print(f"Loaded {len(image_paths)} images for {set_name}")
        
        return self.datasets
    
    def detect_set_from_image(self, image_path: str) -> str:
        """
        Detect which set an image belongs to based on folder structure
        """
        if "Set A" in image_path or "Set_A" in image_path:
            return "Set_A"
        elif "Set B" in image_path or "Set_B" in image_path:
            return "Set_B"
        else:
            return "unknown"
    
    def get_answer_key_for_set(self, set_name: str) -> Optional[List[int]]:
        """
        Get answer key for a specific set
        """
        return self.answer_keys.get(set_name)
    
    def prepare_training_data(self) -> List[Tuple[str, str, List[int]]]:
        """
        Prepare training data by combining images with their corresponding answer keys
        Returns: List of tuples (image_path, set_name, answer_key)
        """
        training_data = []
        
        for set_name, image_paths in self.datasets.items():
            answer_key = self.get_answer_key_for_set(set_name)
            if answer_key:
                for img_path in image_paths:
                    training_data.append((img_path, set_name, answer_key))
        
        return training_data
    
    def validate_data_consistency(self) -> bool:
        """
        Validate that datasets and answer keys are consistent
        """
        for set_name in self.datasets.keys():
            if set_name not in self.answer_keys:
                print(f"Warning: No answer key found for dataset {set_name}")
                return False
        
        for set_name in self.answer_keys.keys():
            if set_name not in self.datasets:
                print(f"Warning: No dataset found for answer key {set_name}")
                return False
        
        print("Data consistency check passed!")
        return True
    
    def get_summary(self) -> Dict:
        """
        Get summary of loaded data
        """
        summary = {
            'answer_keys': {k: len(v) for k, v in self.answer_keys.items()},
            'datasets': {k: len(v) for k, v in self.datasets.items()},
            'total_images': sum(len(v) for v in self.datasets.values()),
            'total_questions': sum(len(v) for v in self.answer_keys.values()) // len(self.answer_keys) if self.answer_keys else 0
        }
        return summary

# Test the data handler
if __name__ == "__main__":
    handler = OMRDataHandler()
    
    # Load data
    print("Loading answer keys...")
    answer_keys = handler.load_answer_keys()
    
    print("\nLoading datasets...")
    datasets = handler.load_datasets()
    
    print("\nData Summary:")
    summary = handler.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    print("\nValidating data consistency...")
    handler.validate_data_consistency()
    
    print("\nTraining data sample:")
    training_data = handler.prepare_training_data()
    for i, (img_path, set_name, answer_key) in enumerate(training_data[:3]):
        print(f"{i+1}. {os.path.basename(img_path)} - {set_name} - {len(answer_key)} answers")