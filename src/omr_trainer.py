import cv2
import numpy as np
import os
import json
from typing import Dict, List, Tuple, Optional
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from enhanced_omr import EnhancedOMRProcessor
from data_handler import OMRDataHandler
import matplotlib.pyplot as plt

class OMRTrainer:
    """Training module for OMR system optimization"""
    
    def __init__(self):
        self.processor = EnhancedOMRProcessor()
        self.data_handler = OMRDataHandler()
        self.training_stats = {}
        self.optimal_params = {}
        
    def extract_bubble_features(self, bubble_image: np.ndarray) -> Dict:
        """Extract features from a bubble image for training"""
        features = {}
        
        # Basic statistics
        features['mean_intensity'] = np.mean(bubble_image)
        features['std_intensity'] = np.std(bubble_image)
        features['total_pixels'] = bubble_image.size
        features['non_zero_pixels'] = cv2.countNonZero(bubble_image)
        features['fill_ratio'] = features['non_zero_pixels'] / features['total_pixels']
        
        # Shape analysis
        contours, _ = cv2.findContours(bubble_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            features['contour_area'] = cv2.contourArea(largest_contour)
            features['contour_perimeter'] = cv2.arcLength(largest_contour, True)
            
            # Compactness (4π*area/perimeter²)
            if features['contour_perimeter'] > 0:
                features['compactness'] = 4 * np.pi * features['contour_area'] / (features['contour_perimeter'] ** 2)
            else:
                features['compactness'] = 0
        else:
            features['contour_area'] = 0
            features['contour_perimeter'] = 0
            features['compactness'] = 0
        
        # Edge density
        edges = cv2.Canny(bubble_image, 50, 150)
        features['edge_density'] = cv2.countNonZero(edges) / bubble_image.size
        
        return features
    
    def analyze_threshold_sensitivity(self, image_paths: List[str]) -> Dict:
        """Analyze optimal thresholding parameters"""
        threshold_results = {}
        thresholds = range(120, 220, 10)
        
        for threshold in thresholds:
            scores = []
            for img_path in image_paths[:5]:  # Test on subset
                try:
                    img = cv2.imread(img_path)
                    if img is None:
                        continue
                        
                    # Modify processor threshold temporarily
                    original_process = self.processor.extract_bubble_responses
                    
                    def modified_extract(img_warp_colored):
                        img_warp_gray = cv2.cvtColor(img_warp_colored, cv2.COLOR_BGR2GRAY)
                        img_thresh = cv2.threshold(img_warp_gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]
                        
                        boxes = self.processor.split_boxes_dynamic(img_thresh, self.processor.questions, self.processor.choices)
                        
                        my_pixel_val = np.zeros((self.processor.questions, self.processor.choices))
                        for i, box in enumerate(boxes):
                            row = i // self.processor.choices
                            col = i % self.processor.choices
                            if row < self.processor.questions:
                                total_pixels = cv2.countNonZero(box)
                                my_pixel_val[row][col] = total_pixels
                        
                        my_index = []
                        for x in range(self.processor.questions):
                            arr = my_pixel_val[x]
                            if np.max(arr) > 0:
                                my_index_val = np.where(arr == np.amax(arr))
                                my_index.append(my_index_val[0][0])
                            else:
                                my_index.append(-1)
                        
                        return my_index, my_pixel_val
                    
                    self.processor.extract_bubble_responses = modified_extract
                    
                    # Process with modified threshold
                    results = self.processor.process_omr_sheet(img_path)
                    if results.get("success"):
                        scores.append(results["score"])
                    
                    # Restore original method
                    self.processor.extract_bubble_responses = original_process
                    
                except Exception as e:
                    print(f"Error testing threshold {threshold} on {img_path}: {e}")
                    continue
            
            if scores:
                threshold_results[threshold] = {
                    'mean_score': np.mean(scores),
                    'std_score': np.std(scores),
                    'scores': scores
                }
        
        # Find optimal threshold
        best_threshold = max(threshold_results.keys(), 
                           key=lambda t: threshold_results[t]['mean_score'])
        
        return {
            'results': threshold_results,
            'optimal_threshold': best_threshold,
            'optimal_score': threshold_results[best_threshold]['mean_score']
        }
    
    def train_bubble_classifier(self, image_paths: List[str]) -> Dict:
        """Train a classifier to distinguish filled vs unfilled bubbles"""
        features_list = []
        labels = []
        
        for img_path in image_paths[:10]:  # Use subset for training
            try:
                set_type = self.data_handler.detect_set_from_image(img_path)
                correct_answers = self.data_handler.get_answer_key_for_set(set_type)
                
                if not correct_answers:
                    continue
                
                # Process image to get bubble boxes
                img = cv2.imread(img_path)
                if img is None:
                    continue
                
                img_resized, _, img_canny = self.processor.preprocess_image(img)
                biggest_points, _ = self.processor.find_omr_contours(img_canny)
                
                if biggest_points is None:
                    continue
                
                img_warp_colored = self.processor.warp_omr_sheet(img_resized, biggest_points)
                img_warp_gray = cv2.cvtColor(img_warp_colored, cv2.COLOR_BGR2GRAY)
                img_thresh = cv2.threshold(img_warp_gray, 170, 255, cv2.THRESH_BINARY_INV)[1]
                
                boxes = self.processor.split_boxes_dynamic(img_thresh, 
                                                         self.processor.questions, 
                                                         self.processor.choices)
                
                # Extract features for each bubble
                for i, box in enumerate(boxes):
                    row = i // self.processor.choices
                    col = i % self.processor.choices
                    
                    if row < len(correct_answers):
                        features = self.extract_bubble_features(box)
                        features_list.append(list(features.values()))
                        
                        # Label: 1 if this is the correct answer, 0 otherwise
                        is_correct_answer = (col == correct_answers[row])
                        labels.append(1 if is_correct_answer else 0)
                
            except Exception as e:
                print(f"Error processing {img_path} for training: {e}")
                continue
        
        if not features_list:
            return {"error": "No training data extracted"}
        
        # Train classifier
        X = np.array(features_list)
        y = np.array(labels)
        
        # Normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Simple clustering approach
        kmeans = KMeans(n_clusters=2, random_state=42)
        clusters = kmeans.fit_predict(X_scaled)
        
        # Determine which cluster represents filled bubbles
        filled_cluster = 0 if np.mean(y[clusters == 0]) > np.mean(y[clusters == 1]) else 1
        
        return {
            'scaler': scaler,
            'kmeans': kmeans,
            'filled_cluster': filled_cluster,
            'feature_names': list(self.extract_bubble_features(np.zeros((10, 10), dtype=np.uint8)).keys()),
            'training_accuracy': np.mean((clusters == filled_cluster) == y),
            'n_samples': len(X)
        }
    
    def evaluate_system_performance(self) -> Dict:
        """Evaluate system performance on all available data"""
        self.data_handler.load_answer_keys()
        self.data_handler.load_datasets()
        
        performance_stats = {
            'set_performance': {},
            'overall_performance': {
                'total_images': 0,
                'successful_processing': 0,
                'average_score': 0,
                'score_distribution': []
            }
        }
        
        all_scores = []
        total_processed = 0
        
        for set_name, image_paths in self.data_handler.datasets.items():
            set_scores = []
            set_errors = []
            
            print(f"Evaluating {set_name} ({len(image_paths)} images)...")
            
            for img_path in image_paths:
                try:
                    results = self.processor.process_omr_sheet(img_path, set_name)
                    
                    if results.get("success"):
                        score = results["score"]
                        set_scores.append(score)
                        all_scores.append(score)
                        total_processed += 1
                    else:
                        set_errors.append(results.get("error", "Unknown error"))
                        
                except Exception as e:
                    set_errors.append(str(e))
            
            performance_stats['set_performance'][set_name] = {
                'images_count': len(image_paths),
                'successful_count': len(set_scores),
                'error_count': len(set_errors),
                'average_score': np.mean(set_scores) if set_scores else 0,
                'score_std': np.std(set_scores) if set_scores else 0,
                'min_score': np.min(set_scores) if set_scores else 0,
                'max_score': np.max(set_scores) if set_scores else 0,
                'errors': set_errors[:5]  # Keep first 5 errors
            }
        
        performance_stats['overall_performance'] = {
            'total_images': sum(len(paths) for paths in self.data_handler.datasets.values()),
            'successful_processing': total_processed,
            'success_rate': total_processed / sum(len(paths) for paths in self.data_handler.datasets.values()) * 100,
            'average_score': np.mean(all_scores) if all_scores else 0,
            'score_std': np.std(all_scores) if all_scores else 0,
            'score_distribution': {
                'min': np.min(all_scores) if all_scores else 0,
                'max': np.max(all_scores) if all_scores else 0,
                'median': np.median(all_scores) if all_scores else 0,
                'q25': np.percentile(all_scores, 25) if all_scores else 0,
                'q75': np.percentile(all_scores, 75) if all_scores else 0
            }
        }
        
        return performance_stats
    
    def save_training_results(self, results: Dict, filename: str = "training_results.json"):
        """Save training results to file"""
        # Convert numpy types to native Python types for JSON serialization
        def convert_numpy(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, dict):
                return {key: convert_numpy(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            else:
                return obj
        
        serializable_results = convert_numpy(results)
        
        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        print(f"Training results saved to {filename}")

# Training script
if __name__ == "__main__":
    trainer = OMRTrainer()
    
    print("Starting OMR system training and evaluation...")
    
    # Load data
    trainer.data_handler.load_answer_keys()
    trainer.data_handler.load_datasets()
    
    # Get all image paths
    all_images = []
    for set_name, image_paths in trainer.data_handler.datasets.items():
        all_images.extend(image_paths)
    
    print(f"Total images available: {len(all_images)}")
    
    # 1. Analyze threshold sensitivity
    print("\n1. Analyzing threshold sensitivity...")
    threshold_analysis = trainer.analyze_threshold_sensitivity(all_images)
    print(f"Optimal threshold: {threshold_analysis['optimal_threshold']}")
    print(f"Optimal mean score: {threshold_analysis['optimal_score']:.2f}%")
    
    # 2. Train bubble classifier
    print("\n2. Training bubble classifier...")
    classifier_results = trainer.train_bubble_classifier(all_images)
    if 'error' not in classifier_results:
        print(f"Classifier training accuracy: {classifier_results['training_accuracy']:.3f}")
        print(f"Training samples: {classifier_results['n_samples']}")
    else:
        print(f"Classifier training failed: {classifier_results['error']}")
    
    # 3. Evaluate system performance
    print("\n3. Evaluating system performance...")
    performance = trainer.evaluate_system_performance()
    
    print(f"Overall success rate: {performance['overall_performance']['success_rate']:.1f}%")
    print(f"Average score: {performance['overall_performance']['average_score']:.1f}%")
    
    for set_name, stats in performance['set_performance'].items():
        print(f"{set_name}: {stats['successful_count']}/{stats['images_count']} images, "
              f"avg score: {stats['average_score']:.1f}%")
    
    # Save results
    training_results = {
        'threshold_analysis': threshold_analysis,
        'classifier_results': classifier_results,
        'performance_evaluation': performance,
        'training_timestamp': __import__('datetime').datetime.now().isoformat()
    }
    
    trainer.save_training_results(training_results)
    print("\nTraining complete! Results saved to training_results.json")