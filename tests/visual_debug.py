import cv2
import numpy as np
import os

def create_visual_debug():
    """Create a visual debugging tool to understand OMR layout"""
    
    # Load test image
    img_path = "DataSets/Set A/Img1.jpeg"
    img = cv2.imread(img_path)
    if img is None:
        print("Could not load image")
        return
    
    # Resize to standard size
    height, width = 700, 700
    img = cv2.resize(img, (width, height))
    original = img.copy()
    
    # Apply preprocessing similar to OMR processor
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 1)
    edges = cv2.Canny(blur, 10, 70)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    
    # Filter for rectangular contours
    rect_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 50:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                rect_contours.append(contour)
    
    rect_contours = sorted(rect_contours, key=cv2.contourArea, reverse=True)
    
    if len(rect_contours) > 0:
        # Get the biggest rectangle (OMR sheet)
        biggest_contour = rect_contours[0]
        
        # Get corner points
        peri = cv2.arcLength(biggest_contour, True)
        approx = cv2.approxPolyDP(biggest_contour, 0.02 * peri, True)
        
        if len(approx) == 4:
            # Reorder points
            points = approx.reshape((4, 2))
            ordered_points = np.zeros((4, 2), dtype=np.float32)
            
            # Sum and difference to find corners
            s = points.sum(axis=1)
            diff = np.diff(points, axis=1)
            
            ordered_points[0] = points[np.argmin(s)]      # top-left
            ordered_points[2] = points[np.argmax(s)]      # bottom-right
            ordered_points[1] = points[np.argmin(diff)]   # top-right
            ordered_points[3] = points[np.argmax(diff)]   # bottom-left
            
            # Apply perspective transform
            pts1 = np.float32(ordered_points)
            pts2 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
            matrix = cv2.getPerspectiveTransform(pts1, pts2)
            warped = cv2.warpPerspective(original, matrix, (width, height))
            
            # Save warped image
            cv2.imwrite("debug_warped_sheet.jpg", warped)
            
            # Now analyze the warped sheet structure
            analyze_warped_structure(warped)
            
            return warped
    
    return None

def analyze_warped_structure(img):
    """Analyze the structure of the warped OMR sheet"""
    
    # Convert to grayscale and threshold
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY_INV)
    
    # Create test grids to visualize different layouts
    test_layouts = [
        {"name": "4_columns_25_rows", "cols": 4, "rows": 25},
        {"name": "5_columns_20_rows", "cols": 5, "rows": 20},
        {"name": "10_columns_10_rows", "cols": 10, "rows": 10},
    ]
    
    for layout in test_layouts:
        test_img = img.copy()
        cols = layout["cols"]
        rows = layout["rows"]
        
        # Draw grid
        col_width = img.shape[1] // cols
        row_height = img.shape[0] // rows
        
        # Vertical lines
        for i in range(cols + 1):
            x = i * col_width
            cv2.line(test_img, (x, 0), (x, img.shape[0]), (0, 255, 0), 2)
        
        # Horizontal lines
        for i in range(rows + 1):
            y = i * row_height
            cv2.line(test_img, (0, y), (img.shape[1], y), (0, 255, 0), 2)
        
        # Save test image
        cv2.imwrite(f"debug_grid_{layout['name']}.jpg", test_img)
        print(f"Created test grid: {layout['name']}")
    
    # Analyze actual bubble positions
    find_actual_bubbles(thresh, img)

def find_actual_bubbles(thresh_img, original_img):
    """Find actual bubble positions in the OMR sheet"""
    
    # Find contours in thresholded image
    contours, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter for bubble-like contours
    bubbles = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if 20 < area < 1000:  # Bubble size range
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            if 0.3 < aspect_ratio < 3.0:  # Reasonable aspect ratio
                bubbles.append((x, y, w, h, area))
    
    print(f"Found {len(bubbles)} potential bubbles")
    
    # Sort bubbles by position (top to bottom, left to right)
    bubbles.sort(key=lambda b: (b[1], b[0]))
    
    # Create bubble visualization
    bubble_img = original_img.copy()
    for i, (x, y, w, h, area) in enumerate(bubbles):
        # Color code by position
        if i < 50:
            color = (255, 0, 0)  # Red for first 50
        elif i < 100:
            color = (0, 255, 0)  # Green for next 50
        elif i < 200:
            color = (0, 0, 255)  # Blue for next 100
        else:
            color = (255, 255, 0)  # Yellow for rest
        
        cv2.rectangle(bubble_img, (x, y), (x+w, y+h), color, 2)
        cv2.putText(bubble_img, str(i), (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
    
    cv2.imwrite("debug_actual_bubbles.jpg", bubble_img)
    
    # Analyze bubble rows
    analyze_bubble_rows(bubbles, original_img)

def analyze_bubble_rows(bubbles, original_img):
    """Group bubbles into rows and analyze the pattern"""
    
    if not bubbles:
        return
    
    # Group bubbles by Y position (rows)
    rows = []
    current_row = []
    last_y = -1
    tolerance = 15  # Y position tolerance for same row
    
    for bubble in bubbles:
        x, y, w, h, area = bubble
        
        if last_y == -1 or abs(y - last_y) < tolerance:
            current_row.append(bubble)
        else:
            if len(current_row) > 0:
                rows.append(sorted(current_row, key=lambda b: b[0]))  # Sort by X
            current_row = [bubble]
        
        last_y = y
    
    # Add the last row
    if len(current_row) > 0:
        rows.append(sorted(current_row, key=lambda b: b[0]))
    
    print(f"Found {len(rows)} bubble rows")
    
    # Analyze row patterns
    row_img = original_img.copy()
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
    
    for i, row in enumerate(rows[:20]):  # Show first 20 rows
        color = colors[i % len(colors)]
        print(f"Row {i}: {len(row)} bubbles")
        
        for j, (x, y, w, h, area) in enumerate(row):
            cv2.rectangle(row_img, (x, y), (x+w, y+h), color, 2)
            cv2.putText(row_img, f"R{i}C{j}", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
    
    cv2.imwrite("debug_bubble_rows.jpg", row_img)
    
    # Determine the most likely pattern
    row_lengths = [len(row) for row in rows if len(row) > 2]
    if row_lengths:
        from collections import Counter
        most_common_length = Counter(row_lengths).most_common(1)[0][0]
        print(f"Most common row length: {most_common_length} bubbles per row")
        
        if most_common_length == 4:
            print("Detected pattern: 4 choices per question (A, B, C, D)")
        elif most_common_length == 5:
            print("Detected pattern: 5 choices per question (A, B, C, D, E)")
        elif most_common_length >= 16:
            print("Detected pattern: Multiple questions per row")

if __name__ == "__main__":
    print("Starting visual OMR debugging...")
    warped = create_visual_debug()
    if warped is not None:
        print("Visual debugging completed. Check the generated debug images:")
        print("- debug_warped_sheet.jpg")
        print("- debug_grid_*.jpg")
        print("- debug_actual_bubbles.jpg") 
        print("- debug_bubble_rows.jpg")
    else:
        print("Could not process the OMR sheet for debugging")