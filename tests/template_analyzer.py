import cv2
import numpy as np
import os
from enhanced_omr import EnhancedOMRProcessor

def analyze_omr_template(image_path):
    """Analyze OMR template structure to understand the layout"""
    print(f"Analyzing OMR template: {image_path}")
    
    # Load and preprocess image
    img = cv2.imread(image_path)
    if img is None:
        print("Could not load image")
        return
    
    # Resize to standard size
    height, width = 700, 700
    img = cv2.resize(img, (width, height))
    
    # Convert to grayscale and apply preprocessing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 1)
    thresh = cv2.threshold(blur, 170, 255, cv2.THRESH_BINARY_INV)[1]
    
    # Save intermediate images for analysis
    cv2.imwrite("debug_original.jpg", img)
    cv2.imwrite("debug_gray.jpg", gray)
    cv2.imwrite("debug_thresh.jpg", thresh)
    
    # Find contours to understand structure
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Draw all contours
    contour_img = img.copy()
    cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)
    cv2.imwrite("debug_contours.jpg", contour_img)
    
    print(f"Found {len(contours)} contours")
    
    # Analyze the layout by examining filled bubbles
    print("\nAnalyzing bubble layout...")
    
    # Look for circular contours (bubbles)
    bubbles = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if 50 < area < 2000:  # Filter by area
            # Check if it's roughly circular
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity > 0.3:  # Reasonably circular
                    x, y, w, h = cv2.boundingRect(contour)
                    bubbles.append((x, y, w, h, area))
    
    print(f"Found {len(bubbles)} potential bubbles")
    
    # Sort bubbles by position (top to bottom, left to right)
    bubbles.sort(key=lambda b: (b[1], b[0]))  # Sort by y first, then x
    
    # Draw detected bubbles
    bubble_img = img.copy()
    for i, (x, y, w, h, area) in enumerate(bubbles[:20]):  # Show first 20
        cv2.rectangle(bubble_img, (x, y), (x+w, y+h), (255, 0, 0), 2)
        cv2.putText(bubble_img, str(i), (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    cv2.imwrite("debug_bubbles.jpg", bubble_img)
    
    return bubbles

def create_improved_omr_processor():
    """Create an improved OMR processor with better template detection"""
    
    class ImprovedOMRProcessor(EnhancedOMRProcessor):
        def __init__(self):
            super().__init__()
            # Define the actual OMR template layout based on analysis
            self.template_config = {
                'questions_per_row': 4,  # 4 choices per question
                'questions_per_column': 25,  # 25 questions per column  
                'total_columns': 4,  # 4 columns of questions
                'total_questions': 100,
                'bubble_threshold': 1000,  # Minimum pixels for filled bubble
            }
        
        def detect_omr_layout(self, img_thresh):
            """Detect the actual OMR layout from the image"""
            height, width = img_thresh.shape
            
            # Find all contours
            contours, _ = cv2.findContours(img_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours to find bubbles
            bubbles = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if 50 < area < 2000:  # Bubble size range
                    x, y, w, h = cv2.boundingRect(contour)
                    # Check aspect ratio (bubbles should be roughly square)
                    aspect_ratio = w / h if h > 0 else 0
                    if 0.5 < aspect_ratio < 2.0:
                        bubbles.append((x, y, w, h, area))
            
            # Sort bubbles by position
            bubbles.sort(key=lambda b: (b[1], b[0]))
            
            return bubbles
        
        def extract_bubble_responses_improved(self, img_warp_colored):
            """Improved bubble response extraction with correct mapping"""
            img_warp_gray = cv2.cvtColor(img_warp_colored, cv2.COLOR_BGR2GRAY)
            img_thresh = cv2.threshold(img_warp_gray, 170, 255, cv2.THRESH_BINARY_INV)[1]
            
            # Detect actual bubble layout
            bubbles = self.detect_omr_layout(img_thresh)
            
            print(f"Detected {len(bubbles)} bubbles")
            
            # Group bubbles into questions
            questions_data = self.group_bubbles_into_questions(bubbles, img_thresh)
            
            # Extract answers
            student_answers = []
            for question_bubbles in questions_data:
                if len(question_bubbles) >= 4:  # Must have at least 4 choices
                    # Check which bubble is filled
                    max_pixels = 0
                    selected_choice = -1
                    
                    for choice_idx, (x, y, w, h, _) in enumerate(question_bubbles[:4]):
                        # Extract bubble region
                        bubble_region = img_thresh[y:y+h, x:x+w]
                        filled_pixels = cv2.countNonZero(bubble_region)
                        
                        if filled_pixels > max_pixels and filled_pixels > self.template_config['bubble_threshold']:
                            max_pixels = filled_pixels
                            selected_choice = choice_idx
                    
                    student_answers.append(selected_choice)
                else:
                    student_answers.append(-1)  # No valid selection
            
            return student_answers[:self.questions]  # Return only required number of questions
        
        def group_bubbles_into_questions(self, bubbles, img_thresh):
            """Group detected bubbles into questions based on layout"""
            height, width = img_thresh.shape
            
            # Divide image into grid sections
            questions_data = []
            
            # Try to detect the grid layout automatically
            if len(bubbles) >= 400:  # Expected 400 bubbles for 100 questions x 4 choices
                # Group bubbles by rows (questions)
                y_positions = [b[1] for b in bubbles]
                unique_y = np.unique(y_positions)
                
                # Find question rows (should be ~25 rows with 4 bubbles each in 4 columns)
                row_tolerance = 20  # pixels
                question_rows = []
                
                current_row = []
                last_y = -1
                
                for bubble in bubbles:
                    x, y, w, h, area = bubble
                    
                    if last_y == -1 or abs(y - last_y) < row_tolerance:
                        current_row.append(bubble)
                    else:
                        if len(current_row) >= 4:  # Valid question row
                            question_rows.append(sorted(current_row, key=lambda b: b[0]))  # Sort by x
                        current_row = [bubble]
                    
                    last_y = y
                
                # Add the last row
                if len(current_row) >= 4:
                    question_rows.append(sorted(current_row, key=lambda b: b[0]))
                
                # Extract questions from rows
                for row in question_rows:
                    # Group every 4 bubbles as a question
                    for i in range(0, len(row) - 3, 4):
                        question_bubbles = row[i:i+4]
                        questions_data.append(question_bubbles)
            
            else:
                # Fallback: Use original grid-based approach
                print("Using fallback grid-based bubble detection")
                questions_data = self.fallback_grid_detection(bubbles, img_thresh)
            
            return questions_data[:self.questions]  # Limit to expected number of questions
        
        def fallback_grid_detection(self, bubbles, img_thresh):
            """Fallback method using grid-based detection"""
            height, width = img_thresh.shape
            
            # Divide into expected grid
            cols = 4  # 4 columns of questions
            rows_per_col = 25  # 25 questions per column
            
            questions_data = []
            
            col_width = width // cols
            row_height = height // rows_per_col
            
            for col in range(cols):
                for row in range(rows_per_col):
                    # Define question region
                    x_start = col * col_width
                    x_end = (col + 1) * col_width
                    y_start = row * row_height
                    y_end = (row + 1) * row_height
                    
                    # Find bubbles in this region
                    question_bubbles = []
                    for bubble in bubbles:
                        bx, by, bw, bh, area = bubble
                        # Check if bubble center is in this region
                        center_x = bx + bw // 2
                        center_y = by + bh // 2
                        
                        if x_start <= center_x < x_end and y_start <= center_y < y_end:
                            question_bubbles.append(bubble)
                    
                    # Sort by x position to get correct choice order (A, B, C, D)
                    question_bubbles.sort(key=lambda b: b[0])
                    questions_data.append(question_bubbles)
            
            return questions_data
        
        def process_omr_sheet(self, image_path, set_type=None):
            """Enhanced OMR processing with improved bubble detection"""
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
                
                # Extract responses using improved method
                student_answers = self.extract_bubble_responses_improved(img_warp_colored)
                
                print(f"Detected {len(student_answers)} student answers")
                print(f"First 10 student answers: {student_answers[:10]}")
                
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
    
    return ImprovedOMRProcessor()

# Test the improved processor
if __name__ == "__main__":
    # First analyze a sample image to understand the template
    sample_image = "DataSets/Set A/Img1.jpeg"
    if os.path.exists(sample_image):
        print("Step 1: Analyzing OMR template...")
        bubbles = analyze_omr_template(sample_image)
        
        print("\nStep 2: Testing improved processor...")
        processor = create_improved_omr_processor()
        results = processor.process_omr_sheet(sample_image)
        
        if results.get("success"):
            print(f"✅ Processing successful!")
            print(f"Score: {results['score']:.1f}%")
            print(f"Set Type: {results['set_type']}")
            print(f"Student answers: {results['student_answers'][:20]}")  # First 20 answers
            
        else:
            print(f"❌ Error: {results.get('error')}")
    else:
        print(f"Sample image not found: {sample_image}")