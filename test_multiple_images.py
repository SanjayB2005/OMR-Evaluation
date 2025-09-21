#!/usr/bin/env python3
"""
Test the improved OMR processor on multiple images to check consistency
"""

import os
import sys

# Add the src directory to path
sys.path.append('src/processors')
sys.path.append('src/core')

from trained_precision_omr import TrainedPrecisionOMRProcessor

def test_multiple_images():
    """Test the processor on multiple images"""
    processor = TrainedPrecisionOMRProcessor()
    
    # Test images from different sets
    test_images = [
        "DataSets/Set A/Img1.jpeg",
        "DataSets/Set A/Img2.jpeg", 
        "DataSets/Set A/Img3.jpeg",
        "DataSets/Set B/Img9.jpeg",
        "DataSets/Set B/Img10.jpeg"
    ]
    
    total_accuracy = 0
    total_detection = 0
    successful_tests = 0
    
    print("=" * 80)
    print("TESTING IMPROVED OMR PROCESSOR ON MULTIPLE IMAGES")
    print("=" * 80)
    
    for image_path in test_images:
        if os.path.exists(image_path):
            print(f"\n📸 Testing: {image_path}")
            print("-" * 60)
            
            result = processor.process_omr_sheet(image_path)
            
            if result.get("success"):
                accuracy = result['score']
                detected = len([a for a in result['student_answers'] if a >= 0])
                total_accuracy += accuracy
                total_detection += detected
                successful_tests += 1
                
                print(f"✅ Accuracy: {accuracy:.1f}%")
                print(f"📊 Correct answers: {result['correct_count']}/{result['total_questions']}")
                print(f"🎯 Detected answers: {detected}/100")
                print(f"📋 Set identified: {result['set_type']}")
                print(f"🔍 Question rows found: {result['detected_questions']}")
                
                # Show first 5 answers for verification
                print("\nFirst 5 answers:")
                for i in range(min(5, len(result['student_answers']), len(result['correct_answers']))):
                    student = result['student_answers'][i]
                    correct = result['correct_answers'][i] if i < len(result['correct_answers']) else -1
                    student_letter = chr(ord('A') + student) if student >= 0 else "None"
                    correct_letter = chr(ord('A') + correct) if correct >= 0 else "None"
                    status = "✅" if student == correct and student >= 0 else "❌"
                    print(f"  Q{i+1}: {student_letter} (correct: {correct_letter}) {status}")
            else:
                print(f"❌ Failed: {result.get('error')}")
        else:
            print(f"⚠️ Image not found: {image_path}")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    if successful_tests > 0:
        avg_accuracy = total_accuracy / successful_tests
        avg_detection = total_detection / successful_tests
        
        print(f"📈 Average Accuracy: {avg_accuracy:.1f}%")
        print(f"🎯 Average Detection: {avg_detection:.1f} answers per sheet")
        print(f"✅ Successful tests: {successful_tests}/{len(test_images)}")
        
        # Performance assessment
        if avg_accuracy >= 10:
            grade = "🌟 EXCELLENT"
        elif avg_accuracy >= 7:
            grade = "👍 GOOD"
        elif avg_accuracy >= 5:
            grade = "🔧 IMPROVING"
        else:
            grade = "⚠️ NEEDS WORK"
            
        print(f"📊 Performance Grade: {grade}")
        
        # Detection assessment
        if avg_detection >= 50:
            detection_grade = "🌟 EXCELLENT"
        elif avg_detection >= 30:
            detection_grade = "👍 GOOD"
        elif avg_detection >= 15:
            detection_grade = "🔧 IMPROVING"
        else:
            detection_grade = "⚠️ NEEDS WORK"
            
        print(f"🔍 Detection Grade: {detection_grade}")
    else:
        print("❌ No successful tests completed")

if __name__ == "__main__":
    test_multiple_images()