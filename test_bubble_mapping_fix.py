#!/usr/bin/env python3
"""
Test script to verify the bubble-to-choice mapping fixes.
This script tests the corrected TrainedPrecisionOMRProcessor.
"""

import os
import sys
from src.processors.trained_precision_omr import TrainedPrecisionOMRProcessor, map_choice_index_to_letter, sort_bubbles_for_choices

def test_helper_functions():
    """Test the new helper functions"""
    print("🧪 Testing helper functions...")
    
    # Test choice mapping
    assert map_choice_index_to_letter(0) == 'A'
    assert map_choice_index_to_letter(1) == 'B' 
    assert map_choice_index_to_letter(2) == 'C'
    assert map_choice_index_to_letter(3) == 'D'
    assert map_choice_index_to_letter(4) is None
    assert map_choice_index_to_letter(-1) is None
    
    print("✅ Choice mapping function works correctly")
    
    # Test bubble sorting (simulate bubble positions)
    test_bubbles = [(100, 50, None), (50, 50, None), (150, 50, None), (75, 50, None)]  # x, y, contour
    sorted_bubbles = sort_bubbles_for_choices(test_bubbles)
    x_positions = [b[0] for b in sorted_bubbles]
    
    assert x_positions == [50, 75, 100, 150], f"Expected [50, 75, 100, 150], got {x_positions}"
    print("✅ Bubble sorting function works correctly")

def test_mapping_with_sample():
    """Test the corrected processor with a sample image"""
    print("\n🔍 Testing corrected OMR processor...")
    
    # Initialize processor
    processor = TrainedPrecisionOMRProcessor()
    
    # Test with sample image
    test_image = "DataSets/Set A/Img1.jpeg"
    
    if os.path.exists(test_image):
        print(f"📁 Processing: {test_image}")
        print("=" * 60)
        
        result = processor.process_omr_sheet(test_image)
        
        if result.get("success"):
            print(f"✅ Processing successful!")
            print(f"📊 Accuracy: {result['score']:.1f}%")
            print(f"🎯 Detected answers: {len([a for a in result['student_answers'] if a >= 0])}/100")
            print(f"🔍 Set type detected: {result['set_type']}")
            
            print("\n📋 First 15 detected answers (verifying A,B,C,D mapping):")
            print("-" * 70)
            print("Q#  | Student | Correct | Status | Verification")
            print("-" * 70)
            
            for i in range(min(15, len(result['student_answers']))):
                student = result['student_answers'][i]
                correct = result['correct_answers'][i] if i < len(result['correct_answers']) else -1
                
                student_letter = map_choice_index_to_letter(student) if student >= 0 else "None"
                correct_letter = map_choice_index_to_letter(correct) if correct >= 0 else "None"
                
                status = "✅ Match" if student == correct and student >= 0 else "❌ Wrong" if student >= 0 else "⚪ Empty"
                
                # Additional verification
                verification = "GOOD" if student_letter in ['A', 'B', 'C', 'D'] else "ERROR" if student >= 0 else "EMPTY"
                
                print(f"{i+1:2d}  | {student_letter:7s} | {correct_letter:7s} | {status:8s} | {verification}")
            
            print("-" * 70)
            
            # Check for specific mapping issues
            detected_answers = [a for a in result['student_answers'] if a >= 0]
            if detected_answers:
                choice_distribution = {}
                for ans in detected_answers:
                    letter = map_choice_index_to_letter(ans)
                    choice_distribution[letter] = choice_distribution.get(letter, 0) + 1
                
                print(f"\n📈 Choice distribution (should be varied):")
                for letter in ['A', 'B', 'C', 'D']:
                    count = choice_distribution.get(letter, 0)
                    percentage = (count / len(detected_answers)) * 100 if detected_answers else 0
                    print(f"   {letter}: {count:2d} times ({percentage:4.1f}%)")
                
                # Check for suspicious patterns
                max_choice_ratio = max(choice_distribution.values()) / len(detected_answers) if detected_answers else 0
                if max_choice_ratio > 0.7:
                    print(f"⚠️  WARNING: One choice appears {max_choice_ratio:.1%} of the time - possible mapping issue!")
                else:
                    print(f"✅ Choice distribution looks reasonable (max: {max_choice_ratio:.1%})")
            
            print(f"\n🎯 Debug files created:")
            print(f"   - debug_ultimate_omr.jpg (overall results)")
            print(f"   - debug_choice_mapping.jpg (choice position mapping)")
            print(f"   - Check console output above for detailed position verification")
            
        else:
            print(f"❌ Error: {result.get('error')}")
            
    else:
        print(f"⚠️  Test image not found: {test_image}")
        print("   Available test images:")
        if os.path.exists("DataSets"):
            for folder in os.listdir("DataSets"):
                folder_path = os.path.join("DataSets", folder)
                if os.path.isdir(folder_path):
                    files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    print(f"     {folder}: {files[:3]}...")  # Show first 3 files

def main():
    print("🔧 BUBBLE-TO-CHOICE MAPPING FIX VALIDATION")
    print("=" * 50)
    print("This script tests the fixes for the bubble detection mapping issue")
    print("where detected choices were showing wrong letters (A vs D problem).")
    print("=" * 50)
    
    # Test helper functions first
    test_helper_functions()
    
    # Test with actual image
    test_mapping_with_sample()
    
    print("\n" + "=" * 50)
    print("🎯 MAPPING FIX SUMMARY:")
    print("1. ✅ Added proper left-to-right bubble sorting")
    print("2. ✅ Created centralized choice index → letter mapping")
    print("3. ✅ Fixed all methods to use consistent mapping")
    print("4. ✅ Added visual debugging for position verification")
    print("5. ✅ Added validation of A,B,C,D order in bubble groups")
    print("=" * 50)

if __name__ == "__main__":
    main()