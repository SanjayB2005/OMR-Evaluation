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
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'processors'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from trained_precision_omr import TrainedPrecisionOMRProcessor
from data_handler import OMRDataHandler
import matplotlib.pyplot as plt
import seaborn as sns

# Configure page
st.set_page_config(
    page_title="OMR Sheet Processing System",
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
        
        # Score distribution chart
        if len(scores) > 1:
            st.subheader("Score Distribution")
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(scores, bins=min(10, len(scores)), alpha=0.7, color='skyblue', edgecolor='black')
            ax.set_xlabel('Score (%)')
            ax.set_ylabel('Frequency')
            ax.set_title('Distribution of OMR Sheet Scores')
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)

def main():
    st.markdown('<h1 class="main-header">📊 OMR Sheet Processing System</h1>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    mode = st.sidebar.selectbox(
        "Choose Processing Mode",
        ["Single Sheet Processing", "Batch Processing", "System Status", "Results History"]
    )
    
    if mode == "Single Sheet Processing":
        st.header("🔍 Single OMR Sheet Processing")
        
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
                ["Auto-detect", "Set_A", "Set_B", "Custom"],
                help="Choose the question set type or let the system auto-detect"
            )
            
            # Custom answer key option
            custom_answers = None
            if set_type == "Custom":
                st.subheader("Upload Custom Answer Key")
                answer_key_file = st.file_uploader(
                    "Upload Excel answer key file...",
                    type=['xlsx', 'xls'],
                    help="Upload Excel file with answer key in format like '1 - a', '2 - b', etc."
                )
                
                if answer_key_file:
                    custom_answers, error = process_uploaded_excel(answer_key_file)
                    if error:
                        st.error(f"Error processing answer key: {error}")
                    else:
                        st.success(f"Loaded {len(custom_answers)} answers from custom key")
        
        with col2:
            if uploaded_image is not None:
                # Display uploaded image
                image = Image.open(uploaded_image)
                st.subheader("Uploaded Image")
                st.image(image, caption="Original OMR Sheet", width='stretch')
        
        # Process button
        if uploaded_image is not None:
            if st.button("🔍 Process OMR Sheet", type="primary"):
                with st.spinner("Processing OMR sheet..."):
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                        tmp_file.write(uploaded_image.getvalue())
                        tmp_path = tmp_file.name
                    
                    try:
                        # Process the image
                        if set_type == "Custom" and custom_answers:
                            # Temporarily set custom answer key
                            original_keys = st.session_state.processor.answer_keys.copy()
                            st.session_state.processor.answer_keys["Custom"] = custom_answers
                            results = st.session_state.processor.process_omr_sheet(tmp_path, "Custom")
                            st.session_state.processor.answer_keys = original_keys
                        else:
                            detect_set = None if set_type == "Auto-detect" else set_type
                            results = st.session_state.processor.process_omr_sheet(tmp_path, detect_set)
                        
                        if results.get("success"):
                            # Store results in history
                            results['uploaded_filename'] = uploaded_image.name
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
                            
                            # Detailed results
                            st.subheader("📋 Detailed Results")
                            
                            # Create comparison DataFrame
                            comparison_data = []
                            for i in range(min(20, len(results['correct_answers']))):  # Show first 20 questions
                                student_ans = results['student_answers'][i] if i < len(results['student_answers']) else -1
                                correct_ans = results['correct_answers'][i]
                                is_correct = student_ans == correct_ans
                                
                                student_letter = chr(ord('A') + student_ans) if student_ans >= 0 else "None"
                                correct_letter = chr(ord('A') + correct_ans)
                                
                                comparison_data.append({
                                    'Question': i + 1,
                                    'Student Answer': student_letter,
                                    'Correct Answer': correct_letter,
                                    'Result': "✅ Correct" if is_correct else "❌ Wrong"
                                })
                            
                            df_comparison = pd.DataFrame(comparison_data)
                            st.dataframe(df_comparison, width='stretch')
                            
                            if len(results['correct_answers']) > 20:
                                st.info(f"Showing first 20 questions. Total: {len(results['correct_answers'])} questions.")
                            
                            # Visualization
                            if results.get('processed_image') is not None:
                                st.subheader("🎨 Processed Image with Results")
                                viz_img = st.session_state.processor.visualize_results(results)
                                if viz_img is not None:
                                    st.image(viz_img, caption="Processed OMR Sheet with Results", width='stretch')
                        
                        else:
                            st.error(f"❌ Processing failed: {results.get('error', 'Unknown error')}")
                    
                    except Exception as e:
                        st.error(f"❌ An error occurred: {str(e)}")
                    
                    finally:
                        # Clean up temporary file
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
    
    elif mode == "Batch Processing":
        st.header("📚 Batch OMR Sheet Processing")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Upload Multiple OMR Sheets")
            uploaded_files = st.file_uploader(
                "Choose OMR sheet images...",
                type=['jpg', 'jpeg', 'png'],
                accept_multiple_files=True,
                help="Upload multiple OMR sheet images for batch processing"
            )
            
            # Batch settings
            batch_set_type = st.selectbox(
                "Set Type for All Images",
                ["Auto-detect", "Set_A", "Set_B", "Custom"],
                help="Applied to all uploaded images"
            )
            
            if batch_set_type == "Custom":
                batch_answer_key = st.file_uploader(
                    "Upload Answer Key for Batch",
                    type=['xlsx', 'xls'],
                    help="This answer key will be used for all images"
                )
        
        with col2:
            if uploaded_files:
                st.subheader(f"📁 {len(uploaded_files)} Files Selected")
                for i, file in enumerate(uploaded_files[:5]):  # Show first 5
                    st.write(f"{i+1}. {file.name}")
                if len(uploaded_files) > 5:
                    st.write(f"... and {len(uploaded_files) - 5} more files")
        
        # Batch process button
        if uploaded_files and st.button("🔄 Process All Sheets", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            batch_results = []
            custom_batch_answers = None
            
            # Process custom answer key if provided
            if batch_set_type == "Custom" and 'batch_answer_key' in locals() and batch_answer_key:
                custom_batch_answers, error = process_uploaded_excel(batch_answer_key)
                if error:
                    st.error(f"Error processing batch answer key: {error}")
                    st.stop()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {uploaded_file.name}... ({i+1}/{len(uploaded_files)})")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                try:
                    if batch_set_type == "Custom" and custom_batch_answers:
                        original_keys = st.session_state.processor.answer_keys.copy()
                        st.session_state.processor.answer_keys["Custom"] = custom_batch_answers
                        results = st.session_state.processor.process_omr_sheet(tmp_path, "Custom")
                        st.session_state.processor.answer_keys = original_keys
                    else:
                        detect_set = None if batch_set_type == "Auto-detect" else batch_set_type
                        results = st.session_state.processor.process_omr_sheet(tmp_path, detect_set)
                    
                    results['uploaded_filename'] = uploaded_file.name
                    batch_results.append(results)
                    
                except Exception as e:
                    batch_results.append({
                        'uploaded_filename': uploaded_file.name,
                        'success': False,
                        'error': str(e)
                    })
                
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("Batch processing completed!")
            
            # Store batch results in history
            st.session_state.results_history.extend(batch_results)
            
            # Display batch summary
            st.subheader("📊 Batch Processing Summary")
            display_results_summary(batch_results)
            
            # Detailed batch results
            st.subheader("📋 Individual Results")
            for i, result in enumerate(batch_results):
                with st.expander(f"📄 {result['uploaded_filename']} - {'✅ Success' if result.get('success') else '❌ Failed'}"):
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
            
            # Download results as CSV
            if batch_results:
                results_df = []
                for result in batch_results:
                    if result.get('success'):
                        results_df.append({
                            'Filename': result['uploaded_filename'],
                            'Set_Type': result['set_type'],
                            'Score_Percent': result['score'],
                            'Correct_Answers': result['correct_count'],
                            'Total_Questions': result['total_questions'],
                            'Status': 'Success'
                        })
                    else:
                        results_df.append({
                            'Filename': result['uploaded_filename'],
                            'Set_Type': 'N/A',
                            'Score_Percent': 0,
                            'Correct_Answers': 0,
                            'Total_Questions': 0,
                            'Status': f"Failed: {result.get('error', 'Unknown')}"
                        })
                
                df = pd.DataFrame(results_df)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name="omr_batch_results.csv",
                    mime="text/csv"
                )
    
    elif mode == "System Status":
        st.header("⚙️ System Status")
        
        # System information
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Available Answer Keys")
            for set_name, answers in st.session_state.processor.answer_keys.items():
                st.write(f"**{set_name}**: {len(answers)} questions")
        
        with col2:
            st.subheader("🎯 System Configuration")
            st.write(f"**Image Height**: {st.session_state.processor.height_img}px")
            st.write(f"**Image Width**: {st.session_state.processor.width_img}px")
            st.write(f"**Questions**: {st.session_state.processor.questions}")
            st.write(f"**Choices**: {st.session_state.processor.choices}")
        
        # Test with sample data
        st.subheader("🧪 Test System with Sample Data")
        if st.button("Run System Test"):
            with st.spinner("Running system test..."):
                data_handler = OMRDataHandler()
                data_handler.load_datasets()
                
                if data_handler.datasets:
                    # Test with first available image
                    test_set = list(data_handler.datasets.keys())[0]
                    test_image = data_handler.datasets[test_set][0]
                    
                    results = st.session_state.processor.process_omr_sheet(test_image, test_set)
                    
                    if results.get('success'):
                        st.success(f"✅ System test passed! Score: {results['score']:.1f}%")
                    else:
                        st.error(f"❌ System test failed: {results.get('error')}")
                else:
                    st.warning("No sample data found for testing")
    
    elif mode == "Results History":
        st.header("📈 Results History")
        
        if st.session_state.results_history:
            st.subheader("🗂️ All Processed Results")
            display_results_summary(st.session_state.results_history)
            
            # Clear history button
            if st.button("🗑️ Clear History", type="secondary"):
                st.session_state.results_history = []
                st.success("History cleared!")
                st.experimental_rerun()
            
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

if __name__ == "__main__":
    main()