"""
ANSWER KEY VERIFICATION TEST
===========================
This test checks if the issue is that we're using the wrong answer key
for the specific OMR image being tested.

The algorithm might be working correctly, but we're comparing against
the wrong expected answers.
"""

import cv2
import numpy as np
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'processors'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))
from src.processors.trained_precision_omr import TrainedPrecisionOMRProcessor
from data_handler import OMRDataHandler

def verify_answer_key_match():
    """Check if the answer key matches what's actually marked on the sheet"""
    
    print("🔍 ANSWER KEY VERIFICATION TEST")
    print("=" * 50)
    
    # Initialize
    processor = TrainedPrecisionOMRProcessor()
    data_handler = OMRDataHandler()
    data_handler.load_answer_keys()
    
    # Test image
    test_image = "DataSets/Set A/Img1.jpeg"
    print(f"📄 Testing image: {test_image}")
    
    # Show available answer keys
    print(f"\\n📚 Available answer keys:")
    for set_name, answers in data_handler.answer_keys.items():
        print(f"   {set_name}: {len(answers)} answers")
        print(f"   First 10: {answers[:10]}")
    
    # Process the image
    result = processor.process_omr_sheet(test_image)
    
    if result['success']:
        detected_answers = result.get('student_answers', [])
        detected_set_type = result.get('set_type', 'Unknown')
        
        print(f"\\n🎯 DETECTION RESULTS:")
        print(f"   Detected set type: {detected_set_type}")
        print(f"   Detected {len(detected_answers)} answers")
        print(f"   First 10 detected: {detected_answers[:10]}")
        
        # Check against all answer keys to see which matches best
        print(f"\\n🔍 ANSWER KEY COMPARISON:")
        
        best_match_set = None
        best_match_score = 0
        
        for set_name, correct_answers in data_handler.answer_keys.items():
            if len(correct_answers) > 0:
                # Calculate how many match
                matches = 0
                total_compared = min(len(detected_answers), len(correct_answers))
                
                for i in range(total_compared):
                    if i < len(detected_answers) and detected_answers[i] >= 0:
                        detected_letter = ['A', 'B', 'C', 'D'][detected_answers[i]]
                        if detected_letter == correct_answers[i]:
                            matches += 1
                
                match_percentage = (matches / total_compared) * 100 if total_compared > 0 else 0
                print(f"   {set_name}: {matches}/{total_compared} matches ({match_percentage:.1f}%)")
                
                if match_percentage > best_match_score:
                    best_match_score = match_percentage
                    best_match_set = set_name
        
        print(f"\\n🏆 BEST MATCH: {best_match_set} with {best_match_score:.1f}% accuracy")
        
        if best_match_score < 50:
            print(f"\\n⚠️  WARNING: Best match is only {best_match_score:.1f}%")
            print("   This suggests one of these issues:")
            print("   1. The image filename doesn't match any available answer key")
            print("   2. The OMR sheet is filled differently than expected")
            print("   3. The detection algorithm needs further calibration")
            print("   4. The image is a practice sheet or has different answers")
        
        # Manual verification for a few questions
        print(f"\\n🔍 MANUAL VERIFICATION (First 10 questions):")
        print("Compare these detected answers with what you see visually marked:")
        
        correct_answers = data_handler.answer_keys.get(best_match_set, [])
        
        for i in range(min(10, len(detected_answers))):
            detected_letter = ['A', 'B', 'C', 'D'][detected_answers[i]] if detected_answers[i] >= 0 else 'None'
            expected_letter = correct_answers[i] if i < len(correct_answers) else 'N/A'
            
            status = "✅" if detected_letter == expected_letter else "❌"
            print(f"   Q{i+1:2d}: Detected={detected_letter}, Expected={expected_letter} {status}")
    
    else:
        print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    verify_answer_key_match()