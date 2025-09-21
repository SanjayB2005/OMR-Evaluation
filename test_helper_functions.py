"""
Bubble Mapping Diagnostic Tool - Based on user's requested helper code
This implements the exact helper functions from the user's request to fix bubble-to-choice mapping.
"""

import cv2
import numpy as np
import string
import os

def sort_contours_grid(contours, rows, cols, method="tlbr", row_tol=10):
    """
    Sort contours into a grid with `rows` rows and `cols` columns.
    Returns a list-of-lists: grid[r][c] -> contour
    method: "tlbr" = top-to-bottom then left-to-right
    row_tol: vertical tolerance in pixels for grouping into rows
    """
    # get bounding boxes
    bboxes = [cv2.boundingRect(c) for c in contours]
    # pair them to allow stable sort
    items = list(zip(contours, bboxes))
    # sort by y coordinate (top to bottom)
    items.sort(key=lambda x: x[1][1])
    # group into rows
    rows_list = []
    current_row = []
    current_y = None
    for cnt, (x, y, w, h) in items:
        if current_y is None:
            current_y = y
        if abs(y - current_y) <= row_tol:
            current_row.append((cnt, (x,y,w,h)))
        else:
            # sort the current row left-to-right
            current_row.sort(key=lambda it: it[1][0])
            rows_list.append([it[0] for it in current_row])
            current_row = [(cnt,(x,y,w,h))]
            current_y = y
    if current_row:
        current_row.sort(key=lambda it: it[1][0])
        rows_list.append([it[0] for it in current_row])

    # If grouping created more or fewer rows than expected, try to rebucket by simple split
    if len(rows_list) != rows:
        # fallback: split items evenly
        flat_sorted = [it[0] for it in items]
        rows_list = []
        per_row = int(round(len(flat_sorted) / rows))
        for r in range(rows):
            start = r*per_row
            end = start + per_row
            rows_list.append(flat_sorted[start:end])
    # ensure each row has exactly cols by trimming/padding (best-effort)
    grid = []
    for r in rows_list[:rows]:
        if len(r) >= cols:
            grid.append(r[:cols])
        else:
            # pad with None to keep structure (unlikely if detection good)
            r += [None]*(cols - len(r))
            grid.append(r)
    return grid  # grid[0..rows-1][0..cols-1]

def detect_filled_from_bubble(image_gray, contour):
    """
    Given gray image and a contour of a bubble, compute fill metric.
    Returns a float where lower usually means filled (if filled bubble is darker).
    You may invert logic depending on preprocessing.
    """
    mask = np.zeros(image_gray.shape, dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    # compute mean intensity inside the contour
    mean_val = cv2.mean(image_gray, mask=mask)[0]
    return mean_val

def map_index_to_label(idx, options=4, start_letter='A', reverse=False):
    letters = list(string.ascii_uppercase)
    labels = letters[:options]
    if reverse:
        labels = labels[::-1]
    if idx is None or idx < 0 or idx >= len(labels):
        return None
    return labels[idx]

def evaluate_sheet(image_bgr, bubble_contours, rows, cols, options=4,
                   threshold_fill=130, reverse_col_order=False, debug=False):
    """
    - image_bgr: original image (BGR)
    - bubble_contours: list of all bubble contours (unsorted)
    - rows, cols: grid dimensions (number of question rows and bubble columns per row grouping)
    - options: number of choices per question (e.g., 4)
    Returns: list of selected labels per question (None if ambiguous)
    """
    img_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    grid = sort_contours_grid(bubble_contours, rows, options)
    selections = []
    annotated = image_bgr.copy()
    qnum = 0
    for r, row in enumerate(grid):
        # if a row contains contiguous groups of 'options' bubbles per question,
        # you may need to split row into questions: e.g., if each question uses options bubbles only
        # simplest case: each row corresponds to exactly 1 question (or adjust accordingly)
        # Here we assume each row contains exactly 'options' contours representing that question.
        if len(row) < options:
            # skip malformed rows
            continue
        # compute fill for each bubble in the row
        fills = [detect_filled_from_bubble(img_gray, c) if c is not None else 255 for c in row]
        # smaller mean -> darker -> likely filled (adjust threshold logic as needed)
        # decide chosen index using min or threshold
        idx = int(np.argmin(fills))
        # optionally apply absolute threshold to avoid accidental low-diff
        # if fills[idx] > threshold_fill: -> treat as blank
        chosen_label = None
        if fills[idx] < threshold_fill:
            chosen_label = map_index_to_label(idx, options=options, reverse=reverse_col_order)
        else:
            chosen_label = None

        selections.append(chosen_label)

        # debug markup
        if debug:
            for i, c in enumerate(row):
                if c is None: continue
                x,y,w,h = cv2.boundingRect(c)
                cv2.rectangle(annotated, (x,y), (x+w,y+h), (200,200,200), 1)
                cv2.putText(annotated, str(i), (x+3,y+15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255),1)
            # mark selection
            if idx < len(row) and row[idx] is not None:
                sx,sy,sw,sh = cv2.boundingRect(row[idx])
                cv2.putText(annotated, f"Q{qnum}:{chosen_label}", (sx, sy-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0),1)
        qnum += 1

    if debug:
        cv2.imwrite("helper_debug_annotated.jpg", annotated)
        print("Debug annotated image saved as: helper_debug_annotated.jpg")
    return selections

def test_helper_functions():
    """Test the helper functions with sample image"""
    print("🧪 Testing helper functions from user request...")
    
    # Test image
    test_image = "DataSets/Set A/Img1.jpeg"
    
    if not os.path.exists(test_image):
        print(f"❌ Test image not found: {test_image}")
        return
    
    # Load image
    img = cv2.imread(test_image)
    if img is None:
        print(f"❌ Could not load image: {test_image}")
        return
        
    # Resize for consistency  
    img = cv2.resize(img, (600, 800))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply threshold to find bubbles
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter for bubble-like contours
    bubble_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if 50 < area < 400:  # Bubble size range
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity > 0.3:  # Reasonably circular
                    bubble_contours.append(contour)
    
    print(f"Found {len(bubble_contours)} potential bubble contours")
    
    if len(bubble_contours) >= 20:  # Need at least 20 bubbles for 5 questions
        # Test the helper function
        rows = 5  # 5 questions
        options = 4  # 4 choices each
        
        # Use helper function to analyze sheet
        selections = evaluate_sheet(img, bubble_contours, rows, rows, options=options, debug=True)
        
        print(f"\n📋 Results from helper function:")
        print(f"Detected {len([s for s in selections if s is not None])}/{len(selections)} answers")
        
        for i, selection in enumerate(selections[:10]):  # Show first 10
            if selection is not None:
                print(f"Q{i+1}: {selection}")
            else:
                print(f"Q{i+1}: No answer detected")
                
        print(f"\n✅ Helper function test completed")
        print(f"📁 Debug image saved: helper_debug_annotated.jpg")
        
    else:
        print(f"❌ Not enough bubble contours found ({len(bubble_contours)} < 20)")

if __name__ == "__main__":
    print("🔧 TESTING USER-REQUESTED HELPER FUNCTIONS")
    print("=" * 50)
    print("Testing the exact helper code provided in the user's request")
    print("to diagnose and fix bubble-to-choice mapping issues.")
    print("=" * 50)
    
    test_helper_functions()
    
    print("\n" + "=" * 50)
    print("🎯 HELPER FUNCTION VERIFICATION COMPLETE")
    print("These functions can be integrated into your existing pipeline")
    print("to fix the bubble detection → choice letter mapping issues.")
    print("=" * 50)