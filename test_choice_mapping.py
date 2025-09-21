#!/usr/bin/env python3
"""
Test script to verify the improved choice mapping system
"""

import os
import sys

# Add the src directory to path
sys.path.append('src/processors')
sys.path.append('src/core')

from trained_precision_omr import TrainedPrecisionOMRProcessor

def test_choice_mapping():
    """Test the choice mapping specifically"""
    processor = TrainedPrecisionOMRProcessor()
    
    # Test with a specific image
    test_image = "DataSets/Set A/Img1.jpeg"
    
    if os.path.exists(test_image):
        print("🔍 Testing improved choice mapping system...")
        print("=" * 60)
        
        result = processor.process_omr_sheet(test_image)
        
        if result.get("success"):
            print(f"✅ Processing successful!")
            print(f"📊 Accuracy: {result['score']:.1f}%")
            print(f"🎯 Detected answers: {len([a for a in result['student_answers'] if a >= 0])}/100")
            print(f"🔍 Question rows found: {result['detected_questions']}")
            
            print("\n📋 First 10 detected answers with choice mapping:")
            print("-" * 50)
            for i in range(min(10, len(result['student_answers']), len(result['correct_answers']))):
                student = result['student_answers'][i]
                correct = result['correct_answers'][i] if i < len(result['correct_answers']) else -1
                student_letter = chr(ord('A') + student) if student >= 0 else "None"
                correct_letter = chr(ord('A') + correct) if correct >= 0 else "None"
                status = "✅" if student == correct and student >= 0 else "❌"
                print(f"Q{i+1:2d}: Detected = {student_letter:4s} | Correct = {correct_letter:4s} | {status}")
                
            print(f"\n🎯 Check the debug images in the latest debug_output folder")
            print("   Look for 'analysis/03_grouped_questions.jpg' to verify choice mapping")
            print("   Red=A, Green=B, Blue=C, Yellow=D")
            print("   X coordinates are shown to verify left-to-right order")
            
        else:
            print(f"❌ Error: {result.get('error')}")
    else:
        print(f"⚠️ Test image not found: {test_image}")

if __name__ == "__main__":
    test_choice_mapping()