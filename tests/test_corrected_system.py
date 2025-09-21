import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'processors'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
from corrected_omr import CorrectedOMRProcessor

def test_multiple_images():
    """Test the corrected OMR processor with multiple images"""
    processor = CorrectedOMRProcessor()
    
    # Test with Set A images
    print("Testing OMR System - Bubble Mapping Correction")
    print("=" * 60)
    
    set_a_path = "DataSets/Set A"
    if os.path.exists(set_a_path):
        image_files = [f for f in os.listdir(set_a_path) if f.lower().endswith(('.jpeg', '.jpg', '.png'))]
        image_files.sort()
        
        total_score = 0
        total_images = 0
        total_detected = 0
        
        print(f"\nTesting {len(image_files)} images from Set A:")
        print("-" * 60)
        
        for i, image_file in enumerate(image_files[:10]):  # Test first 10 images
            image_path = os.path.join(set_a_path, image_file)
            print(f"\nProcessing {image_file}...")
            
            results = processor.process_omr_sheet(image_path)
            
            if results.get("success"):
                score = results['score']
                detected = sum(1 for ans in results['student_answers'] if ans >= 0)
                correct_count = results['correct_count']
                total_questions = results['total_questions']
                
                total_score += score
                total_images += 1
                total_detected += detected
                
                print(f"  ✅ Score: {score:.1f}% ({correct_count}/{total_questions})")
                print(f"  📊 Detected: {detected}/100 answers")
                print(f"  🎯 Set Type: {results['set_type']}")
                
                # Show sample answers for verification
                sample_answers = []
                for j in range(min(5, len(results['student_answers']))):
                    student = results['student_answers'][j]
                    correct = results['correct_answers'][j]
                    student_letter = chr(ord('A') + student) if student >= 0 else "None"
                    correct_letter = chr(ord('A') + correct)
                    status = "✅" if student == correct else "❌"
                    sample_answers.append(f"Q{j+1}:{student_letter}→{correct_letter}{status}")
                
                print(f"  📝 Sample: {' '.join(sample_answers)}")
                
            else:
                print(f"  ❌ Error: {results.get('error')}")
        
        # Summary statistics
        if total_images > 0:
            avg_score = total_score / total_images
            avg_detected = total_detected / total_images
            
            print("\n" + "=" * 60)
            print("SUMMARY RESULTS:")
            print("=" * 60)
            print(f"📈 Average Score: {avg_score:.1f}%")
            print(f"🎯 Average Detection: {avg_detected:.1f}/100 answers")
            print(f"📊 Images Processed: {total_images}")
            
            # Evaluate success
            if avg_detected >= 90:
                print("🟢 DETECTION: Excellent (90%+ answers detected)")
            elif avg_detected >= 70:
                print("🟡 DETECTION: Good (70%+ answers detected)")
            else:
                print("🔴 DETECTION: Needs improvement (<70% answers detected)")
            
            if avg_score >= 70:
                print("🟢 ACCURACY: Excellent (70%+ correct)")
            elif avg_score >= 50:
                print("🟡 ACCURACY: Good (50%+ correct)")
            else:
                print("🔴 ACCURACY: Needs improvement (<50% correct)")
        
        # Test the original problem case
        print("\n" + "=" * 60)
        print("TESTING ORIGINAL PROBLEM:")
        print("Issue: 'student answer as A but in OMR sheet image it is option D'")
        print("=" * 60)
        
        # Process first image in detail
        if image_files:
            first_image = os.path.join(set_a_path, image_files[0])
            results = processor.process_omr_sheet(first_image)
            
            if results.get("success"):
                # Look for cases where student marked D but system detects A (or vice versa)
                mapping_issues = []
                
                for q_num, (student, correct) in enumerate(zip(results['student_answers'], results['correct_answers'])):
                    if student >= 0:  # Valid answer detected
                        student_letter = chr(ord('A') + student)
                        correct_letter = chr(ord('A') + correct)
                        
                        # Check for potential mapping issues
                        if abs(student - correct) > 1:  # Significant difference
                            mapping_issues.append((q_num+1, student_letter, correct_letter))
                
                print(f"Found {len(mapping_issues)} potential mapping issues:")
                for q_num, student_letter, correct_letter in mapping_issues[:10]:
                    print(f"  Q{q_num}: Detected {student_letter}, Expected {correct_letter}")
                
                if len(mapping_issues) == 0:
                    print("🟢 No significant mapping issues detected!")
                elif len(mapping_issues) < 20:
                    print("🟡 Minor mapping issues - within acceptable range")
                else:
                    print("🔴 Significant mapping issues detected")
    
    else:
        print("Set A directory not found!")

if __name__ == "__main__":
    test_multiple_images()