import cv2
import numpy as np
import os
import sys
import json

# Add the src/core directory to path to find data_handler
current_dir = os.path.dirname(os.path.abspath(__file__))
core_dir = os.path.join(current_dir, '..', 'core')
main_dir = os.path.join(current_dir, '..', '..')
sys.path.append(core_dir)
sys.path.append(main_dir)

from data_handler import OMRDataHandler

def sort_bubbles_for_choices(bubble_row, validate_order=True):
    """Sort bubbles in a row left-to-right and validate A,B,C,D ordering"""
    if not bubble_row:
        return []
    
    # Sort by X coordinate (left to right)
    sorted_bubbles = sorted(bubble_row, key=lambda bubble: bubble[0])  # bubble[0] is X coordinate
    
    if validate_order and len(sorted_bubbles) >= 4:
        # Verify the bubbles are reasonably spaced for A,B,C,D layout
        x_positions = [bubble[0] for bubble in sorted_bubbles[:4]]
        
        # Check if bubbles are roughly evenly spaced
        gaps = [x_positions[i+1] - x_positions[i] for i in range(len(x_positions)-1)]
        if gaps:
            avg_gap = sum(gaps) / len(gaps)
            # All gaps should be roughly similar (within 50% of average)
            irregular_gaps = [gap for gap in gaps if abs(gap - avg_gap) > avg_gap * 0.5]
            
            if len(irregular_gaps) > 1:  # More than 1 irregular gap suggests wrong grouping
                print(f"Warning: Irregular bubble spacing detected - gaps: {gaps}")
    
    return sorted_bubbles

def map_choice_index_to_letter(choice_index, validate_range=True):
    """Map choice index (0,1,2,3) to letter (A,B,C,D) with validation"""
    if validate_range and (choice_index < 0 or choice_index > 3):
        return None
    
    if choice_index < 0:
        return None
        
    choice_letters = ['A', 'B', 'C', 'D']
    return choice_letters[choice_index] if choice_index < len(choice_letters) else None

class TrainedPrecisionOMRProcessor:
    """Ultimate OMR processor combining multiple detection methods for maximum accuracy"""
    
    def __init__(self):
        self.data_handler = OMRDataHandler(base_path=os.path.join(os.path.dirname(__file__), '..', '..'))
        self.data_handler.load_answer_keys()
        self.questions = 100
        self.choices = 4
        
        # Enhanced training parameters for better accuracy
        self.training_params = {
            'area_min': 80,
            'area_max': 800,
            'circularity_min': 0.4,
            'aspect_ratio_min': 0.5,
            'aspect_ratio_max': 2.0,
            'size_min': 5,
            'size_max': 50,
            'extent_min': 0.3,
            'solidity_min': 0.5,
            'fill_variance_threshold': 0.005,
            'min_fill_score': 0.04,
            'adaptive_block_size': 15,
            'adaptive_c': 5
        }
        
        self.load_training_params()
    
    def load_training_params(self):
        """Load previously trained parameters if available"""
        if os.path.exists('trained_params.json'):
            try:
                with open('trained_params.json', 'r') as f:
                    saved_params = json.load(f)
                    self.training_params.update(saved_params)
                print("Loaded trained parameters")
            except:
                print("Using default parameters")
    
    def save_training_params(self):
        """Save trained parameters"""
        with open('trained_params.json', 'w') as f:
            json.dump(self.training_params, f, indent=2)
        print("Saved trained parameters")
    
    def process_omr_sheet(self, image_path, set_type=None):
        """Process OMR sheet using hybrid Ultimate approach with multiple validation methods"""
        try:
            # Read and preprocess image
            img = cv2.imread(image_path)
            if img is None:
                return {"success": False, "error": "Could not read image"}
            
            # Resize for consistency
            img = cv2.resize(img, (600, 800))
            original_img = img.copy()
            
            # Enhanced preprocessing pipeline
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply CLAHE for better contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            
            # Apply bilateral filter to reduce noise while preserving edges
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Try multiple methods and use the best result
            methods = [
                self.method_contour_based(filtered, original_img),
                self.method_grid_based(filtered),
                self.method_adaptive_threshold(filtered),
                self.method_mark_detection(filtered),  # ORIGINAL: Specialized mark detection
                self.method_mark_detection_improved(filtered),  # IMPROVED: Fixed bias version
                self.method_mark_detection_normalized(filtered),  # NORMALIZED: Background-corrected version
            ]
            
            # Evaluate and select best method
            best_answers = self.select_best_method(methods)
            
            # Determine set type and calculate score
            if set_type and set_type != "Custom":
                # Use provided set type if specified
                determined_set_type = set_type
            else:
                # Auto-detect set type
                determined_set_type = self.determine_set_type(best_answers)
            
            correct_answers = self.data_handler.answer_keys.get(determined_set_type, [])
            score, correct_count = self.calculate_score(best_answers, correct_answers)
            
            # Save comprehensive debug
            self.save_ultimate_debug(original_img, best_answers, correct_answers)
            
            return {
                "success": True,
                "score": score,
                "correct_count": correct_count,
                "total_questions": len(correct_answers),
                "student_answers": best_answers,
                "correct_answers": correct_answers,
                "set_type": determined_set_type,
                "detected_questions": len([a for a in best_answers if a >= 0])
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def method_contour_based(self, gray_img, original_img):
        """Enhanced contour-based detection with CORRECTED bubble grouping for D,B,D pattern"""
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY_INV, 15, 5)
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Enhanced bubble filtering with more specific criteria
        bubble_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 50 < area < 400:  # Adjusted bubble size range
                # Enhanced shape validation
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.3:  # Relaxed circularity
                        x, y, w, h = cv2.boundingRect(contour)
                        aspect_ratio = w / h if h > 0 else 0
                        if 0.4 < aspect_ratio < 2.5:  # Relaxed aspect ratio
                            bubble_contours.append(contour)
        
        print(f"Found {len(bubble_contours)} potential bubble contours")
        
        # Group bubbles into questions with CORRECTED logic for 5-subject layout
        bubble_centers = []
        for contour in bubble_contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                bubble_centers.append((cx, cy, contour))
        
        # Sort by y-coordinate first (top to bottom)
        bubble_centers.sort(key=lambda x: x[1])
        
        # CORRECTED: Group into horizontal rows, then analyze each row for 5 subjects × 4 choices
        questions_bubbles = []
        if bubble_centers:
            current_row = []
            current_y = bubble_centers[0][1]
            row_tolerance = 15  # Increased tolerance for same row
            
            for cx, cy, contour in bubble_centers:
                if abs(cy - current_y) <= row_tolerance:
                    current_row.append((cx, cy, contour))
                else:
                    # Process this row for multiple subjects
                    if len(current_row) >= 8:  # Need at least 8 bubbles for reasonable row (2 subjects × 4 choices)
                        # CORRECTED: Use proper sorting function
                        sorted_row = sort_bubbles_for_choices(current_row, validate_order=False)
                        
                        # Try to detect 5 subject groups within this row
                        subject_groups = self.group_bubbles_into_subjects(sorted_row)
                        questions_bubbles.extend(subject_groups)
                    
                    current_row = [(cx, cy, contour)]
                    current_y = cy
            
            # Process the last row
            if len(current_row) >= 8:
                sorted_row = sort_bubbles_for_choices(current_row, validate_order=False)
                subject_groups = self.group_bubbles_into_subjects(sorted_row)
                questions_bubbles.extend(subject_groups)
        
        print(f"Grouped into {len(questions_bubbles)} question groups")
        
        # Extract answers using enhanced fill analysis
        student_answers = []
        for q_num, bubble_row in enumerate(questions_bubbles):
            if q_num >= self.questions:
                break
            
            if len(bubble_row) < 2:
                student_answers.append(-1)
                continue
            
            # Enhanced fill analysis for CORRECTED bubble detection
            choice_scores = []
            
            for choice_idx, (cx, cy, contour) in enumerate(bubble_row[:self.choices]):
                # Create mask and analyze fill
                mask = np.zeros(gray_img.shape, dtype=np.uint8)
                cv2.fillPoly(mask, [contour], 255)
                
                masked_pixels = gray_img[mask > 0]
                if len(masked_pixels) > 0:
                    mean_intensity = np.mean(masked_pixels)
                    min_intensity = np.min(masked_pixels)
                    std_intensity = np.std(masked_pixels)
                    
                    # CORRECTED scoring for detecting actual shaded marks (not just darkness)
                    # Lower intensity = darker = likely shaded
                    mean_darkness = (255 - mean_intensity) / 255.0
                    min_darkness = (255 - min_intensity) / 255.0
                    
                    # Enhanced dark pixel detection for pencil/pen marks
                    dark_threshold = mean_intensity - (std_intensity * 0.8)  # More sensitive
                    dark_pixels = np.sum(masked_pixels < dark_threshold)
                    dark_percentage = dark_pixels / len(masked_pixels)
                    
                    # Very dark pixel detection for strong marks
                    very_dark_threshold = 80  # Lower = more sensitive to marks
                    very_dark_pixels = np.sum(masked_pixels < very_dark_threshold)
                    very_dark_percentage = very_dark_pixels / len(masked_pixels)
                    
                    # Edge detection for pencil stroke patterns
                    edges = cv2.Canny((masked_pixels.reshape(-1, 1)).astype(np.uint8), 30, 100)
                    edge_density = np.sum(edges > 0) / len(masked_pixels) if len(masked_pixels) > 0 else 0
                    
                    # Weighted scoring optimized for ACTUAL shading detection
                    combined_score = (
                        mean_darkness * 0.25 +           # Overall darkness
                        min_darkness * 0.3 +             # Darkest regions
                        dark_percentage * 0.25 +         # Dark pixel ratio
                        very_dark_percentage * 0.15 +    # Very dark pixels
                        edge_density * 0.05              # Stroke patterns
                    )
                    
                    choice_scores.append(combined_score)
                else:
                    choice_scores.append(0.0)
            
            # Enhanced selection logic for ACTUAL shading detection
            if choice_scores and len(choice_scores) >= 2:
                max_score = max(choice_scores)
                
                # Lower threshold since we're looking for actual marks
                if max_score > 0.08:  # Much lower threshold for actual shading
                    selected_choice = choice_scores.index(max_score)
                    
                    # Check confidence - marked bubble should be significantly darker
                    sorted_scores = sorted(choice_scores, reverse=True)
                    if len(sorted_scores) >= 2:
                        confidence = sorted_scores[0] - sorted_scores[1]
                        
                        # Very low confidence threshold for actual marks
                        if confidence >= 0.01 or max_score > 0.15:
                            student_answers.append(selected_choice)
                            
                            # Debug first few questions with CORRECTED mapping
                            if q_num < 5:
                                choice_letters = [map_choice_index_to_letter(i) for i in range(len(choice_scores))]
                                scores_str = ', '.join([f"{letter}:{score:.3f}" for letter, score in zip(choice_letters, choice_scores) if letter])
                                selected_letter = map_choice_index_to_letter(selected_choice)
                                
                                # Show bubble positions for mapping verification
                                bubble_positions = [f"x{bubble_row[i][0]}" for i in range(min(len(bubble_row), len(choice_scores)))]
                                positions_str = ', '.join([f"{choice_letters[i]}@{pos}" for i, pos in enumerate(bubble_positions) if i < len(choice_letters)])
                                
                                print(f"Contour Q{q_num+1}: {scores_str} -> {selected_letter} (conf: {confidence:.3f})")
                                print(f"  Bubble positions: {positions_str}")
                        else:
                            student_answers.append(-1)
                            if q_num < 5:
                                print(f"Contour Q{q_num+1}: Low confidence - max: {max_score:.3f}, conf: {confidence:.3f}")
                    else:
                        student_answers.append(selected_choice)
                else:
                    student_answers.append(-1)
                    if q_num < 5:
                        print(f"Contour Q{q_num+1}: No clear shading detected - max: {max_score:.3f}")
            else:
                student_answers.append(-1)
        
        # Pad with -1 if needed
        while len(student_answers) < self.questions:
            student_answers.append(-1)
        
        detected_count = sum(1 for ans in student_answers if ans >= 0)
        return f"Enhanced Contour Method (CORRECTED)", student_answers[:self.questions], detected_count
    
    def method_grid_based(self, gray_img):
        """Systematic grid-based approach - CORRECTED for proper OMR layout with header skip"""
        height, width = gray_img.shape
        
        # Apply threshold to detect DARK marks (not white areas)
        _, thresh = cv2.threshold(gray_img, 130, 255, cv2.THRESH_BINARY)  # Normal threshold for dark detection
        
        # CORRECTED Grid parameters for your OMR sheet layout:
        # 5 subjects (columns), each with 20 questions (rows)
        subjects = 5  # Python, EDA, SQL, Power BI, Statistics
        questions_per_subject = 20
        
        # CRITICAL FIX: Skip header area (titles/subject names)
        header_skip = int(height * 0.1)  # Skip top 10% which contains headers
        usable_height = height - header_skip
        
        subject_width = width // subjects  # Width of each subject column
        question_height = usable_height // questions_per_subject  # Height of each question row
        
        print(f"Grid analysis: {width}x{height}, header_skip={header_skip}, usable_height={usable_height}")
        print(f"Each subject: {subject_width} wide, each question: {question_height} tall")
        
        student_answers = []
        
        # Read COLUMN-BY-COLUMN (subject by subject), not row by row
        for subject in range(subjects):
            for question in range(questions_per_subject):
                # Calculate overall question number (0-99)
                question_num = subject * questions_per_subject + question
                if question_num >= self.questions:
                    break
                
                # Extract the specific question area within this subject
                subject_x1 = subject * subject_width
                subject_x2 = (subject + 1) * subject_width
                
                # IMPORTANT: Start from after the header area
                question_y1 = header_skip + (question * question_height)
                question_y2 = header_skip + ((question + 1) * question_height)
                
                # Get the region for this specific question
                question_roi = thresh[question_y1:question_y2, subject_x1:subject_x2]
                
                # Within this question, divide into 4 choice areas (A, B, C, D)
                choice_width = question_roi.shape[1] // 4
                choice_pixels = []
                
                for choice in range(4):
                    choice_x1 = choice * choice_width
                    choice_x2 = (choice + 1) * choice_width
                    choice_roi = question_roi[:, choice_x1:choice_x2]
                    pixels = cv2.countNonZero(choice_roi)
                    choice_pixels.append(pixels)
                
                # CORRECTED: Look for DARK shaded areas (actual pencil marks)
                # In thresholded image, BLACK pixels = actual shading/marks
                if choice_pixels:
                    # Calculate relative darkness - look for unusually LOW pixel counts (dark areas)
                    avg_pixels = sum(choice_pixels) / len(choice_pixels)
                    min_pixels = min(choice_pixels)
                    
                    # A bubble is "shaded" if it has significantly FEWER white pixels (more dark pixels)
                    shading_threshold = max(10, avg_pixels * 0.7)  # 30% fewer white pixels = more dark shading
                    
                    if min_pixels < shading_threshold:
                        selected_choice = choice_pixels.index(min_pixels)  # Choose DARKEST (lowest white pixels)
                        student_answers.append(selected_choice)
                        
                        # Debug first few questions to verify correct reading with CORRECTED mapping
                        if question_num < 5:
                            choices_str = f"A:{choice_pixels[0]}, B:{choice_pixels[1]}, C:{choice_pixels[2]}, D:{choice_pixels[3]}"
                            selected_letter = map_choice_index_to_letter(selected_choice)
                            # Show actual x-coordinates to verify left-to-right mapping
                            choice_x_coords = [subject_x1 + (i * choice_width) + choice_width//2 for i in range(4)]
                            coords_str = f"A@x{choice_x_coords[0]}, B@x{choice_x_coords[1]}, C@x{choice_x_coords[2]}, D@x{choice_x_coords[3]}"
                            print(f"Q{question_num+1} (Subject {subject+1}, Q{question+1}): {choices_str} -> {selected_letter} (darkest, threshold: {shading_threshold:.0f})")
                            print(f"  Choice positions: {coords_str}")
                    else:
                        student_answers.append(-1)
                        if question_num < 5:
                            choices_str = f"A:{choice_pixels[0]}, B:{choice_pixels[1]}, C:{choice_pixels[2]}, D:{choice_pixels[3]}"
                            print(f"Q{question_num+1} (Subject {subject+1}, Q{question+1}): {choices_str} -> None (min: {min_pixels}, threshold: {shading_threshold:.0f})")
                else:
                    student_answers.append(-1)
                    if question_num < 5:
                        print(f"Q{question_num+1} (Subject {subject+1}, Q{question+1}): No choice pixels detected")
        
        # Pad with -1 if needed
        while len(student_answers) < self.questions:
            student_answers.append(-1)
        
        detected_count = sum(1 for ans in student_answers if ans >= 0)
        return f"Grid-based Method (HEADER-CORRECTED)", student_answers[:self.questions], detected_count
    
    def method_adaptive_threshold(self, gray_img):
        """Adaptive threshold method with zone-based analysis"""
        height, width = gray_img.shape
        
        # Divide image into zones for adaptive processing
        zones_y = 4
        zones_x = 4
        
        zone_height = height // zones_y
        zone_width = width // zones_x
        
        # Process each zone with adaptive threshold
        full_thresh = np.zeros_like(gray_img)
        
        for zy in range(zones_y):
            for zx in range(zones_x):
                y1 = zy * zone_height
                y2 = (zy + 1) * zone_height
                x1 = zx * zone_width
                x2 = (zx + 1) * zone_width
                
                zone = gray_img[y1:y2, x1:x2]
                zone_thresh = cv2.adaptiveThreshold(zone, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                  cv2.THRESH_BINARY_INV, 11, 3)
                full_thresh[y1:y2, x1:x2] = zone_thresh
        
        # Apply morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        full_thresh = cv2.morphologyEx(full_thresh, cv2.MORPH_CLOSE, kernel)
        full_thresh = cv2.morphologyEx(full_thresh, cv2.MORPH_OPEN, kernel)
        
        # Column-based analysis (5 subjects × 20 questions each)
        student_answers = []
        
        # Parameters for 5 columns of 20 questions each
        cols = 5
        questions_per_col = 20
        
        col_width = width // cols
        question_height = height // questions_per_col
        
        for col in range(cols):
            col_x1 = col * col_width
            col_x2 = (col + 1) * col_width
            
            for row in range(questions_per_col):
                question_num = col * questions_per_col + row
                if question_num >= self.questions:
                    break
                
                # Extract question row
                q_y1 = row * question_height
                q_y2 = (row + 1) * question_height
                
                question_roi = full_thresh[q_y1:q_y2, col_x1:col_x2]
                
                # Divide into 4 choices
                choice_width = question_roi.shape[1] // 4
                choice_pixels = []
                
                for choice in range(4):
                    c_x1 = choice * choice_width
                    c_x2 = (choice + 1) * choice_width
                    choice_roi = question_roi[:, c_x1:c_x2]
                    pixels = cv2.countNonZero(choice_roi)
                    choice_pixels.append(pixels)
                
                # Enhanced selection with relative comparison
                if choice_pixels:
                    max_pixels = max(choice_pixels)
                    if max_pixels > 50:
                        # Check for clear winner
                        sorted_pixels = sorted(choice_pixels, reverse=True)
                        if len(sorted_pixels) >= 2 and sorted_pixels[0] > sorted_pixels[1] * 1.3:
                            selected_choice = choice_pixels.index(max_pixels)
                            student_answers.append(selected_choice)
                        else:
                            student_answers.append(-1)  # Tie or unclear
                    else:
                        student_answers.append(-1)
                else:
                    student_answers.append(-1)
        
        # Pad with -1 if needed
        while len(student_answers) < self.questions:
            student_answers.append(-1)
        
        detected_count = sum(1 for ans in student_answers if ans >= 0)
        return f"Adaptive Threshold Method", student_answers[:self.questions], detected_count
    
    def method_mark_detection(self, gray_img):
        """SPECIALIZED method for detecting pencil/pen marks within bubble areas"""
        height, width = gray_img.shape
        
        # INVERTED LOGIC: Look for dark marks (pencil shading), not white areas
        # Use normal threshold to detect dark pencil marks
        _, binary = cv2.threshold(gray_img, 120, 255, cv2.THRESH_BINARY)  # NORMAL, not INV
        
        # Additional threshold for darker pencil marks  
        dark_mark_thresh = cv2.threshold(gray_img, 90, 255, cv2.THRESH_BINARY)[1]  # Even darker marks
        
        # Combine to catch all levels of pencil darkness
        combined_thresh = cv2.bitwise_and(binary, dark_mark_thresh)  # AND, not OR
        
        # Remove very large connected components (form structure)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(combined_thresh, cv2.MORPH_OPEN, kernel)
        
        # Grid parameters for 5 subjects × 20 questions
        subjects = 5
        questions_per_subject = 20
        header_skip = int(height * 0.15)  # Skip more header area
        usable_height = height - header_skip
        
        subject_width = width // subjects
        question_height = usable_height // questions_per_subject
        
        print(f"Mark detection: {width}x{height}, header_skip={header_skip}")
        
        student_answers = []
        
        for subject in range(subjects):
            for question in range(questions_per_subject):
                question_num = subject * questions_per_subject + question
                if question_num >= self.questions:
                    break
                
                # Get question area
                subject_x1 = subject * subject_width
                subject_x2 = (subject + 1) * subject_width
                question_y1 = header_skip + (question * question_height)
                question_y2 = header_skip + ((question + 1) * question_height)
                
                question_roi = cleaned[question_y1:question_y2, subject_x1:subject_x2]
                gray_roi = gray_img[question_y1:question_y2, subject_x1:subject_x2]
                
                # Divide into 4 choice areas
                choice_width = question_roi.shape[1] // 4
                choice_scores = []
                
                for choice in range(4):
                    choice_x1 = choice * choice_width
                    choice_x2 = (choice + 1) * choice_width
                    
                    choice_binary = question_roi[:, choice_x1:choice_x2]
                    choice_gray = gray_roi[:, choice_x1:choice_x2]
                    
                    # Count DARK pixels (actual shading) - INVERTED LOGIC
                    dark_pixels = choice_gray.size - cv2.countNonZero(choice_binary) if choice_gray.size > 0 else 0
                    
                    # Additional analysis - look for shaded regions in original
                    if choice_gray.size > 0:
                        mean_intensity = np.mean(choice_gray)
                        min_intensity = np.min(choice_gray)
                        std_intensity = np.std(choice_gray)
                        
                        # Calculate SHADING score (look for dark marks)
                        # High dark_pixels = actual pencil marks
                        # Low mean_intensity = dark shaded area
                        # High std = variation indicating pencil strokes
                        
                        dark_density = dark_pixels / choice_gray.size if choice_gray.size > 0 else 0
                        darkness_score = (255 - mean_intensity) / 255.0
                        min_dark_score = (255 - min_intensity) / 255.0
                        variation_score = std_intensity / 50.0  # Pencil marks create variation
                        
                        # Combined score emphasizing ACTUAL PENCIL SHADING
                        combined_score = (dark_density * 0.4 + darkness_score * 0.25 + min_dark_score * 0.25 + min(variation_score, 1.0) * 0.1)
                        choice_scores.append(combined_score)
                    else:
                        choice_scores.append(0.0)
                
                # Select choice with highest mark score
                if choice_scores:
                    max_score = max(choice_scores)
                    # Much lower threshold since we're looking for actual marks
                    if max_score > 0.1:  # Low threshold for mark detection
                        selected_choice = choice_scores.index(max_score)
                        
                        # Verify it's significantly higher than others
                        other_scores = [s for i, s in enumerate(choice_scores) if i != selected_choice]
                        if other_scores:
                            second_best = max(other_scores)
                            confidence = max_score - second_best
                            
                            if confidence > 0.02 or max_score > 0.25:  # Either clear winner or strong mark
                                student_answers.append(selected_choice)
                                if question_num < 5:
                                    scores_str = f"A:{choice_scores[0]:.3f}, B:{choice_scores[1]:.3f}, C:{choice_scores[2]:.3f}, D:{choice_scores[3]:.3f}"
                                    selected_letter = map_choice_index_to_letter(selected_choice)
                                    print(f"Mark Q{question_num+1}: {scores_str} -> {selected_letter} (conf: {confidence:.3f})")
                            else:
                                student_answers.append(-1)
                                if question_num < 5:
                                    print(f"Mark Q{question_num+1}: Low confidence - max: {max_score:.3f}, conf: {confidence:.3f}")
                        else:
                            student_answers.append(selected_choice)
                    else:
                        student_answers.append(-1)
                        if question_num < 5:
                            scores_str = f"A:{choice_scores[0]:.3f}, B:{choice_scores[1]:.3f}, C:{choice_scores[2]:.3f}, D:{choice_scores[3]:.3f}"
                            print(f"Mark Q{question_num+1}: {scores_str} -> None (max: {max_score:.3f})")
                else:
                    student_answers.append(-1)
        
        # Pad with -1 if needed
        while len(student_answers) < self.questions:
            student_answers.append(-1)
        
        detected_count = sum(1 for ans in student_answers if ans >= 0)
        return f"Mark Detection Method", student_answers[:self.questions], detected_count
    
    def method_mark_detection_improved(self, gray_img):
        """IMPROVED method for detecting pencil/pen marks within bubble areas - FIXED BIAS"""
        height, width = gray_img.shape
        
        # Use adaptive threshold to reduce form structure interference
        adaptive_thresh = cv2.adaptiveThreshold(
            gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Create a mask to filter out form structure
        # Use edge detection to identify and remove printed form lines
        edges = cv2.Canny(gray_img, 50, 150)
        
        # Dilate edges to create exclusion mask for form structure
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
        edge_mask = cv2.dilate(edges, kernel, iterations=1)
        
        # Invert edge mask so we analyze areas WITHOUT form structure
        analysis_mask = cv2.bitwise_not(edge_mask)
        
        # Grid parameters
        subjects = 5
        questions_per_subject = 20
        header_skip = int(height * 0.15)
        usable_height = height - header_skip
        
        subject_width = width // subjects
        question_height = usable_height // questions_per_subject
        
        print(f"Improved mark detection: {width}x{height}, header_skip={header_skip}")
        
        student_answers = []
        
        for subject in range(subjects):
            for question in range(questions_per_subject):
                question_num = subject * questions_per_subject + question
                if question_num >= self.questions:
                    break
                
                # Get question area
                subject_x1 = subject * subject_width
                subject_x2 = (subject + 1) * subject_width
                question_y1 = header_skip + (question * question_height)
                question_y2 = header_skip + ((question + 1) * question_height)
                
                question_roi = gray_img[question_y1:question_y2, subject_x1:subject_x2]
                mask_roi = analysis_mask[question_y1:question_y2, subject_x1:subject_x2]
                
                # Divide into 4 choice areas with proper spacing
                choice_width = question_roi.shape[1] // 4
                choice_scores = []
                
                for choice in range(4):
                    choice_x1 = choice * choice_width
                    choice_x2 = (choice + 1) * choice_width
                    
                    choice_gray = question_roi[:, choice_x1:choice_x2]
                    choice_mask = mask_roi[:, choice_x1:choice_x2]
                    
                    if choice_gray.size > 0:
                        # Apply mask to ignore form structure
                        masked_pixels = choice_gray[choice_mask > 0]
                        
                        if len(masked_pixels) > 10:  # Need enough pixels to analyze
                            # Calculate baseline (expected background brightness)
                            background_percentile = np.percentile(masked_pixels, 85)  # Bright background reference
                            
                            # Look for pixels significantly darker than background
                            dark_threshold = background_percentile - 30  # Adaptive threshold
                            dark_pixels = np.sum(masked_pixels < dark_threshold)
                            dark_ratio = dark_pixels / len(masked_pixels)
                            
                            # Look for very dark pixels (actual pencil marks)
                            very_dark_threshold = background_percentile - 60
                            very_dark_pixels = np.sum(masked_pixels < very_dark_threshold)
                            very_dark_ratio = very_dark_pixels / len(masked_pixels)
                            
                            # Calculate intensity variation (pencil creates texture)
                            intensity_std = np.std(masked_pixels)
                            normalized_std = min(intensity_std / 20.0, 1.0)
                            
                            # Score based on ACTUAL shading indicators
                            shading_score = (
                                dark_ratio * 0.4 +           # General darkness
                                very_dark_ratio * 0.5 +     # Strong dark marks
                                normalized_std * 0.1        # Texture variation
                            )
                            
                            choice_scores.append(shading_score)
                        else:
                            choice_scores.append(0.0)
                    else:
                        choice_scores.append(0.0)
                
                # Select choice with CLEAR shading evidence
                if choice_scores and len(choice_scores) == 4:
                    max_score = max(choice_scores)
                    
                    # Higher threshold to avoid false positives
                    if max_score > 0.15:  # Require clear evidence of shading
                        selected_choice = choice_scores.index(max_score)
                        
                        # Ensure it's significantly better than others
                        other_scores = [s for i, s in enumerate(choice_scores) if i != selected_choice]
                        if other_scores:
                            second_best = max(other_scores)
                            confidence = max_score - second_best
                            
                            # Require clear confidence difference
                            if confidence > 0.05 or max_score > 0.3:
                                student_answers.append(selected_choice)
                                if question_num < 5:
                                    scores_str = f"A:{choice_scores[0]:.3f}, B:{choice_scores[1]:.3f}, C:{choice_scores[2]:.3f}, D:{choice_scores[3]:.3f}"
                                    selected_letter = map_choice_index_to_letter(selected_choice)
                                    print(f"Improved Q{question_num+1}: {scores_str} -> {selected_letter} (conf: {confidence:.3f})")
                            else:
                                student_answers.append(-1)
                                if question_num < 5:
                                    print(f"Improved Q{question_num+1}: Low confidence - max: {max_score:.3f}, conf: {confidence:.3f}")
                        else:
                            student_answers.append(selected_choice)
                    else:
                        student_answers.append(-1)
                        if question_num < 5:
                            print(f"Improved Q{question_num+1}: No clear shading - max: {max_score:.3f}")
                else:
                    student_answers.append(-1)
        
        # Pad with -1 if needed
        while len(student_answers) < self.questions:
            student_answers.append(-1)
        
        detected_count = sum(1 for ans in student_answers if ans >= 0)
        return f"Improved Mark Detection Method", student_answers[:self.questions], detected_count
    
    def method_mark_detection_normalized(self, gray_img):
        """BACKGROUND-NORMALIZED method for detecting actual pencil marks - FIXES STRUCTURAL BIAS"""
        height, width = gray_img.shape
        
        # Grid parameters
        subjects = 5
        questions_per_subject = 20
        header_skip = int(height * 0.15)
        usable_height = height - header_skip
        
        subject_width = width // subjects
        question_height = usable_height // questions_per_subject
        
        print(f"Background-normalized detection: {width}x{height}, header_skip={header_skip}")
        
        # FIRST PASS: Calculate background intensity for each choice position
        # This will help us normalize for structural differences
        choice_background_stats = [[] for _ in range(4)]  # A, B, C, D
        
        # Sample multiple questions to get background statistics
        sample_questions = min(50, subjects * questions_per_subject)
        
        for sample in range(sample_questions):
            subject = sample // questions_per_subject
            question = sample % questions_per_subject
            
            if subject >= subjects:
                break
                
            # Get question area
            subject_x1 = subject * subject_width
            subject_x2 = (subject + 1) * subject_width
            question_y1 = header_skip + (question * question_height)
            question_y2 = header_skip + ((question + 1) * question_height)
            
            question_roi = gray_img[question_y1:question_y2, subject_x1:subject_x2]
            choice_width = question_roi.shape[1] // 4
            
            for choice in range(4):
                choice_x1 = choice * choice_width
                choice_x2 = (choice + 1) * choice_width
                choice_area = question_roi[:, choice_x1:choice_x2]
                
                if choice_area.size > 0:
                    # Use median intensity as background reference (more robust than mean)
                    background_intensity = np.median(choice_area)
                    choice_background_stats[choice].append(background_intensity)
        
        # Calculate background baselines for each choice position
        choice_baselines = []
        for choice in range(4):
            if choice_background_stats[choice]:
                baseline = np.median(choice_background_stats[choice])
                choice_baselines.append(baseline)
            else:
                choice_baselines.append(200)  # Default bright background
        
        print(f"Background baselines - A:{choice_baselines[0]:.1f}, B:{choice_baselines[1]:.1f}, C:{choice_baselines[2]:.1f}, D:{choice_baselines[3]:.1f}")
        
        # SECOND PASS: Detect marks using normalized scoring
        student_answers = []
        
        for subject in range(subjects):
            for question in range(questions_per_subject):
                question_num = subject * questions_per_subject + question
                if question_num >= self.questions:
                    break
                
                # Get question area
                subject_x1 = subject * subject_width
                subject_x2 = (subject + 1) * subject_width
                question_y1 = header_skip + (question * question_height)
                question_y2 = header_skip + ((question + 1) * question_height)
                
                question_roi = gray_img[question_y1:question_y2, subject_x1:subject_x2]
                choice_width = question_roi.shape[1] // 4
                choice_scores = []
                
                for choice in range(4):
                    choice_x1 = choice * choice_width
                    choice_x2 = (choice + 1) * choice_width
                    choice_area = question_roi[:, choice_x1:choice_x2]
                    
                    if choice_area.size > 0:
                        # Get the expected background for this choice position
                        expected_background = choice_baselines[choice]
                        
                        # Calculate actual intensity statistics
                        actual_median = np.median(choice_area)
                        actual_min = np.min(choice_area)
                        actual_percentile_10 = np.percentile(choice_area, 10)  # Darkest 10%
                        
                        # NORMALIZE using background baseline
                        # Positive values = darker than expected background
                        median_deviation = expected_background - actual_median
                        min_deviation = expected_background - actual_min
                        dark_deviation = expected_background - actual_percentile_10
                        
                        # Look for significant darkening (pencil marks)
                        mark_threshold = 20  # Marks should be at least 20 intensity units darker
                        
                        # Count pixels significantly darker than expected background
                        dark_mark_pixels = np.sum(choice_area < (expected_background - mark_threshold))
                        dark_mark_ratio = dark_mark_pixels / choice_area.size
                        
                        # Score based on RELATIVE darkening from expected background
                        normalized_score = (
                            max(0, median_deviation / 50.0) * 0.3 +     # General darkening
                            max(0, min_deviation / 100.0) * 0.3 +       # Darkest spots
                            max(0, dark_deviation / 60.0) * 0.2 +       # Dark percentile
                            dark_mark_ratio * 0.2                       # Dark pixel ratio
                        )
                        
                        choice_scores.append(normalized_score)
                    else:
                        choice_scores.append(0.0)
                
                # Select choice with highest NORMALIZED score
                if choice_scores and len(choice_scores) == 4:
                    max_score = max(choice_scores)
                    
                    # Threshold for detecting actual marks (after normalization)
                    if max_score > 0.15:  # Require clear evidence of marking
                        selected_choice = choice_scores.index(max_score)
                        
                        # Ensure confidence
                        other_scores = [s for i, s in enumerate(choice_scores) if i != selected_choice]
                        if other_scores:
                            second_best = max(other_scores)
                            confidence = max_score - second_best
                            
                            if confidence > 0.05 or max_score > 0.25:
                                student_answers.append(selected_choice)
                                if question_num < 5:
                                    scores_str = f"A:{choice_scores[0]:.3f}, B:{choice_scores[1]:.3f}, C:{choice_scores[2]:.3f}, D:{choice_scores[3]:.3f}"
                                    selected_letter = map_choice_index_to_letter(selected_choice)
                                    print(f"Normalized Q{question_num+1}: {scores_str} -> {selected_letter} (conf: {confidence:.3f})")
                            else:
                                student_answers.append(-1)
                                if question_num < 5:
                                    print(f"Normalized Q{question_num+1}: Low confidence - max: {max_score:.3f}, conf: {confidence:.3f}")
                        else:
                            student_answers.append(selected_choice)
                    else:
                        student_answers.append(-1)
                        if question_num < 5:
                            print(f"Normalized Q{question_num+1}: No clear marking - max: {max_score:.3f}")
                else:
                    student_answers.append(-1)
        
        # Pad with -1 if needed
        while len(student_answers) < self.questions:
            student_answers.append(-1)
        
        detected_count = sum(1 for ans in student_answers if ans >= 0)
        return f"Background-Normalized Mark Detection", student_answers[:self.questions], detected_count
    
    def group_bubbles_into_subjects(self, bubble_row):
        """Group bubbles in a horizontal row into 5 subjects, each with up to 4 choices"""
        if len(bubble_row) < 4:
            return []
        
        # Ensure bubbles are sorted left-to-right first
        sorted_row = sort_bubbles_for_choices(bubble_row, validate_order=False)
        
        # Calculate gaps between consecutive bubbles to identify subject boundaries
        x_positions = [bubble[0] for bubble in sorted_row]
        gaps = []
        for i in range(len(x_positions) - 1):
            gap = x_positions[i+1] - x_positions[i]
            gaps.append(gap)
        
        if not gaps:
            return [sorted_row[:4]] if len(sorted_row) >= 4 else []
        
        # Find large gaps that separate subjects
        avg_gap = sum(gaps) / len(gaps)
        large_gap_threshold = avg_gap * 1.5  # Gaps 50% larger than average
        
        # Split into subject groups
        subject_groups = []
        group_start = 0
        
        for i, gap in enumerate(gaps):
            if gap > large_gap_threshold:
                # End current group
                group_end = i + 1
                if group_end - group_start >= 2:  # At least 2 bubbles
                    group = sorted_row[group_start:group_end]
                    if len(group) <= 4:  # Max 4 choices per question
                        # Ensure this group is also properly sorted
                        group_sorted = sort_bubbles_for_choices(group, validate_order=True)
                        subject_groups.append(group_sorted)
                group_start = group_end
        
        # Add the last group
        if group_start < len(sorted_row):
            group = sorted_row[group_start:]
            if len(group) >= 2 and len(group) <= 4:
                group_sorted = sort_bubbles_for_choices(group, validate_order=True)
                subject_groups.append(group_sorted)
        
        return subject_groups
    
    def select_best_method(self, methods):
        """Select the best method based on detection rate and consistency - PRIORITIZING IMPROVED METHODS"""
        print("Evaluating Ultimate OMR methods:")
        
        best_answers = []
        best_score = 0
        
        for method_name, answers, detected_count in methods:
            detection_rate = detected_count / len(answers) if answers else 0
            
            # Calculate answer distribution (good methods should have varied answers)
            answer_counts = {}
            for ans in answers:
                if ans >= 0:
                    answer_counts[ans] = answer_counts.get(ans, 0) + 1
            
            # Penalty for methods that always pick the same choice
            max_choice_ratio = max(answer_counts.values()) / max(detected_count, 1) if answer_counts else 1
            diversity_score = 1.0 - max_choice_ratio if max_choice_ratio > 0.8 else 1.0
            
            # SPECIAL PRIORITY: Force use of background-normalized method if available
            if "Background-Normalized" in method_name and detected_count > 10:
                # Give the normalized method highest priority if it detects reasonable number
                combined_score = 0.99  # Highest priority score
                print(f"{method_name}: detected {detected_count}/100, diversity: {diversity_score:.2f}, score: {combined_score:.2f} (HIGHEST PRIORITY)")
            elif "Improved Mark Detection" in method_name and detected_count > 20:
                # Give the improved method a significant boost if it detects reasonable number
                combined_score = 0.95  # High priority score
                print(f"{method_name}: detected {detected_count}/100, diversity: {diversity_score:.2f}, score: {combined_score:.2f} (PRIORITIZED)")
            else:
                # Combined score for other methods
                combined_score = detection_rate * 0.7 + diversity_score * 0.3
                print(f"{method_name}: detected {detected_count}/100, diversity: {diversity_score:.2f}, score: {combined_score:.2f}")
            
            if combined_score > best_score:
                best_score = combined_score
                best_answers = answers
        
        return best_answers
    
    def save_ultimate_debug(self, original_img, student_answers, correct_answers):
        """Save comprehensive debug output with CORRECTED choice mapping visualization"""
        debug_img = original_img.copy()
        
        # Create summary
        cv2.putText(debug_img, f"Ultimate OMR Processor Results", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        detected_count = sum(1 for ans in student_answers if ans >= 0)
        cv2.putText(debug_img, f"Detected: {detected_count}/100 answers", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Add choice mapping legend
        cv2.putText(debug_img, f"Choice Mapping: A=Red, B=Green, C=Blue, D=Yellow", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.imwrite("debug_ultimate_omr.jpg", debug_img)
        print(f"Ultimate debug saved: debug_ultimate_omr.jpg")
        
        # Create detailed mapping analysis
        self.save_detailed_choice_mapping(original_img, student_answers, correct_answers)
    
    def save_detailed_choice_mapping(self, original_img, student_answers, correct_answers):
        """Create detailed visualization showing choice mapping for first 20 questions"""
        # Create a new image for mapping analysis
        mapping_img = original_img.copy()
        height, width = mapping_img.shape[:2]
        
        # Colors for each choice: A=Red, B=Green, C=Blue, D=Yellow
        choice_colors = {
            0: (0, 0, 255),    # A = Red
            1: (0, 255, 0),    # B = Green  
            2: (255, 0, 0),    # C = Blue
            3: (0, 255, 255)   # D = Yellow
        }
        
        # Draw grid overlay to show expected positions
        # Assume 5 subjects across width, 20 questions per subject down height
        header_skip = int(height * 0.1)
        usable_height = height - header_skip
        subject_width = width // 5
        question_height = usable_height // 20
        
        # Draw subject column lines
        for i in range(1, 5):
            x = i * subject_width
            cv2.line(mapping_img, (x, header_skip), (x, height), (128, 128, 128), 1)
        
        # Draw question row lines (every 5th question for clarity)
        for i in range(0, 20, 5):
            y = header_skip + (i * question_height)
            cv2.line(mapping_img, (0, y), (width, y), (128, 128, 128), 1)
        
        # Mark detected answers with proper choice colors
        for q_num in range(min(20, len(student_answers))):  # Show first 20 questions
            answer = student_answers[q_num]
            if answer >= 0:
                # Calculate position in grid
                subject = q_num // 20
                question_in_subject = q_num % 20
                
                # Calculate bubble position
                subject_x = subject * subject_width
                question_y = header_skip + (question_in_subject * question_height)
                
                choice_width = subject_width // 4
                bubble_x = subject_x + (answer * choice_width) + choice_width // 2
                bubble_y = question_y + question_height // 2
                
                # Draw detected choice with appropriate color
                color = choice_colors.get(answer, (255, 255, 255))
                cv2.circle(mapping_img, (bubble_x, bubble_y), 8, color, -1)
                cv2.circle(mapping_img, (bubble_x, bubble_y), 10, (255, 255, 255), 2)
                
                # Add text label
                choice_letter = map_choice_index_to_letter(answer)
                cv2.putText(mapping_img, f"Q{q_num+1}:{choice_letter}", 
                           (bubble_x - 15, bubble_y - 15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
        
        # Add legend
        legend_y = 30
        cv2.putText(mapping_img, "Choice Mapping Legend:", (width - 200, legend_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        for i, (choice_letter, color) in enumerate([('A', (0, 0, 255)), ('B', (0, 255, 0)), 
                                                   ('C', (255, 0, 0)), ('D', (0, 255, 255))]):
            legend_y += 20
            cv2.circle(mapping_img, (width - 180, legend_y), 6, color, -1)
            cv2.putText(mapping_img, f"{choice_letter} = {['Red', 'Green', 'Blue', 'Yellow'][i]}", 
                       (width - 165, legend_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        cv2.imwrite("debug_choice_mapping.jpg", mapping_img)
        print(f"Choice mapping debug saved: debug_choice_mapping.jpg")
        
        # Print mapping verification
        print("\\n=== CHOICE MAPPING VERIFICATION ===")
        print("First 10 detected answers with positions:")
        for q_num in range(min(10, len(student_answers))):
            answer = student_answers[q_num]
            if answer >= 0:
                choice_letter = map_choice_index_to_letter(answer)
                correct = correct_answers[q_num] if q_num < len(correct_answers) else -1
                correct_letter = map_choice_index_to_letter(correct) if correct >= 0 else "?"
                status = "✅" if answer == correct else "❌"
                print(f"Q{q_num+1:2d}: Detected={choice_letter} (index {answer}) | Correct={correct_letter} | {status}")
            else:
                print(f"Q{q_num+1:2d}: No answer detected")
        print("=" * 40)
    
    def filter_bubble_contours(self, contours):
        """Filter contours to find potential bubbles with trained parameters"""
        bubble_contours = []
        
        for contour in contours:
            if self.is_valid_bubble(contour):
                bubble_contours.append(contour)
        
        print(f"Found {len(bubble_contours)} potential bubbles")
        return bubble_contours
    
    def is_valid_bubble(self, contour):
        """Enhanced bubble validation with trained parameters"""
        # Calculate basic properties
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        
        # Filter by area
        if not (self.training_params['area_min'] < area < self.training_params['area_max']):
            return False
        
        if perimeter <= 0:
            return False
            
        # Calculate circularity
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < self.training_params['circularity_min']:
            return False
        
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        
        # Aspect ratio check
        aspect_ratio = float(w) / h
        if not (self.training_params['aspect_ratio_min'] < aspect_ratio < self.training_params['aspect_ratio_max']):
            return False
        
        # Size consistency check
        if (w < self.training_params['size_min'] or h < self.training_params['size_min'] or 
            w > self.training_params['size_max'] or h > self.training_params['size_max']):
            return False
        
        # Extent check
        rect_area = w * h
        extent = float(area) / rect_area
        if extent < self.training_params['extent_min']:
            return False
        
        # Solidity check
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        if hull_area > 0:
            solidity = float(area) / hull_area
            if solidity < self.training_params['solidity_min']:
                return False
        
        return True
    
    def group_bubbles_by_questions(self, bubble_contours, img_shape):
        """Group bubbles into questions based on their positions with improved multi-column support"""
        if not bubble_contours:
            return []
        
        # Get center points of all bubbles
        bubble_centers = []
        for contour in bubble_contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                bubble_centers.append((cx, cy, contour))
        
        if not bubble_centers:
            return []
        
        # Sort bubbles by Y coordinate (top to bottom) first
        bubble_centers.sort(key=lambda x: x[1])
        
        # Group bubbles into rows with adaptive tolerance
        questions_bubbles = []
        current_row = []
        current_y = bubble_centers[0][1]
        row_tolerance = max(8, img_shape[0] // 80)  # Smaller tolerance for better row separation
        
        for cx, cy, contour in bubble_centers:
            if abs(cy - current_y) <= row_tolerance:
                current_row.append((cx, cy, contour))
            else:
                if len(current_row) >= 2:
                    # Sort by X coordinate to get left-to-right order
                    current_row.sort(key=lambda x: x[0])
                    processed_row = self.process_bubble_row(current_row, img_shape)
                    if processed_row:
                        questions_bubbles.extend(processed_row)
                current_row = [(cx, cy, contour)]
                current_y = cy
        
        # Add the last row if valid
        if len(current_row) >= 2:
            current_row.sort(key=lambda x: x[0])
            processed_row = self.process_bubble_row(current_row, img_shape)
            if processed_row:
                questions_bubbles.extend(processed_row)
        
        print(f"Grouped bubbles into {len(questions_bubbles)} valid question rows")
        return questions_bubbles
    
    def process_bubble_row(self, row, img_shape):
        """Process a row of bubbles to handle multi-column layout"""
        if len(row) < 2:
            return []
        
        # For your specific OMR sheet layout, we need to identify the subject columns
        # Based on your image, there are 5 subjects: PYTHON, DATA ANALYSIS, MySQL, POWER BI, ADV STATS
        # Each subject should have its own set of 4 choices (A, B, C, D)
        
        x_positions = [bubble[0] for bubble in row]
        
        # If we have exactly 4 bubbles, treat as a single question
        if len(row) == 4:
            return [row]
        
        # If we have more than 4 bubbles, we need to group them by subject columns
        if len(row) > 4:
            # Calculate gaps between consecutive bubbles
            gaps = []
            for i in range(len(x_positions) - 1):
                gap = x_positions[i+1] - x_positions[i]
                gaps.append(gap)
            
            if gaps:
                # Identify significant gaps that separate subject columns
                avg_gap = sum(gaps) / len(gaps)
                large_gap_indices = []
                
                # A gap is considered "large" if it's significantly bigger than average
                for i, gap in enumerate(gaps):
                    if gap > avg_gap * 1.8:  # 80% larger than average
                        large_gap_indices.append(i)
                
                # Split into subject groups based on large gaps
                groups = []
                start_idx = 0
                
                for gap_idx in large_gap_indices:
                    end_idx = gap_idx + 1
                    if end_idx - start_idx >= 2:  # At least 2 bubbles
                        group = row[start_idx:end_idx]
                        if len(group) <= 4:  # Maximum 4 choices per question
                            groups.append(group)
                    start_idx = end_idx
                
                # Add the last group
                if start_idx < len(row):
                    group = row[start_idx:]
                    if len(group) >= 2 and len(group) <= 4:
                        groups.append(group)
                
                return groups
        
        # Simplified: just return first 4 bubbles to get more question rows
        return [row[:4]]
    
    def is_valid_bubble_row(self, bubble_row):
        """Check if a row of bubbles is valid"""
        return len(bubble_row) >= 2
    
    def extract_answers_from_bubbles(self, gray_img, questions_bubbles):
        """Extract answers by analyzing filled bubbles using enhanced accuracy methods"""
        student_answers = []
        
        for q_num, bubble_row in enumerate(questions_bubbles):
            if q_num >= self.questions:
                break
                
            if len(bubble_row) < 2:
                student_answers.append(-1)
                continue
            
            # Analyze each bubble in the row with multiple methods
            choice_scores = []
            choice_details = []
            
            for choice_idx, (cx, cy, contour) in enumerate(bubble_row[:self.choices]):
                # Enhanced fill detection for better shaded bubble recognition
                mask = np.zeros(gray_img.shape, dtype=np.uint8)
                cv2.fillPoly(mask, [contour], 255)
                
                masked_pixels = gray_img[mask > 0]
                if len(masked_pixels) > 0:
                    mean_intensity = np.mean(masked_pixels)
                    std_intensity = np.std(masked_pixels)
                    min_intensity = np.min(masked_pixels)
                    
                    # Method 1: Enhanced intensity analysis with better thresholds
                    # For pencil marks, we expect significantly darker regions
                    fill_score_v1 = (255 - mean_intensity) / 255.0
                    
                    # Method 2: Minimum intensity check (darkest pixels in bubble)
                    # Filled bubbles should have very dark pixels
                    fill_score_v2 = (255 - min_intensity) / 255.0
                    
                    # Method 3: Dark pixel percentage
                    # Count pixels that are significantly darker than the mean
                    dark_threshold = max(100, mean_intensity - std_intensity)  # Adaptive threshold
                    dark_pixels = np.sum(masked_pixels < dark_threshold)
                    dark_percentage = dark_pixels / len(masked_pixels)
                    
                    # Method 4: Very dark pixel detection
                    # Look for pixels that are much darker (likely pencil marks)
                    very_dark_threshold = 120  # Threshold for pencil marks
                    very_dark_pixels = np.sum(masked_pixels < very_dark_threshold)
                    very_dark_percentage = very_dark_pixels / len(masked_pixels)
                    
                    # Method 5: Intensity variance analysis
                    # Filled bubbles should have higher variance (mix of dark marks and background)
                    variance_score = std_intensity / 50.0  # Normalize by expected max std
                    
                    # Combined scoring with weights optimized for pencil/pen marks
                    combined_score = (
                        fill_score_v1 * 0.2 +           # Basic intensity
                        fill_score_v2 * 0.3 +           # Darkest regions  
                        dark_percentage * 0.2 +         # Dark pixel ratio
                        very_dark_percentage * 0.2 +    # Very dark pixels (pencil marks)
                        min(variance_score, 1.0) * 0.1  # Intensity variation
                    )
                    
                    # Store detailed analysis for debugging
                    analysis_details = {
                        'mean_intensity': mean_intensity,
                        'min_intensity': min_intensity,
                        'std_intensity': std_intensity,
                        'dark_percentage': dark_percentage,
                        'very_dark_percentage': very_dark_percentage,
                        'combined_score': combined_score
                    }
                else:
                    combined_score = 0.0
                    analysis_details = {
                        'mean_intensity': 255,
                        'min_intensity': 255,
                        'std_intensity': 0,
                        'dark_percentage': 0,
                        'very_dark_percentage': 0,
                        'combined_score': 0.0
                    }
                
                choice_scores.append(combined_score)
                choice_details.append(analysis_details)
            
            # Enhanced selection logic with better accuracy
            if choice_scores:
                max_score = max(choice_scores)
                min_score = min(choice_scores)
                score_variance = max_score - min_score
                
                # Enhanced debug output for first few questions to verify fill detection
                if q_num < 3:
                    choice_debug = []
                    for i, score in enumerate(choice_scores):
                        if i < len(bubble_row) and i < len(choice_details):
                            cx = bubble_row[i][0]  # X coordinate
                            details = choice_details[i]
                            choice_debug.append(
                                f"{chr(ord('A')+i)}(score:{score:.3f}, "
                                f"mean:{details['mean_intensity']:.0f}, "
                                f"min:{details['min_intensity']:.0f}, "
                                f"dark%:{details['dark_percentage']:.2f}, "
                                f"vdark%:{details['very_dark_percentage']:.2f}@x{cx})"
                            )
                    print(f"Q{q_num+1}: {choice_debug}")
                    print(f"      Variance = {score_variance:.3f}")
                
                # Enhanced selection criteria with optimized thresholds for new scoring
                min_threshold = 0.15  # Lowered threshold for new scoring system
                variance_threshold = 0.05  # Minimum variance needed for confident selection
                
                # Calculate adaptive confidence threshold based on score distribution
                score_mean = np.mean(choice_scores)
                score_std = np.std(choice_scores)
                
                # More sophisticated selection with multiple criteria
                if max_score > min_threshold:
                    selected_choice = choice_scores.index(max_score)
                    
                    # Additional validation: ensure the selected choice is significantly better
                    other_scores = [s for i, s in enumerate(choice_scores) if i != selected_choice]
                    if other_scores:
                        second_best = max(other_scores)
                        confidence = max_score - second_best
                        
                        # More aggressive detection for the new scoring system
                        if (confidence >= 0.02 and max_score > 0.2) or max_score > 0.35:
                            student_answers.append(selected_choice)
                            if q_num < 3:
                                selected_letter = map_choice_index_to_letter(selected_choice)
                                print(f"  -> SELECTED: {selected_letter} "
                                      f"(score: {max_score:.3f}, conf: {confidence:.3f})")
                        else:
                            student_answers.append(-1)
                            if q_num < 3:
                                print(f"  -> Low confidence: max={max_score:.3f}, conf={confidence:.3f}")
                    else:
                        student_answers.append(selected_choice)
                        if q_num < 3:
                            selected_letter = map_choice_index_to_letter(selected_choice)
                            print(f"  -> Selected: {selected_letter} (only valid choice)")
                else:
                    student_answers.append(-1)
                    if q_num < 3:
                        print(f"  -> No selection (max: {max_score:.3f}, variance: {score_variance:.3f})")
            else:
                student_answers.append(-1)
        
        # Pad with -1 if we don't have enough answers
        while len(student_answers) < self.questions:
            student_answers.append(-1)
        
        return student_answers[:self.questions]
    
    def train_on_sample(self, image_path, correct_set_type):
        """Train the model on a sample with known correct answers"""
        correct_answers = self.data_handler.answer_keys.get(correct_set_type, [])
        if not correct_answers:
            print(f"No correct answers found for {correct_set_type}")
            return False
        
        print(f"Training on {image_path} with {correct_set_type}...")
        
        # Test different parameter combinations
        best_score = 0
        best_params = self.training_params.copy()
        
        # Enhanced parameter ranges for better accuracy training
        param_ranges = {
            'fill_variance_threshold': [0.003, 0.005, 0.008, 0.01, 0.015],  # More sensitive options
            'min_fill_score': [0.04, 0.06, 0.08, 0.1, 0.12],  # Lower thresholds
            'area_min': [40, 50, 60],
            'area_max': [400, 500, 600],
            'circularity_min': [0.3, 0.4, 0.5],
            'adaptive_block_size': [15, 21, 27],  # Different block sizes
            'adaptive_c': [3, 5, 7]  # Different C values
        }
        
        for param_name, values in param_ranges.items():
            for value in values:
                # Test this parameter value
                test_params = self.training_params.copy()
                test_params[param_name] = value
                self.training_params = test_params
                
                # Process the image
                result = self.process_omr_sheet(image_path)
                
                if result.get("success"):
                    score = result.get("score", 0)
                    detected_count = len([a for a in result.get("student_answers", []) if a >= 0])
                    
                    # Score based on accuracy and detection rate
                    combined_score = score + (detected_count / 100) * 10  # Bonus for detection
                    
                    if combined_score > best_score:
                        best_score = combined_score
                        best_params = test_params.copy()
                        print(f"New best: {param_name}={value}, score={score:.1f}%, detected={detected_count}")
        
        # Use the best parameters
        self.training_params = best_params
        self.save_training_params()
        
        print(f"Training complete. Best score: {best_score:.1f}")
        return True
    
    def determine_set_type(self, student_answers):
        """Determine if this is Set A or Set B based on answers"""
        scores = {}
        for set_name, correct_answers in self.data_handler.answer_keys.items():
            score, _ = self.calculate_score(student_answers, correct_answers)
            scores[set_name] = score
        
        return max(scores, key=scores.get) if scores else "Set_A"
    
    def calculate_score(self, student_answers, correct_answers):
        """Calculate the score"""
        if not correct_answers:
            return 0.0, 0
        
        correct_count = sum(1 for s, c in zip(student_answers, correct_answers) 
                          if s == c and s >= 0)
        total = len(correct_answers)
        score = (correct_count / total) * 100 if total > 0 else 0
        
        return score, correct_count
    
    def save_debug_images(self, original_img, thresh_img, bubble_contours, questions_bubbles):
        """Save debug images to organized folders for better file structure"""
        # Create debug folder structure
        debug_base_dir = "debug_output"
        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(debug_base_dir, f"session_{timestamp}")
        
        # Create directories if they don't exist
        os.makedirs(debug_dir, exist_ok=True)
        os.makedirs(os.path.join(debug_dir, "processing"), exist_ok=True)
        os.makedirs(os.path.join(debug_dir, "detection"), exist_ok=True)
        os.makedirs(os.path.join(debug_dir, "analysis"), exist_ok=True)
        
        # Save threshold image
        cv2.imwrite(os.path.join(debug_dir, "processing", "01_threshold.jpg"), thresh_img)
        
        # Save original image for reference
        cv2.imwrite(os.path.join(debug_dir, "processing", "00_original.jpg"), original_img)
        
        # Draw all detected bubbles with detailed information
        bubble_img = original_img.copy()
        for i, contour in enumerate(bubble_contours):
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            
            # Color coding based on size and validity
            if area < 100:
                color = (0, 0, 255)  # Red for small
            elif area > 300:
                color = (255, 0, 255)  # Magenta for large
            else:
                color = (0, 255, 0)  # Green for normal
            
            cv2.drawContours(bubble_img, [contour], -1, color, 2)
            cv2.putText(bubble_img, f"{int(area)}", (x, y-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
            
            # Add contour number for detailed analysis
            cv2.putText(bubble_img, f"#{i}", (x, y+h+10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.25, color, 1)
        
        cv2.imwrite(os.path.join(debug_dir, "detection", "02_detected_bubbles.jpg"), bubble_img)
        
        # Draw grouped questions with improved labeling and choice verification
        questions_img = original_img.copy()
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # Red, Green, Blue, Yellow for A, B, C, D
        
        for q_num, bubble_row in enumerate(questions_bubbles[:25]):  # Show first 25 questions
            for choice_idx, (cx, cy, contour) in enumerate(bubble_row[:4]):
                color = colors[choice_idx % len(colors)]
                cv2.drawContours(questions_img, [contour], -1, color, 2)
                
                # Fixed question numbering to start from 1 with clear choice labels
                choice_label = chr(ord('A') + choice_idx)
                label = f"Q{q_num+1}-{choice_label}"
                cv2.putText(questions_img, label, (cx-20, cy-15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                
                # Add X coordinate for debugging choice order
                cv2.putText(questions_img, f"x{cx}", (cx-15, cy+25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
                
                # Add question number on the left side
                if choice_idx == 0:
                    cv2.putText(questions_img, f"{q_num+1}", (cx-50, cy), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.imwrite(os.path.join(debug_dir, "analysis", "03_grouped_questions.jpg"), questions_img)
        
        # Create a summary image with statistics
        summary_img = np.zeros((500, 800, 3), dtype=np.uint8)
        info_lines = [
            f"Detection Summary - {timestamp}",
            f"Total contours found: {len(bubble_contours)}",
            f"Valid question rows: {len(questions_bubbles)}",
            f"Expected questions: {self.questions}",
            f"Questions with 4 choices: {len([r for r in questions_bubbles if len(r) == 4])}",
            "",
            "Training Parameters:",
            f"Area range: {self.training_params['area_min']}-{self.training_params['area_max']}",
            f"Circularity min: {self.training_params['circularity_min']}",
            f"Fill variance threshold: {self.training_params['fill_variance_threshold']}",
            f"Min fill score: {self.training_params['min_fill_score']}",
            "",
            "Color Legend:",
            "Red: Small bubbles (<100 area)",
            "Green: Normal bubbles (100-300 area)",
            "Magenta: Large bubbles (>300 area)",
            "",
            "Question Colors:",
            "Red: Choice A, Green: Choice B",
            "Blue: Choice C, Yellow: Choice D"
        ]
        
        for i, line in enumerate(info_lines):
            color = (255, 255, 255) if line else (100, 100, 100)
            cv2.putText(summary_img, line, (20, 30 + i*22), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        cv2.imwrite(os.path.join(debug_dir, "analysis", "04_summary.jpg"), summary_img)
        
        print(f"Debug images saved to: {debug_dir}")
        print(f"  - Processing: threshold and original images")
        print(f"  - Detection: bubble detection results")
        print(f"  - Analysis: grouped questions and summary")
        
        return debug_dir

# Test and train the processor
if __name__ == "__main__":
    processor = TrainedPrecisionOMRProcessor()
    
    # Test with sample image
    sample_image = "DataSets/Set A/Img1.jpeg"
    if os.path.exists(sample_image):
        print(f"Testing trained precision processor with {sample_image}...")
        
        # First, try training on this sample (assuming it's Set A)
        processor.train_on_sample(sample_image, "Set_A")
        
        # Then test the trained model
        results = processor.process_omr_sheet(sample_image)
        
        if results.get("success"):
            print(f"✅ Score: {results['score']:.1f}%")
            print(f"Set Type: {results['set_type']}")
            print(f"Correct: {results['correct_count']}/{results['total_questions']}")
            print(f"Detected questions: {results['detected_questions']}")
            
            # Count non-empty answers
            non_empty = sum(1 for ans in results['student_answers'] if ans >= 0)
            print(f"Detected answers: {non_empty}/100")
            
            # Show first 10 answers
            print("\nFirst 10 answers:")
            for i in range(min(10, len(results['student_answers']), len(results['correct_answers']))):
                student = results['student_answers'][i]
                correct = results['correct_answers'][i] if i < len(results['correct_answers']) else -1
                student_letter = chr(ord('A') + student) if student >= 0 else "None"
                correct_letter = chr(ord('A') + correct) if correct >= 0 else "None"
                status = "✅" if student == correct and student >= 0 else "❌"
                print(f"Q{i+1}: {student_letter} (correct: {correct_letter}) {status}")
                
        else:
            print(f"❌ Error: {results.get('error')}")
    else:
        print(f"Sample image not found: {sample_image}")