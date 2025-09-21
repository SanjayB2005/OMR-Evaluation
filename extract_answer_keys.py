import pandas as pd
import re

def extract_answers(df, set_name):
    """Extract answers from the Excel file"""
    answers = {}
    
    for col in df.columns:
        for val in df[col].dropna():
            val_str = str(val).strip()
            if '-' in val_str:
                # Extract question number and answer
                parts = val_str.split('-')
                if len(parts) == 2:
                    q_num = parts[0].strip().replace('.', '')
                    answer = parts[1].strip().upper()
                    
                    try:
                        q_number = int(q_num)
                        if 1 <= q_number <= 100:
                            answers[q_number] = answer
                    except ValueError:
                        continue
    
    return answers

# Read both answer keys
df_a = pd.read_excel('AnswerKey/Set A.xlsx')
df_b = pd.read_excel('AnswerKey/Set B.xlsx')

# Extract answers
answers_a = extract_answers(df_a, "Set A")
answers_b = extract_answers(df_b, "Set B")

print("SET A ANSWERS:")
for i in range(1, 101):
    if i in answers_a:
        print(f"Q{i}: {answers_a[i]}")

print("\n" + "="*50 + "\n")

print("SET B ANSWERS:")
for i in range(1, 101):
    if i in answers_b:
        print(f"Q{i}: {answers_b[i]}")

print(f"\nSet A has {len(answers_a)} questions")
print(f"Set B has {len(answers_b)} questions")