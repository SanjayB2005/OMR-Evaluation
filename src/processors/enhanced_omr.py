import cv2
import numpy as np
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
import utlis
from typing import List, Tuple, Optional, Dict
from data_handler import OMRDataHandler

class EnhancedOMRProcessor:
    """Enhanced OMR processing system with dynamic configuration"""
    
    def __init__(self, height_img=700, width_img=700, questions=100, choices=4):
        self.height_img = height_img
        self.width_img = width_img
        self.questions = questions
        self.choices = choices
        self.data_handler = OMRDataHandler()
        
        # Load answer keys
        self.answer_keys = self.data_handler.load_answer_keys()
        
    def detect_set_type(self, image_path: str) -> str:
        """Detect set type from image path or content"""
        return self.data_handler.detect_set_from_image(image_path)
    
    def get_answer_key(self, set_type: str) -> Optional[List[int]]:
        """Get answer key for specific set type"""
        return self.data_handler.get_answer_key_for_set(set_type)
    
    def preprocess_image(self, img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Preprocess image for OMR detection"""
        img = cv2.resize(img, (self.width_img, self.height_img))
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_blur = cv2.GaussianBlur(img_gray, (7, 7), 1)
        img_canny = cv2.Canny(img_blur, 10, 70)
        return img, img_gray, img_canny
    
    def find_omr_contours(self, img_canny: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Find OMR sheet and grade area contours"""
        contours, hierarchy = cv2.findContours(img_canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        rect_con = utlis.rectContour(contours)
        
        if len(rect_con) >= 2:
            biggest_points = utlis.getCornerPoints(rect_con[0])
            grade_points = utlis.getCornerPoints(rect_con[1])
            return biggest_points, grade_points
        elif len(rect_con) >= 1:
            biggest_points = utlis.getCornerPoints(rect_con[0])
            return biggest_points, None
        else:
            return None, None
    
    def warp_omr_sheet(self, img: np.ndarray, biggest_points: np.ndarray) -> np.ndarray:
        """Apply perspective transform to get warped OMR sheet"""
        biggest_points = utlis.reorder(biggest_points)
        pts1 = np.float32(biggest_points)
        pts2 = np.float32([[0, 0], [self.width_img, 0], [0, self.height_img], [self.width_img, self.height_img]])
        matrix = cv2.getPerspectiveTransform(pts1, pts2)
        img_warp_colored = cv2.warpPerspective(img, matrix, (self.width_img, self.height_img))
        return img_warp_colored
    
    def extract_bubble_responses(self, img_warp_colored: np.ndarray) -> Tuple[List[int], np.ndarray]:
        """Extract bubble responses from warped OMR sheet with improved detection"""
        img_warp_gray = cv2.cvtColor(img_warp_colored, cv2.COLOR_BGR2GRAY)
        
        # Try multiple threshold values to find the best one
        thresholds = [150, 170, 190, 210]
        best_threshold = 170
        best_score = 0
        
        for thresh_val in thresholds:
            img_thresh = cv2.threshold(img_warp_gray, thresh_val, 255, cv2.THRESH_BINARY_INV)[1]
            
            # Apply morphological operations to clean up the image
            kernel = np.ones((3,3), np.uint8)
            img_thresh = cv2.morphologyEx(img_thresh, cv2.MORPH_CLOSE, kernel)
            img_thresh = cv2.morphologyEx(img_thresh, cv2.MORPH_OPEN, kernel)
            
            # Count total white pixels as a quality metric
            total_pixels = cv2.countNonZero(img_thresh)
            if 1000 < total_pixels < 50000:  # Reasonable range
                if total_pixels > best_score:
                    best_score = total_pixels
                    best_threshold = thresh_val
        
        # Use the best threshold
        img_thresh = cv2.threshold(img_warp_gray, best_threshold, 255, cv2.THRESH_BINARY_INV)[1]
        
        # Apply morphological operations
        kernel = np.ones((3,3), np.uint8)
        img_thresh = cv2.morphologyEx(img_thresh, cv2.MORPH_CLOSE, kernel)
        img_thresh = cv2.morphologyEx(img_thresh, cv2.MORPH_OPEN, kernel)
        
        print(f"Using threshold: {best_threshold}")
        
        # Split into boxes using the corrected layout
        boxes = self.split_boxes_dynamic(img_thresh, self.questions, self.choices)
        
        print(f"Total boxes created: {len(boxes)}")
        
        # Initialize pixel value matrix with correct dimensions
        my_pixel_val = np.zeros((self.questions, self.choices))
        
        # Process boxes and map them correctly to questions and choices
        box_index = 0
        for question in range(self.questions):
            for choice in range(self.choices):
                if box_index < len(boxes):
                    total_pixels = cv2.countNonZero(boxes[box_index])
                    my_pixel_val[question][choice] = total_pixels
                    box_index += 1
        
        # Debug: Print pixel values for first few questions
        print("Pixel values for first 5 questions:")
        for q in range(min(5, self.questions)):
            print(f"Q{q+1}: {my_pixel_val[q]}")
        
        # Find selected answers for each question
        my_index = []
        for question in range(self.questions):
            question_pixels = my_pixel_val[question]
            max_pixels = np.max(question_pixels)
            
            # Adaptive threshold based on image characteristics
            # Lower threshold for better detection
            min_threshold = 200  # Reduced from 500
            
            # Only consider it marked if above threshold
            if max_pixels > min_threshold:
                selected_choice = np.argmax(question_pixels)
                my_index.append(selected_choice)
                
                # Debug output for first few questions
                if question < 5:
                    choice_letter = chr(ord('A') + selected_choice)
                    print(f"Q{question+1}: Selected {choice_letter} (pixels: {max_pixels})")
            else:
                # Check if there's a clear relative winner even below absolute threshold
                if max_pixels > 0:
                    # Calculate relative dominance
                    sorted_pixels = np.sort(question_pixels)[::-1]  # Sort descending
                    if len(sorted_pixels) >= 2 and sorted_pixels[0] > sorted_pixels[1] * 1.5:
                        # Clear winner with 50% more pixels than second choice
                        selected_choice = np.argmax(question_pixels)
                        my_index.append(selected_choice)
                        if question < 5:
                            choice_letter = chr(ord('A') + selected_choice)
                            print(f"Q{question+1}: Selected {choice_letter} (pixels: {max_pixels}) - relative winner")
                    else:
                        my_index.append(-1)  # No clear answer
                        if question < 5:
                            print(f"Q{question+1}: No clear answer (max pixels: {max_pixels})")
                else:
                    my_index.append(-1)  # No answer
                    if question < 5:
                        print(f"Q{question+1}: No answer detected")
        
        return my_index, my_pixel_val
    
    def split_boxes_dynamic(self, img: np.ndarray, questions: int, choices: int) -> List[np.ndarray]:
        """Dynamically split image into answer boxes with correct layout mapping"""
        if questions == 100 and choices == 4:
            # For 100 questions with 4 choices, the typical OMR layout is:
            # 25 questions per column, 4 columns, each question has 4 choices arranged horizontally
            
            boxes = []
            rows_per_section = 25  # 25 questions per column
            sections = 4  # 4 columns
            
            # Calculate dimensions
            section_width = img.shape[1] // sections
            question_height = img.shape[0] // rows_per_section
            
            # For each section (column)
            for section in range(sections):
                section_start_x = section * section_width
                section_end_x = (section + 1) * section_width
                section_img = img[:, section_start_x:section_end_x]
                
                # For each question in this section
                for row in range(rows_per_section):
                    question_start_y = row * question_height
                    question_end_y = (row + 1) * question_height
                    question_img = section_img[question_start_y:question_end_y, :]
                    
                    # Split question into 4 choices (A, B, C, D from left to right)
                    choice_width = question_img.shape[1] // choices
                    
                    for choice in range(choices):
                        choice_start_x = choice * choice_width
                        choice_end_x = (choice + 1) * choice_width
                        choice_box = question_img[:, choice_start_x:choice_end_x]
                        boxes.append(choice_box)
            
            return boxes
        else:
            # Original logic for smaller grids
            rows = np.vsplit(img, questions)
            boxes = []
            for r in rows:
                cols = np.hsplit(r, choices)
                for box in cols:
                    boxes.append(box)
            return boxes
    
    def calculate_score(self, student_answers: List[int], correct_answers: List[int]) -> Tuple[float, List[int]]:
        """Calculate score and generate grading list"""
        grading = []
        for i in range(len(correct_answers)):
            if i < len(student_answers) and student_answers[i] == correct_answers[i]:
                grading.append(1)
            else:
                grading.append(0)
        
        score = (sum(grading) / len(correct_answers)) * 100
        return score, grading
    
    def process_omr_sheet(self, image_path: str, set_type: Optional[str] = None) -> Dict:
        """
        Process a complete OMR sheet and return results
        """
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            return {"error": "Could not load image"}
        
        # Auto-detect set type if not provided
        if set_type is None:
            set_type = self.detect_set_type(image_path)
        
        # Get answer key
        correct_answers = self.get_answer_key(set_type)
        if correct_answers is None:
            return {"error": f"No answer key found for set type: {set_type}"}
        
        try:
            # Preprocess image
            img_resized, img_gray, img_canny = self.preprocess_image(img)
            
            # Find contours
            biggest_points, grade_points = self.find_omr_contours(img_canny)
            
            if biggest_points is None:
                return {"error": "Could not detect OMR sheet contours"}
            
            # Warp OMR sheet
            img_warp_colored = self.warp_omr_sheet(img_resized, biggest_points)
            
            # Extract responses
            student_answers, pixel_values = self.extract_bubble_responses(img_warp_colored)
            
            # Calculate score
            score, grading = self.calculate_score(student_answers, correct_answers)
            
            # Prepare results
            results = {
                "image_path": image_path,
                "set_type": set_type,
                "student_answers": student_answers,
                "correct_answers": correct_answers,
                "grading": grading,
                "score": score,
                "total_questions": len(correct_answers),
                "correct_count": sum(grading),
                "wrong_count": len(grading) - sum(grading),
                "processed_image": img_warp_colored,
                "success": True
            }
            
            return results
            
        except Exception as e:
            return {"error": f"Processing failed: {str(e)}", "success": False}
    
    def visualize_results(self, results: Dict, save_path: Optional[str] = None) -> np.ndarray:
        """Create visualization of OMR processing results"""
        if not results.get("success", False):
            return None
        
        img = results["processed_image"].copy()
        student_answers = results["student_answers"]
        grading = results["grading"]
        correct_answers = results["correct_answers"]
        
        # Use modified utlis functions for visualization
        utlis.showAnswers(img, student_answers, grading, correct_answers, self.questions, self.choices)
        utlis.drawGrid(img, self.questions, self.choices)
        
        # Add score text
        score_text = f"Score: {results['score']:.1f}% ({results['correct_count']}/{results['total_questions']})"
        cv2.putText(img, score_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(img, f"Set: {results['set_type']}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        if save_path:
            cv2.imwrite(save_path, img)
        
        return img

# Test the enhanced OMR processor
if __name__ == "__main__":
    processor = EnhancedOMRProcessor()
    
    # Test with a sample image
    sample_image = "DataSets/Set A/Img1.jpeg"
    if os.path.exists(sample_image):
        print(f"Processing {sample_image}...")
        results = processor.process_omr_sheet(sample_image)
        
        if results.get("success"):
            print(f"Score: {results['score']:.1f}%")
            print(f"Set Type: {results['set_type']}")
            print(f"Correct: {results['correct_count']}/{results['total_questions']}")
            
            # Visualize results
            viz_img = processor.visualize_results(results, "test_result.jpg")
            print("Visualization saved as test_result.jpg")
        else:
            print(f"Error: {results.get('error')}")
    else:
        print(f"Sample image not found: {sample_image}")