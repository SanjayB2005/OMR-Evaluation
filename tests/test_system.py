import os
import pandas as pd
from enhanced_omr import EnhancedOMRProcessor
from data_handler import OMRDataHandler
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

class OMRSystemTester:
    """Comprehensive testing system for OMR processing"""
    
    def __init__(self):
        self.processor = EnhancedOMRProcessor()
        self.data_handler = OMRDataHandler()
        self.test_results = []
        
    def run_comprehensive_test(self):
        """Run comprehensive test on all available data"""
        print("🚀 Starting Comprehensive OMR System Test")
        print("=" * 60)
        
        # Load data
        print("📂 Loading data...")
        self.data_handler.load_answer_keys()
        self.data_handler.load_datasets()
        
        # Display data summary
        print(f"📊 Data Summary:")
        summary = self.data_handler.get_summary()
        for key, value in summary.items():
            print(f"   {key}: {value}")
        print()
        
        # Test each dataset
        overall_results = {
            'total_images': 0,
            'successful_processing': 0,
            'failed_processing': 0,
            'scores': [],
            'set_results': {}
        }
        
        for set_name, image_paths in self.data_handler.datasets.items():
            print(f"🔍 Testing {set_name} ({len(image_paths)} images)")
            set_results = self.test_dataset(set_name, image_paths)
            overall_results['set_results'][set_name] = set_results
            
            # Update overall stats
            overall_results['total_images'] += set_results['total_images']
            overall_results['successful_processing'] += set_results['successful_count']
            overall_results['failed_processing'] += set_results['error_count']
            overall_results['scores'].extend(set_results['scores'])
            
            print(f"   ✅ Success: {set_results['successful_count']}/{set_results['total_images']}")
            print(f"   📊 Avg Score: {set_results['average_score']:.1f}%")
            print(f"   📈 Score Range: {set_results['min_score']:.1f}% - {set_results['max_score']:.1f}%")
            print()
        
        # Generate comprehensive report
        self.generate_test_report(overall_results)
        
        return overall_results
    
    def test_dataset(self, set_name, image_paths):
        """Test processing on a specific dataset"""
        results = {
            'set_name': set_name,
            'total_images': len(image_paths),
            'successful_count': 0,
            'error_count': 0,
            'scores': [],
            'detailed_results': []
        }
        
        for i, img_path in enumerate(image_paths):
            print(f"   Processing {os.path.basename(img_path)}... ", end="")
            
            try:
                # Process the OMR sheet
                omr_results = self.processor.process_omr_sheet(img_path, set_name)
                
                if omr_results.get('success'):
                    score = omr_results['score']
                    results['scores'].append(score)
                    results['successful_count'] += 1
                    
                    detailed_result = {
                        'image_path': img_path,
                        'image_name': os.path.basename(img_path),
                        'score': score,
                        'correct_count': omr_results['correct_count'],
                        'total_questions': omr_results['total_questions'],
                        'set_type': omr_results['set_type'],
                        'status': 'success'
                    }
                    results['detailed_results'].append(detailed_result)
                    print(f"✅ {score:.1f}%")
                    
                    # Save visualization
                    viz_img = self.processor.visualize_results(omr_results)
                    if viz_img is not None:
                        output_dir = "test_results"
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)
                        
                        output_path = os.path.join(output_dir, f"{set_name}_{os.path.basename(img_path)}_result.jpg")
                        import cv2
                        cv2.imwrite(output_path, viz_img)
                
                else:
                    results['error_count'] += 1
                    error_msg = omr_results.get('error', 'Unknown error')
                    
                    detailed_result = {
                        'image_path': img_path,
                        'image_name': os.path.basename(img_path),
                        'score': 0,
                        'error': error_msg,
                        'status': 'failed'
                    }
                    results['detailed_results'].append(detailed_result)
                    print(f"❌ {error_msg}")
                    
            except Exception as e:
                results['error_count'] += 1
                detailed_result = {
                    'image_path': img_path,
                    'image_name': os.path.basename(img_path),
                    'score': 0,
                    'error': str(e),
                    'status': 'exception'
                }
                results['detailed_results'].append(detailed_result)
                print(f"💥 Exception: {str(e)}")
        
        # Calculate statistics
        if results['scores']:
            import numpy as np
            results['average_score'] = np.mean(results['scores'])
            results['score_std'] = np.std(results['scores'])
            results['min_score'] = np.min(results['scores'])
            results['max_score'] = np.max(results['scores'])
            results['median_score'] = np.median(results['scores'])
        else:
            results['average_score'] = 0
            results['score_std'] = 0
            results['min_score'] = 0
            results['max_score'] = 0
            results['median_score'] = 0
        
        return results
    
    def generate_test_report(self, overall_results):
        """Generate comprehensive test report"""
        print("📋 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        # Overall statistics
        total_images = overall_results['total_images']
        successful = overall_results['successful_processing']
        failed = overall_results['failed_processing']
        success_rate = (successful / total_images * 100) if total_images > 0 else 0
        
        print(f"📊 Overall Performance:")
        print(f"   Total Images Processed: {total_images}")
        print(f"   Successful Processing: {successful}")
        print(f"   Failed Processing: {failed}")
        print(f"   Success Rate: {success_rate:.1f}%")
        print()
        
        if overall_results['scores']:
            import numpy as np
            scores = overall_results['scores']
            print(f"📈 Score Statistics:")
            print(f"   Average Score: {np.mean(scores):.1f}%")
            print(f"   Median Score: {np.median(scores):.1f}%")
            print(f"   Standard Deviation: {np.std(scores):.1f}%")
            print(f"   Score Range: {np.min(scores):.1f}% - {np.max(scores):.1f}%")
            print()
        
        # Per-set breakdown
        print(f"📂 Per-Set Performance:")
        for set_name, set_results in overall_results['set_results'].items():
            print(f"   {set_name}:")
            print(f"      Success Rate: {set_results['successful_count']}/{set_results['total_images']} ({set_results['successful_count']/set_results['total_images']*100:.1f}%)")
            print(f"      Average Score: {set_results['average_score']:.1f}%")
            print(f"      Score Range: {set_results['min_score']:.1f}% - {set_results['max_score']:.1f}%")
            print()
        
        # Generate CSV report
        self.save_detailed_results_csv(overall_results)
        
        # Generate visualizations
        self.create_performance_charts(overall_results)
        
        print(f"💾 Detailed results saved to 'test_results_detailed.csv'")
        print(f"📊 Performance charts saved to 'performance_charts.png'")
        print()
        
        # Recommendations
        self.generate_recommendations(overall_results)
    
    def save_detailed_results_csv(self, overall_results):
        """Save detailed results to CSV file"""
        csv_data = []
        
        for set_name, set_results in overall_results['set_results'].items():
            for result in set_results['detailed_results']:
                csv_row = {
                    'Set_Name': set_name,
                    'Image_Name': result['image_name'],
                    'Status': result['status'],
                    'Score_Percentage': result['score'],
                    'Error_Message': result.get('error', ''),
                    'Correct_Count': result.get('correct_count', 0),
                    'Total_Questions': result.get('total_questions', 0)
                }
                csv_data.append(csv_row)
        
        df = pd.DataFrame(csv_data)
        df.to_csv('test_results_detailed.csv', index=False)
    
    def create_performance_charts(self, overall_results):
        """Create performance visualization charts"""
        if not overall_results['scores']:
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('OMR System Performance Analysis', fontsize=16, fontweight='bold')
        
        # 1. Score distribution histogram
        ax1.hist(overall_results['scores'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        ax1.set_xlabel('Score (%)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Score Distribution')
        ax1.grid(True, alpha=0.3)
        
        # 2. Per-set average scores
        set_names = list(overall_results['set_results'].keys())
        avg_scores = [overall_results['set_results'][name]['average_score'] for name in set_names]
        success_rates = [overall_results['set_results'][name]['successful_count']/overall_results['set_results'][name]['total_images']*100 for name in set_names]
        
        x_pos = range(len(set_names))
        ax2.bar(x_pos, avg_scores, alpha=0.7, color='lightgreen', label='Avg Score')
        ax2.set_xlabel('Set Name')
        ax2.set_ylabel('Average Score (%)')
        ax2.set_title('Average Scores by Set')
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(set_names)
        ax2.grid(True, alpha=0.3)
        
        # 3. Success rates by set
        ax3.bar(x_pos, success_rates, alpha=0.7, color='orange', label='Success Rate')
        ax3.set_xlabel('Set Name')
        ax3.set_ylabel('Success Rate (%)')
        ax3.set_title('Processing Success Rates by Set')
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(set_names)
        ax3.grid(True, alpha=0.3)
        
        # 4. Box plot of scores by set
        set_scores = []
        set_labels = []
        for set_name, set_results in overall_results['set_results'].items():
            if set_results['scores']:
                set_scores.append(set_results['scores'])
                set_labels.append(set_name)
        
        if set_scores:
            ax4.boxplot(set_scores, labels=set_labels)
            ax4.set_xlabel('Set Name')
            ax4.set_ylabel('Score (%)')
            ax4.set_title('Score Distribution by Set')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('performance_charts.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_recommendations(self, overall_results):
        """Generate recommendations based on test results"""
        print("💡 RECOMMENDATIONS")
        print("=" * 60)
        
        total_images = overall_results['total_images']
        successful = overall_results['successful_processing']
        success_rate = (successful / total_images * 100) if total_images > 0 else 0
        
        if success_rate >= 90:
            print("✅ Excellent performance! The system is working very well.")
        elif success_rate >= 75:
            print("⚠️  Good performance, but there's room for improvement.")
        else:
            print("🔧 Performance needs improvement. Consider the following:")
        
        if overall_results['scores']:
            import numpy as np
            avg_score = np.mean(overall_results['scores'])
            
            if avg_score < 50:
                print("   • The average score is quite low. This might indicate:")
                print("     - Issues with OMR sheet template alignment")
                print("     - Incorrect answer key mapping")
                print("     - Need for better image preprocessing")
            
            score_std = np.std(overall_results['scores'])
            if score_std > 25:
                print("   • High score variation detected. Consider:")
                print("     - Standardizing image quality")
                print("     - Improving bubble detection algorithms")
                print("     - Checking for consistent OMR sheet formats")
        
        # Per-set recommendations
        for set_name, set_results in overall_results['set_results'].items():
            set_success_rate = set_results['successful_count'] / set_results['total_images'] * 100
            if set_success_rate < 80:
                print(f"   • {set_name} has low success rate ({set_success_rate:.1f}%):")
                print(f"     - Review answer key format for {set_name}")
                print(f"     - Check image quality for {set_name} dataset")
        
        print()
        print("🔄 Next Steps:")
        print("   1. Review failed cases in 'test_results_detailed.csv'")
        print("   2. Analyze visualization results in 'test_results/' folder")
        print("   3. Adjust system parameters based on findings")
        print("   4. Re-run tests after improvements")

# Main testing script
if __name__ == "__main__":
    print("🧪 OMR System Comprehensive Testing")
    print("Starting automated testing suite...")
    print()
    
    tester = OMRSystemTester()
    
    # Run comprehensive test
    start_time = datetime.now()
    results = tester.run_comprehensive_test()
    end_time = datetime.now()
    
    print(f"⏱️  Total testing time: {end_time - start_time}")
    print("🎉 Testing completed successfully!")
    
    # Launch web app option
    print("\n" + "=" * 60)
    print("🌐 Ready to launch web interface!")
    print("Run the following command to start the web app:")
    print("   streamlit run omr_web_app.py")
    print("=" * 60)