import cv2
import numpy as np
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from data_handler import OMRDataHandler

class CorrectedOMRProcessor:
    """OMR processor specifically designed to fix bubble-to-answer mapping issues"""
    
    def __init__(self):
        self.data_handler = OMRDataHandler()
        self.data_handler.load_answer_keys()
        self.questions = 100
        self.choices = 4
        
    def process_omr_sheet(self, image_path, set_type=None):
        """Process OMR sheet with corrected mapping logic"""
        try:
            # Read and prepare image
            img = cv2.imread(image_path)
            if img is None:
                return {"success": False, "error": "Could not read image"}
            
            # Resize for consistent processing
            img = cv2.resize(img, (800, 1200))  # Larger size for better detail
            original_img = img.copy()
            
            # Convert to grayscale and apply advanced preprocessing
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Use CLAHE for better contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            
            # Apply Gaussian blur
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Multiple thresholding approaches
            _, thresh_otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            thresh_adaptive = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                   cv2.THRESH_BINARY_INV, 15, 3)
            
            # Combine both threshold methods
            thresh = cv2.bitwise_or(thresh_otsu, thresh_adaptive)
            
            # Clean up with morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            
            # Systematic grid-based approach to avoid mapping errors
            student_answers = self.extract_answers_systematic_grid(thresh, img.shape)
            
            # Determine set type and calculate results
            if set_type and set_type != "Custom":
                # Use provided set type
                final_set_type = set_type
            else:
                # Auto-detect set type
                final_set_type = self.determine_set_type(student_answers)
            
            correct_answers = self.data_handler.answer_keys.get(final_set_type, [])
            score, correct_count = self.calculate_score(student_answers, correct_answers)
            
            # Save comprehensive debug output
            self.save_debug_analysis(original_img, thresh, student_answers, correct_answers)
            
            return {
                "success": True,
                "score": score,
                "correct_count": correct_count,
                "total_questions": len(correct_answers),
                "student_answers": student_answers,
                "correct_answers": correct_answers,
                "set_type": final_set_type
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def extract_answers_systematic_grid(self, thresh_img, img_shape):
        """Extract answers using systematic grid approach to prevent mapping errors"""
        height, width = thresh_img.shape
        
        # Try different systematic approaches
        approaches = [
            self.approach_column_based(thresh_img),
            self.approach_row_based(thresh_img),
            self.approach_block_based(thresh_img),
        ]
        
        # Evaluate each approach and select the best one
        best_answers = []
        best_score = 0
        
        for approach_name, answers in approaches:
            # Calculate how many answers were detected (non -1 values)
            detected_count = sum(1 for ans in answers if ans >= 0)
            score = detected_count / len(answers) if answers else 0
            
            print(f"{approach_name}: detected {detected_count}/100 answers (score: {score:.2f})")
            
            if score > best_score:
                best_score = score
                best_answers = answers
        
        return best_answers
    
    def approach_column_based(self, thresh_img):
        """Column-based approach: divide image into 4 columns for A,B,C,D"""
        height, width = thresh_img.shape
        answers = []
        
        # Divide image into 4 equal columns (A, B, C, D)
        col_width = width // 4
        
        # Divide into rows for questions
        questions_per_section = 25  # 100 questions / 4 sections = 25 each
        row_height = height // questions_per_section
        
        for section in range(4):  # 4 sections
            section_start_x = section * col_width
            section_end_x = (section + 1) * col_width
            
            for question in range(questions_per_section):
                question_start_y = question * row_height
                question_end_y = (question + 1) * row_height
                
                # Extract this question's area
                question_roi = thresh_img[question_start_y:question_end_y, 
                                        section_start_x:section_end_x]
                
                # Divide question area into 4 choice columns
                choice_width = question_roi.shape[1] // 4
                choice_pixels = []
                
                for choice in range(4):
                    choice_start_x = choice * choice_width
                    choice_end_x = (choice + 1) * choice_width
                    
                    choice_roi = question_roi[:, choice_start_x:choice_end_x]
                    pixels = cv2.countNonZero(choice_roi)
                    choice_pixels.append(pixels)
                
                # Find the choice with most pixels
                if choice_pixels and max(choice_pixels) > 50:
                    selected_choice = choice_pixels.index(max(choice_pixels))
                    answers.append(selected_choice)
                else:
                    answers.append(-1)
        
        return ("Column-based", answers)
    
    def approach_row_based(self, thresh_img):
        """Row-based approach: each row is one question with 4 choices"""
        height, width = thresh_img.shape
        answers = []
        
        # Divide into 100 rows for 100 questions
        row_height = height // 100
        
        for question in range(100):
            question_start_y = question * row_height
            question_end_y = (question + 1) * row_height
            
            # Extract this question's row
            question_row = thresh_img[question_start_y:question_end_y, :]
            
            # Divide row into 4 choice columns
            choice_width = width // 4
            choice_pixels = []
            
            for choice in range(4):
                choice_start_x = choice * choice_width
                choice_end_x = (choice + 1) * choice_width
                
                choice_roi = question_row[:, choice_start_x:choice_end_x]
                pixels = cv2.countNonZero(choice_roi)
                choice_pixels.append(pixels)
            
            # Find the choice with most pixels
            if choice_pixels and max(choice_pixels) > 30:
                selected_choice = choice_pixels.index(max(choice_pixels))
                answers.append(selected_choice)
            else:
                answers.append(-1)
        
        return ("Row-based", answers)
    
    def approach_block_based(self, thresh_img):
        """Block-based approach: 10x10 grid of questions"""
        height, width = thresh_img.shape
        answers = []
        
        # Create 10x10 grid (100 total blocks)
        blocks_per_row = 10
        blocks_per_col = 10
        
        block_height = height // blocks_per_col
        block_width = width // blocks_per_row
        
        for row in range(blocks_per_col):
            for col in range(blocks_per_row):
                block_start_y = row * block_height
                block_end_y = (row + 1) * block_height
                block_start_x = col * block_width
                block_end_x = (col + 1) * block_width
                
                # Extract this block
                block_roi = thresh_img[block_start_y:block_end_y, 
                                     block_start_x:block_end_x]
                
                # Divide block into 4 sub-areas for choices
                sub_height = block_roi.shape[0] // 2
                sub_width = block_roi.shape[1] // 2
                
                choice_pixels = []
                
                # A (top-left), B (top-right), C (bottom-left), D (bottom-right)
                choice_positions = [
                    (0, sub_height, 0, sub_width),              # A: top-left
                    (0, sub_height, sub_width, block_roi.shape[1]),  # B: top-right
                    (sub_height, block_roi.shape[0], 0, sub_width),  # C: bottom-left
                    (sub_height, block_roi.shape[0], sub_width, block_roi.shape[1])  # D: bottom-right
                ]
                
                for y1, y2, x1, x2 in choice_positions:
                    if y2 <= block_roi.shape[0] and x2 <= block_roi.shape[1]:
                        choice_area = block_roi[y1:y2, x1:x2]
                        pixels = cv2.countNonZero(choice_area)
                        choice_pixels.append(pixels)
                    else:
                        choice_pixels.append(0)
                
                # Find the choice with most pixels
                if choice_pixels and max(choice_pixels) > 20:
                    selected_choice = choice_pixels.index(max(choice_pixels))
                    answers.append(selected_choice)
                else:
                    answers.append(-1)
        
        return ("Block-based", answers)
    
    def determine_set_type(self, student_answers):
        """Determine set type"""
        scores = {}
        for set_name, correct_answers in self.data_handler.answer_keys.items():
            score, _ = self.calculate_score(student_answers, correct_answers)
            scores[set_name] = score
        
        return max(scores, key=scores.get) if scores else "Set_A"
    
    def calculate_score(self, student_answers, correct_answers):
        """Calculate score"""
        if not correct_answers:
            return 0.0, 0
        
        correct_count = sum(1 for s, c in zip(student_answers, correct_answers) 
                          if s == c and s >= 0)
        total = len(correct_answers)
        score = (correct_count / total) * 100 if total > 0 else 0
        
        return score, correct_count
    
    def save_debug_analysis(self, original_img, thresh_img, student_answers, correct_answers):
        """Save debug analysis to understand mapping"""
        # Save threshold image
        cv2.imwrite("debug_corrected_threshold.jpg", thresh_img)
        
        # Create mapping visualization
        debug_img = original_img.copy()
        height, width = debug_img.shape[:2]
        
        # Overlay grid to show how we're interpreting the layout
        # Draw grid lines
        for i in range(1, 4):  # Vertical lines for choices
            x = (width * i) // 4
            cv2.line(debug_img, (x, 0), (x, height), (255, 255, 255), 2)
        
        for i in range(1, 100):  # Horizontal lines for questions (every 12 pixels for 100 questions)
            y = (height * i) // 100
            cv2.line(debug_img, (0, y), (width, y), (255, 255, 255), 1)
        
        # Mark detected answers
        row_height = height // 100
        col_width = width // 4
        
        choice_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        
        for q_num, student_ans in enumerate(student_answers[:20]):  # Show first 20
            if student_ans >= 0:
                y_center = (q_num * row_height) + (row_height // 2)
                x_center = (student_ans * col_width) + (col_width // 2)
                
                color = choice_colors[student_ans]
                cv2.circle(debug_img, (x_center, y_center), 10, color, -1)
                cv2.putText(debug_img, f"Q{q_num+1}", (x_center-15, y_center-15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        cv2.imwrite("debug_corrected_mapping.jpg", debug_img)
        
        # Create answer comparison chart
        comparison_img = np.ones((600, 800, 3), dtype=np.uint8) * 255
        
        for i in range(min(20, len(student_answers))):
            student = student_answers[i]
            correct = correct_answers[i] if i < len(correct_answers) else -1
            
            y_pos = 30 + (i * 25)
            
            # Question number
            cv2.putText(comparison_img, f"Q{i+1:2d}:", (10, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            
            # Student answer
            student_text = chr(ord('A') + student) if student >= 0 else "None"
            color = (0, 200, 0) if student == correct else (0, 0, 200)
            cv2.putText(comparison_img, f"Student: {student_text}", (80, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
            
            # Correct answer
            correct_text = chr(ord('A') + correct) if correct >= 0 else "None"
            cv2.putText(comparison_img, f"Correct: {correct_text}", (250, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            
            # Status
            status = "✓" if student == correct else "✗"
            status_color = (0, 200, 0) if student == correct else (0, 0, 200)
            cv2.putText(comparison_img, status, (400, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        
        cv2.imwrite("debug_corrected_comparison.jpg", comparison_img)
        
        print("Debug files saved: debug_corrected_*.jpg")

# Test the corrected processor
if __name__ == "__main__":
    processor = CorrectedOMRProcessor()
    
    # Test with sample image
    sample_image = "DataSets/Set A/Img1.jpeg"
    if os.path.exists(sample_image):
        print(f"Testing corrected OMR processor with {sample_image}...")
        print("=" * 60)
        
        results = processor.process_omr_sheet(sample_image)
        
        if results.get("success"):
            print(f"\n✅ FINAL RESULTS:")
            print(f"Score: {results['score']:.1f}%")
            print(f"Set Type: {results['set_type']}")
            print(f"Correct: {results['correct_count']}/{results['total_questions']}")
            
            # Count non-empty answers
            non_empty = sum(1 for ans in results['student_answers'] if ans >= 0)
            print(f"Detected answers: {non_empty}/100")
            
            print(f"\nFirst 20 answers (showing mapping):")
            print("Q#  | Student | Correct | Status")
            print("-" * 35)
            
            for i in range(min(20, len(results['student_answers']))):
                student = results['student_answers'][i]
                correct = results['correct_answers'][i]
                student_letter = chr(ord('A') + student) if student >= 0 else "None"
                correct_letter = chr(ord('A') + correct)
                status = "✅ MATCH" if student == correct else "❌ DIFF"
                print(f"Q{i+1:2d} |    {student_letter:1s}    |    {correct_letter:1s}    | {status}")
                
        else:
            print(f"❌ Error: {results.get('error')}")
    else:
        print(f"Sample image not found: {sample_image}")