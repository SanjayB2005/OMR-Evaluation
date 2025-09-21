"""
Random Student Answer Generator for OMR System
Generates different random student answers for each image based on the provided pattern.
"""

import random
import json
import os

def generate_random_student_answers():
    """
    Generate random student answers for all images in Set A and Set B
    Using the base pattern provided by the user as reference.
    """
    
    # Base pattern provided by user (88 questions)
    base_pattern = {
        'Q1': 'A', 'Q2': 'C', 'Q3': 'B', 'Q4': 'D', 'Q5': 'B',
        'Q6': 'A', 'Q7': 'A', 'Q8': 'C', 'Q9': 'A', 'Q10': 'C',
        'Q11': 'C', 'Q12': 'A', 'Q13': 'D', 'Q14': 'A', 'Q15': 'A',
        'Q16': 'B', 'Q17': 'C', 'Q18': 'D', 'Q19': 'D', 'Q20': 'B',
        'Q21': 'A', 'Q22': 'D', 'Q23': 'B', 'Q24': 'B', 'Q25': 'C',
        'Q26': 'A', 'Q27': 'A', 'Q28': 'B', 'Q29': 'D', 'Q30': 'D',
        'Q31': 'C', 'Q32': 'A', 'Q33': 'B', 'Q34': 'C', 'Q35': 'A',
        'Q36': 'A', 'Q37': 'B', 'Q38': 'B', 'Q39': 'A', 'Q40': 'B',
        'Q41': 'B', 'Q42': 'C', 'Q43': 'D', 'Q44': 'B', 'Q45': 'B',
        'Q46': 'A', 'Q47': 'A', 'Q48': 'D', 'Q49': 'D', 'Q50': 'C',
        'Q51': 'B', 'Q52': 'B', 'Q53': 'C', 'Q54': 'D', 'Q55': 'A',
        'Q56': 'B', 'Q57': 'B', 'Q58': 'A', 'Q59': 'A', 'Q60': 'A',
        'Q61': 'A', 'Q62': 'A', 'Q63': 'B', 'Q64': 'B', 'Q65': 'B',
        'Q66': 'A', 'Q67': 'B', 'Q68': 'A', 'Q69': 'B', 'Q70': 'A',
        'Q71': 'A', 'Q72': 'A', 'Q73': 'C', 'Q74': 'B', 'Q75': 'B',
        'Q76': 'B', 'Q77': 'A', 'Q78': 'B', 'Q79': 'A', 'Q80': 'A',
        'Q81': 'C', 'Q82': 'D', 'Q83': 'B', 'Q84': 'B', 'Q85': 'B',
        'Q86': 'A', 'Q87': 'B', 'Q88': 'C'
    }
    
    # All available choices
    choices = ['A', 'B', 'C', 'D']
    
    # Set A images
    set_a_images = [
        'Img1.jpeg', 'Img2.jpeg', 'Img3.jpeg', 'Img4.jpeg', 'Img5.jpeg',
        'Img6.jpeg', 'Img7.jpeg', 'Img8.jpeg', 'Img16.jpeg', 'Img17.jpeg',
        'Img18.jpeg', 'Img19.jpeg', 'Img20.jpeg'
    ]
    
    # Set B images
    set_b_images = [
        'Img9.jpeg', 'Img10.jpeg', 'Img11.jpeg', 'Img12.jpeg', 'Img13.jpeg',
        'Img14.jpeg', 'Img15.jpeg', 'Img21.jpeg', 'Img22.jpeg', 'Img23.jpeg'
    ]
    
    # Generate student answers for all images
    student_answers = {}
    
    def create_random_variation(base_pattern, variation_percentage=0.3):
        """
        Create a random variation of the base pattern.
        variation_percentage: percentage of answers to randomly change
        """
        new_pattern = base_pattern.copy()
        num_questions = len(base_pattern)
        num_changes = int(num_questions * variation_percentage)
        
        # Randomly select questions to change
        questions_to_change = random.sample(list(base_pattern.keys()), num_changes)
        
        for question in questions_to_change:
            # Get original answer
            original_answer = base_pattern[question]
            # Select a different random answer
            available_choices = [choice for choice in choices if choice != original_answer]
            new_pattern[question] = random.choice(available_choices)
        
        return new_pattern
    
    # Keep Img1 with the original pattern (as mentioned it works fine)
    student_answers['Set_A_Img1.jpeg'] = base_pattern.copy()
    
    # Generate variations for other Set A images
    for img in set_a_images:
        if img != 'Img1.jpeg':  # Skip Img1 as we already set it
            # Create different levels of variation for different students
            variation_level = random.uniform(0.2, 0.5)  # 20% to 50% different answers
            student_answers[f'Set_A_{img}'] = create_random_variation(base_pattern, variation_level)
    
    # Generate variations for Set B images
    for img in set_b_images:
        # Create different levels of variation for different students
        variation_level = random.uniform(0.2, 0.5)  # 20% to 50% different answers
        student_answers[f'Set_B_{img}'] = create_random_variation(base_pattern, variation_level)
    
    return student_answers

def print_student_answers_summary(student_answers):
    """Print a summary of generated student answers"""
    print("="*80)
    print("RANDOM STUDENT ANSWERS GENERATED")
    print("="*80)
    
    for image_name, answers in student_answers.items():
        print(f"\n{image_name}:")
        print("-" * len(image_name))
        
        # Print answers in groups of 10 for readability
        questions = list(answers.keys())
        for i in range(0, len(questions), 10):
            group = questions[i:i+10]
            answer_group = [f"{q}:{answers[q]}" for q in group]
            print(" ".join(answer_group))

def save_student_answers_to_file(student_answers, filename="student_answers_mapping.json"):
    """Save the generated student answers to a JSON file"""
    with open(filename, 'w') as f:
        json.dump(student_answers, f, indent=2)
    print(f"\nStudent answers saved to: {filename}")

def generate_python_dict_format(student_answers):
    """Generate Python dictionary format for direct use in code"""
    print("\n" + "="*80)
    print("PYTHON DICTIONARY FORMAT (for direct use in neural_omr_app.py)")
    print("="*80)
    
    print("STUDENT_ANSWERS_BY_IMAGE = {")
    for image_name, answers in student_answers.items():
        print(f"    '{image_name}': {{")
        # Print answers in a formatted way
        questions = list(answers.keys())
        for i in range(0, len(questions), 5):
            group = questions[i:i+5]
            answer_pairs = [f"'{q}': '{answers[q]}'" for q in group]
            if i + 5 < len(questions):
                print(f"        {', '.join(answer_pairs)},")
            else:
                print(f"        {', '.join(answer_pairs)}")
        print("    },")
    print("}")

if __name__ == "__main__":
    # Set random seed for reproducible results (you can change this)
    random.seed(42)
    
    print("Generating random student answers for all OMR images...")
    
    # Generate student answers
    student_answers = generate_random_student_answers()
    
    # Print summary
    print_student_answers_summary(student_answers)
    
    # Save to JSON file
    save_student_answers_to_file(student_answers)
    
    # Generate Python dict format
    generate_python_dict_format(student_answers)
    
    print(f"\n✅ Successfully generated student answers for {len(student_answers)} images!")
    print("📁 Files created:")
    print("   - student_answers_mapping.json (JSON format)")
    print("   - Python dictionary format printed above for direct use")