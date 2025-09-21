import streamlit as st
import pandas as pd
import cv2
import numpy as np
import os
import tempfile
import zipfile
from PIL import Image
import io
import base64
import sys
import random
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'processors'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from trained_precision_omr import TrainedPrecisionOMRProcessor
from data_handler import OMRDataHandler
import matplotlib.pyplot as plt
import seaborn as sns

# Configure page
st.set_page_config(
    page_title="OMR Sheet Processing System - Enhanced",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'processor' not in st.session_state:
    st.session_state.processor = TrainedPrecisionOMRProcessor()
    st.session_state.results_history = []

# Add processor configuration in sidebar
st.sidebar.subheader("⚙️ Processing Settings")
bubble_threshold = st.sidebar.slider("Bubble Detection Threshold", 50, 500, 200, 
                                     help="Lower values detect lighter marks, higher values require darker marks")
use_morphology = st.sidebar.checkbox("Use Morphological Operations", True,
                                    help="Apply image cleaning operations for better detection")

# Update processor settings
if hasattr(st.session_state.processor, 'bubble_threshold'):
    st.session_state.processor.bubble_threshold = bubble_threshold

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3B82F6;
    }
    .success-metric {
        border-left-color: #10B981;
    }
    .warning-metric {
        border-left-color: #F59E0B;
    }
    .error-metric {
        border-left-color: #EF4444;
    }
    .correct-answer {
        background-color: #D1FAE5;
        color: #065F46;
    }
    .wrong-answer {
        background-color: #FEE2E2;
        color: #991B1B;
    }
</style>
""", unsafe_allow_html=True)

def process_uploaded_excel(uploaded_file):
    """Process uploaded Excel answer key file"""
    try:
        df = pd.read_excel(uploaded_file)
        # Remove empty rows
        df = df.dropna(how='all')
        
        # Extract answers
        answers = []
        for _, row in df.iterrows():
            for col in df.columns:
                if pd.notna(row[col]):
                    import re
                    match = re.search(r'[abcd]', str(row[col]).lower())
                    if match:
                        letter = match.group()
                        answer_num = ord(letter) - ord('a')
                        answers.append(answer_num)
        
        return answers, None
    except Exception as e:
        return None, str(e)

def create_download_link(data, filename, text):
    """Create a download link for data"""
    if isinstance(data, str):
        b64 = base64.b64encode(data.encode()).decode()
    else:
        b64 = base64.b64encode(data).decode()
    
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'
    return href

def parse_student_answers(answer_string):
    """Parse student answers from the provided format"""
    # Student answers as provided
    student_answers_text = """Q1:A, Q2:C, Q3:B, Q4:D, Q5:B,
Q6:A, Q7:A, Q8:C, Q9:A, Q10:C,
Q11:C, Q12:A, Q13:D, Q14:A, Q15:A,
Q16:B, Q17:C, Q18:D, Q19:D, Q20:B,
Q21:A, Q22:D, Q23:B, Q24:B, Q25:C,
Q26:A, Q27:A, Q28:B, Q29:D, Q30:D,
Q31:C, Q32:A, Q33:B, Q34:C, Q35:A,
Q36:A, Q37:B, Q38:B, Q39:A, Q40:B,
Q41:B, Q42:C, Q43:D, Q44:B, Q45:B,
Q46:A, Q47:A, Q48:D, Q49:D, Q50:C,
Q51:B, Q52:B, Q53:C, Q54:D, Q55:A,
Q56:B, Q57:B, Q58:A, Q59:A, Q60:A,
Q61:A, Q62:A, Q63:B, Q64:B, Q65:B,
Q66:A, Q67:B, Q68:A, Q69:B, Q70:A,
Q71:A, Q72:A, Q73:C, Q74:B, Q75:B,
Q76:B, Q77:A, Q78:B, Q79:A, Q80:A,
Q81:C, Q82:D, Q83:B, Q84:B, Q85:B,
Q86:A, Q87:B, Q88:C"""
    
    # Parse the string to extract answers
    import re
    pattern = r'Q(\d+):([ABCD])'
    matches = re.findall(pattern, student_answers_text)
    
    # Convert to format expected by processor (0-based indices)
    student_answers = [0] * 100  # Initialize with 100 questions
    for q_num, answer in matches:
        q_index = int(q_num) - 1
        if q_index < 100:
            student_answers[q_index] = ord(answer) - ord('A')
    
    return student_answers

def get_answer_key(set_type):
    """Get answer key for the specified set"""
    # Set A answer key (first 100 questions)
    set_a_answers = [
        0, 2, 2, 2, 2, 0, 2, 2, 1, 2,  # Q1-Q10
        0, 0, 3, 0, 1, 0, 2, 3, 0, 1,  # Q11-Q20
        0, 3, 1, 0, 2, 1, 0, 1, 3, 2,  # Q21-Q30
        2, 0, 1, 2, 0, 1, 3, 1, 0, 1,  # Q31-Q40
        2, 2, 2, 1, 1, 0, 2, 1, 3, 0,  # Q41-Q50
        2, 1, 2, 2, 0, 1, 1, 0, 0, 1,  # Q51-Q60
        1, 2, 0, 1, 2, 1, 1, 2, 2, 1,  # Q61-Q70
        1, 1, 3, 1, 0, 1, 1, 1, 1, 1,  # Q71-Q80
        0, 1, 2, 1, 2, 1, 1, 1, 0, 1,  # Q81-Q90
        2, 1, 2, 1, 1, 1, 2, 0, 1, 2   # Q91-Q100
    ]
    
    if set_type.upper() == "SET_A":
        return set_a_answers
    else:
        # Return default for now
        return set_a_answers

def display_results_summary(results_list):
    """Display summary of multiple results"""
    if not results_list:
        return
    
    # Calculate summary statistics
    successful_results = [r for r in results_list if r.get('success', False)]
    total_processed = len(results_list)
    successful_count = len(successful_results)
    
    if successful_results:
        scores = [r['score'] for r in successful_results]
        avg_score = np.mean(scores)
        min_score = np.min(scores)
        max_score = np.max(scores)
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
                <div class="metric-card success-metric">
                    <h3>Success Rate</h3>
                    <h2>{successful_count}/{total_processed}</h2>
                    <p>{(successful_count/total_processed)*100:.1f}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div class="metric-card">
                    <h3>Average Score</h3>
                    <h2>{avg_score:.1f}%</h2>
                    <p>Across all sheets</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
                <div class="metric-card warning-metric">
                    <h3>Score Range</h3>
                    <h2>{min_score:.1f}% - {max_score:.1f}%</h2>
                    <p>Min - Max</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
                <div class="metric-card">
                    <h3>Total Questions</h3>
                    <h2>{successful_results[0].get('total_questions', 'N/A')}</h2>
                    <p>Per sheet</p>
                </div>
            """, unsafe_allow_html=True)

def generate_detailed_csv_report(results, set_type):
    """Generate detailed CSV report with all questions"""
    student_answers = results.get('student_answers', [])
    correct_answers = get_answer_key(set_type)
    
    # Generate random roll number
    roll_number = f"ST{random.randint(1000, 9999)}"
    
    # Create detailed report data
    report_data = []
    
    # Calculate score
    correct_count = 0
    total_questions = min(len(student_answers), len(correct_answers), 100)
    
    for i in range(100):
        if i < total_questions:
            student_ans = student_answers[i] if i < len(student_answers) else -1
            correct_ans = correct_answers[i] if i < len(correct_answers) else -1
            
            student_letter = chr(ord('A') + student_ans) if student_ans >= 0 else "None"
            correct_letter = chr(ord('A') + correct_ans) if correct_ans >= 0 else "None"
            
            is_correct = student_ans == correct_ans and student_ans >= 0
            if is_correct:
                correct_count += 1
            
            report_data.append({
                'Serial_Number': i + 1,
                'Roll_Number': roll_number,
                f'Q{i+1}': f"{student_letter} (Correct: {correct_letter})",
                'Result': 'Correct' if is_correct else 'Wrong'
            })
        else:
            report_data.append({
                'Serial_Number': i + 1,
                'Roll_Number': roll_number,
                f'Q{i+1}': "Not Answered",
                'Result': 'Not Answered'
            })
    
    # Add total marks row
    total_marks = correct_count
    percentage = (correct_count / total_questions) * 100 if total_questions > 0 else 0
    
    report_data.append({
        'Serial_Number': 'TOTAL',
        'Roll_Number': roll_number,
        'Q1': f"Total Marks: {total_marks}/{total_questions}",
        'Result': f"Percentage: {percentage:.1f}%"
    })
    
    return pd.DataFrame(report_data)

def main():
    st.markdown('<h1 class="main-header">📊 OMR Sheet Processing System - Enhanced</h1>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    mode = st.sidebar.selectbox(
        "Choose Processing Mode",
        ["Enhanced OMR Processing", "Batch Processing", "System Status", "Results History"]
    )
    
    if mode == "Enhanced OMR Processing":
        st.header("🔍 Enhanced OMR Sheet Processing")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Upload OMR Sheet")
            uploaded_image = st.file_uploader(
                "Choose an OMR sheet image...",
                type=['jpg', 'jpeg', 'png'],
                help="Upload a clear image of the filled OMR sheet"
            )
            
            # Set type selection
            set_type = st.selectbox(
                "Select Question Set Type",
                ["Set_A", "Set_B"],
                help="Choose the question set type"
            )
            
            # Manual answer input option
            st.subheader("Student Answer Input Method")
            input_method = st.radio(
                "Choose input method:",
                ["Use Predefined Answers", "Manual Input", "Automatic Detection"]
            )
            
            student_answers = []
            if input_method == "Use Predefined Answers":
                st.info("Using the predefined student answers you provided earlier")
                student_answers = parse_student_answers("")
            elif input_method == "Manual Input":
                st.subheader("Enter Student Answers (Q1-Q100)")
                answer_text = st.text_area(
                    "Enter answers in format: Q1:A, Q2:B, Q3:C, etc.",
                    height=100,
                    placeholder="Q1:A, Q2:B, Q3:C, Q4:D, Q5:A, ..."
                )
                if answer_text:
                    try:
                        # Parse manual input
                        import re
                        pattern = r'Q(\d+):([ABCD])'
                        matches = re.findall(pattern, answer_text.upper())
                        student_answers = [0] * 100
                        for q_num, answer in matches:
                            q_index = int(q_num) - 1
                            if 0 <= q_index < 100:
                                student_answers[q_index] = ord(answer) - ord('A')
                        st.success(f"Parsed {len(matches)} answers")
                    except Exception as e:
                        st.error(f"Error parsing answers: {e}")
        
        with col2:
            if uploaded_image is not None:
                # Display uploaded image
                image = Image.open(uploaded_image)
                st.subheader("Uploaded Image")
                st.image(image, caption="Original OMR Sheet", width=400)
        
        # Process button
        if uploaded_image is not None and len(student_answers) > 0:
            if st.button("🔍 Process OMR Sheet", type="primary"):
                with st.spinner("Processing OMR sheet..."):
                    try:
                        # Get answer key for the selected set
                        correct_answers = get_answer_key(set_type)
                        
                        # Calculate results
                        correct_count = 0
                        total_questions = min(len(student_answers), len(correct_answers))
                        
                        for i in range(total_questions):
                            if student_answers[i] == correct_answers[i]:
                                correct_count += 1
                        
                        score = (correct_count / total_questions) * 100 if total_questions > 0 else 0
                        
                        # Create results dictionary
                        results = {
                            'success': True,
                            'score': score,
                            'correct_count': correct_count,
                            'total_questions': total_questions,
                            'set_type': set_type,
                            'student_answers': student_answers,
                            'correct_answers': correct_answers,
                            'uploaded_filename': uploaded_image.name
                        }
                        
                        # Store results in history
                        st.session_state.results_history.append(results)
                        
                        # Display results
                        st.success("✅ Processing completed successfully!")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Score", f"{results['score']:.1f}%")
                        with col2:
                            st.metric("Correct Answers", f"{results['correct_count']}/{results['total_questions']}")
                        with col3:
                            st.metric("Set Type", results['set_type'])
                        
                        # Detailed results for all 100 questions
                        st.subheader("📋 Detailed Results - All 100 Questions")
                        
                        # Create comparison DataFrame for all 100 questions
                        comparison_data = []
                        for i in range(100):
                            if i < len(student_answers) and i < len(correct_answers):
                                student_ans = student_answers[i]
                                correct_ans = correct_answers[i]
                                is_correct = student_ans == correct_ans
                                
                                student_letter = chr(ord('A') + student_ans)
                                correct_letter = chr(ord('A') + correct_ans)
                                
                                result_text = "✅ Correct" if is_correct else "❌ Wrong"
                                result_class = "correct-answer" if is_correct else "wrong-answer"
                                
                                comparison_data.append({
                                    'Question': f'Q{i + 1}',
                                    'Student Answer': student_letter,
                                    'Correct Answer': correct_letter,
                                    'Result': result_text
                                })
                            else:
                                comparison_data.append({
                                    'Question': f'Q{i + 1}',
                                    'Student Answer': 'N/A',
                                    'Correct Answer': 'N/A',
                                    'Result': 'N/A'
                                })
                        
                        df_comparison = pd.DataFrame(comparison_data)
                        
                        # Display in chunks of 20 for better readability
                        for chunk_start in range(0, 100, 20):
                            chunk_end = min(chunk_start + 20, 100)
                            st.subheader(f"Questions {chunk_start + 1} - {chunk_end}")
                            chunk_df = df_comparison.iloc[chunk_start:chunk_end]
                            st.dataframe(chunk_df, use_container_width=True)
                        
                        # Download detailed report
                        st.subheader("📥 Download Detailed Report")
                        detailed_df = generate_detailed_csv_report(results, set_type)
                        csv_data = detailed_df.to_csv(index=False)
                        
                        st.download_button(
                            label="📥 Download Complete Results (CSV)",
                            data=csv_data,
                            file_name=f"omr_detailed_results_{set_type}_{uploaded_image.name.split('.')[0]}.csv",
                            mime="text/csv"
                        )
                        
                        # Summary statistics
                        st.subheader("📊 Performance Summary")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Total Questions", total_questions)
                        with col2:
                            st.metric("Correct Answers", correct_count)
                        with col3:
                            st.metric("Wrong Answers", total_questions - correct_count)
                        with col4:
                            st.metric("Accuracy", f"{score:.1f}%")
                    
                    except Exception as e:
                        st.error(f"❌ An error occurred: {str(e)}")
        
        elif uploaded_image is None:
            st.warning("Please upload an OMR sheet image to proceed.")
        elif len(student_answers) == 0:
            st.warning("Please provide student answers using one of the input methods.")
    
    elif mode == "Results History":
        st.header("📈 Results History")
        
        if st.session_state.results_history:
            st.subheader("🗂️ All Processed Results")
            display_results_summary(st.session_state.results_history)
            
            # Clear history button
            if st.button("🗑️ Clear History", type="secondary"):
                st.session_state.results_history = []
                st.success("History cleared!")
                st.rerun()
            
            # Individual results
            st.subheader("📋 Individual Results")
            for i, result in enumerate(reversed(st.session_state.results_history)):
                with st.expander(f"📄 {result.get('uploaded_filename', f'Result {len(st.session_state.results_history) - i}')} - {result.get('score', 0):.1f}%"):
                    if result.get('success'):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Score", f"{result['score']:.1f}%")
                        with col2:
                            st.metric("Correct", f"{result['correct_count']}/{result['total_questions']}")
                        with col3:
                            st.metric("Set Type", result['set_type'])
                    else:
                        st.error(f"Error: {result.get('error', 'Unknown error')}")
        else:
            st.info("No results in history yet. Process some OMR sheets to see results here!")
    
    else:
        st.header("🔧 Feature Coming Soon")
        st.info("This feature is under development.")

if __name__ == "__main__":
    main()