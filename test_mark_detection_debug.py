"""
MARK DETECTION DEBUG TEST
==========================
This script focuses on debugging the mark detection algorithm specifically.
The issue isn't the A/B/C/D mapping - it's that the algorithm is detecting the wrong bubbles as filled.
"""

import cv2
import numpy as np
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'processors'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))
from trained_precision_omr import TrainedPrecisionOMRProcessor
from data_handler import OMRDataHandler

def debug_mark_detection():
    print("🔍 MARK DETECTION ALGORITHM DEBUG")
    print("=" * 50)
    
    # Initialize processor and data handler
    processor = TrainedPrecisionOMRProcessor()
    data_handler = OMRDataHandler()
    
    # Load answer keys to know what SHOULD be detected
    data_handler.load_answer_keys()
    
    # Test with one image
    test_image = "DataSets/Set A/Img1.jpeg"
    if not os.path.exists(test_image):
        print(f"❌ Test image not found: {test_image}")
        return
    
    print(f"📄 Testing: {test_image}")
    
    # Process the image
    result = processor.process_omr_sheet(test_image)
    
    if result['success']:
        # Check what keys are available in result
        print(f"🔑 Available result keys: {list(result.keys())}")
        
        detected_answers = result.get('student_answers', result.get('answers', []))
        set_type = result.get('set_type', 'Set_A')
        correct_answers = data_handler.answer_keys[set_type]
        
        print(f"\n🎯 Set Type: {set_type}")
        print(f"📊 Detected: {len(detected_answers)} answers")
        print(f"📚 Expected: {len(correct_answers)} answers")
        
        print("\n🔍 DETAILED MARK DETECTION ANALYSIS (First 20 questions)")
        print("-" * 80)
        print("Q#  | Detected | Correct | Match | Issue Analysis")
        print("-" * 80)
        
        issues_summary = {
            'correct': 0,
            'wrong_choice': 0,
            'missing': 0,
            'total': 0
        }
        
        for i in range(min(20, len(correct_answers))):
            q_num = i + 1
            correct_choice = correct_answers[i]
            detected_choice = detected_answers[i] if i < len(detected_answers) else 'None'
            
            issues_summary['total'] += 1
            
            if detected_choice == 'None':
                status = "❌ Missing"
                issue = "Not detected"
                issues_summary['missing'] += 1
            elif detected_choice == correct_choice:
                status = "✅ Correct"
                issue = "Perfect"
                issues_summary['correct'] += 1
            else:
                status = "❌ Wrong"
                issue = f"Should be {correct_choice}"
                issues_summary['wrong_choice'] += 1
            
            print(f"{q_num:2d}  | {str(detected_choice):8s} | {str(correct_choice):7s} | {status:9s} | {issue}")
        
        print("-" * 80)
        print(f"\n📈 ISSUE SUMMARY:")
        print(f"   ✅ Correct detections: {issues_summary['correct']}/{issues_summary['total']} ({issues_summary['correct']/issues_summary['total']*100:.1f}%)")
        print(f"   ❌ Wrong choice detected: {issues_summary['wrong_choice']}/{issues_summary['total']} ({issues_summary['wrong_choice']/issues_summary['total']*100:.1f}%)")
        print(f"   ⚠️  Missing detections: {issues_summary['missing']}/{issues_summary['total']} ({issues_summary['missing']/issues_summary['total']*100:.1f}%)")
        
        # Analyze the pattern of wrong detections
        print(f"\n🔍 PATTERN ANALYSIS:")
        wrong_patterns = {}
        for i in range(min(len(detected_answers), len(correct_answers))):
            detected = detected_answers[i]
            correct = correct_answers[i]
            if detected != 'None' and detected != correct:
                pattern = f"{correct}→{detected}"
                wrong_patterns[pattern] = wrong_patterns.get(pattern, 0) + 1
        
        print("   Common wrong detection patterns:")
        for pattern, count in sorted(wrong_patterns.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {pattern}: {count} times")
        
        # Check if there's a systematic bias
        choice_bias = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for answer in detected_answers:
            if answer in choice_bias:
                choice_bias[answer] += 1
        
        print(f"\n📊 DETECTION BIAS ANALYSIS:")
        total_detected = sum(choice_bias.values())
        for choice, count in choice_bias.items():
            percentage = count / total_detected * 100 if total_detected > 0 else 0
            print(f"   {choice}: {count} times ({percentage:.1f}%)")
        
        # Check if bias towards certain positions (A is often over-detected)
        if choice_bias['A'] > choice_bias['B'] + choice_bias['C'] + choice_bias['D']:
            print("   ⚠️  MAJOR BIAS: Choice A is heavily over-detected!")
            print("   🔧 This suggests the mark detection algorithm has a position bias.")
        
    else:
        print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    debug_mark_detection()