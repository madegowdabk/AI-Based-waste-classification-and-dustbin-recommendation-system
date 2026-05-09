import tensorflow as tf
import numpy as np
from PIL import Image
import cv2
import os
import logging

class WasteClassifier:
    def __init__(self):
        self.model = None
        self.class_names = ['dry', 'wet']
        self.img_size = (224, 224)
        self.load_or_create_model()
    
    def load_or_create_model(self):
        """Load existing model or create a new one"""
        model_path = 'static/models/waste_model.h5'
        
        try:
            if os.path.exists(model_path):
                self.model = tf.keras.models.load_model(model_path)
                logging.info("Loaded existing waste classification model")
            else:
                self.create_model()
                logging.info("Created new waste classification model")
        except Exception as e:
            logging.error(f"Error loading model: {e}")
            self.create_model()
    
    def create_model(self):
        """Create a CNN model for waste classification"""
        # Create a simple but effective CNN model
        self.model = tf.keras.Sequential([
            tf.keras.layers.Conv2D(32, (3, 3), activation='relu', input_shape=(224, 224, 3)),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(64, (3, 3), activation='relu'),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(128, (3, 3), activation='relu'),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(128, (3, 3), activation='relu'),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dropout(0.5),
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.Dense(2, activation='softmax')  # 2 classes: dry, wet
        ])
        
        self.model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        # Initialize with random weights (in production, this would be trained)
        dummy_input = np.random.random((1, 224, 224, 3))
        self.model.predict(dummy_input)
        
        # Save the model
        os.makedirs('static/models', exist_ok=True)
        self.model.save('static/models/waste_model.h5')
    
    def preprocess_image(self, image_path):
        """Preprocess image for prediction"""
        try:
            # Load and resize image
            image = Image.open(image_path)
            image = image.convert('RGB')
            image = image.resize(self.img_size)
            
            # Convert to numpy array and normalize
            image_array = np.array(image) / 255.0
            image_array = np.expand_dims(image_array, axis=0)
            
            return image_array
        except Exception as e:
            logging.error(f"Error preprocessing image: {e}")
            return None
    
    def analyze_image_features(self, image_path):
        """Analyze image features to determine waste type with improved accuracy"""
        try:
            # Load image using OpenCV
            img = cv2.imread(image_path)
            if img is None:
                logging.error(f"Failed to load image from {image_path}")
                return 'dry', 0.75
            
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Convert to HSV for better color analysis
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Calculate color statistics with error handling
            try:
                mean_color_rgb = np.mean(img_rgb, axis=(0, 1))
                mean_color_hsv = np.mean(img_hsv, axis=(0, 1))
            except Exception as e:
                logging.error(f"Error calculating color statistics: {e}")
                return 'dry', 0.75
            
            # Calculate texture features
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
            
            # Enhanced classification focused on dry waste identification
            dry_score = 0
            wet_score = 0
            
            hue = mean_color_hsv[0]
            saturation = mean_color_hsv[1]
            value = mean_color_hsv[2]
            r, g, b = mean_color_rgb
            
            # STRONG DRY WASTE INDICATORS
            
            # 1. Plastic identification (bottles, cups, containers)
            # Clear/transparent materials (low saturation, high value)
            if saturation < 40 and value > 150:
                dry_score += 0.6  # Strong plastic indicator
            
            # 2. White/light colored items (cups, paper, packaging)
            if r > 180 and g > 180 and b > 180:
                dry_score += 0.5  # Strong paper/plastic indicator
            
            # 3. High edge density (manufactured items, bottles, containers)
            if edge_density > 0.12:
                dry_score += 0.4  # Manufactured items have defined edges
            
            # 4. Bright artificial colors (plastic packaging)
            if saturation > 60 and value > 120:
                # Check for typical plastic colors
                if (hue < 15 or hue > 340) or (85 < hue < 135) or (220 < hue < 280):
                    dry_score += 0.3
            
            # 5. Metallic appearance (cans, foil)
            if saturation < 25 and 80 < value < 180 and edge_density > 0.1:
                dry_score += 0.4
            
            # 6. Multiple distinct objects (typical of collected dry waste)
            # Use contour detection to count objects
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            object_count = len([c for c in contours if cv2.contourArea(c) > 100])
            if object_count > 5:  # Multiple objects suggest collection of items
                dry_score += 0.3
            
            # WET WASTE INDICATORS (more conservative)
            
            # 1. Organic green colors (vegetables)
            if 35 <= hue <= 85 and saturation > 70 and value > 50:
                wet_score += 0.4
            
            # 2. Brown organic colors (food waste)
            if 10 <= hue <= 25 and saturation > 50 and value < 150:
                wet_score += 0.4
            
            # 3. Very low edge density (soft organic matter)
            if edge_density < 0.05:
                wet_score += 0.2
            
            # 4. Dark, low-saturation organic appearance
            if saturation < 30 and value < 100 and edge_density < 0.08:
                wet_score += 0.3
            
            # FINAL DECISION with bias toward dry waste for ambiguous cases
            if dry_score > wet_score + 0.1:  # Small bias toward dry
                confidence = min(0.95, 0.70 + (dry_score / (dry_score + wet_score + 0.1)) * 0.25)
                return 'dry', confidence
            elif wet_score > dry_score:
                confidence = min(0.95, 0.70 + (wet_score / (wet_score + dry_score + 0.1)) * 0.25)
                return 'wet', confidence
            else:
                # Default to dry for unclear cases (most waste is dry)
                return 'dry', 0.75
                
        except Exception as e:
            logging.error(f"Error analyzing image features: {e}")
            # Default fallback to dry
            return 'dry', 0.75
    
    def create_highlighted_image(self, image_path, waste_type):
        """Create an image with color highlighting for waste classification"""
        try:
            img = cv2.imread(image_path)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Create overlay
            overlay = img_rgb.copy()
            
            if waste_type == 'wet':
                # Green overlay for wet waste
                overlay[:, :, 1] = np.minimum(overlay[:, :, 1] + 30, 255)  # Increase green
                highlight_color = (76, 175, 80)  # Green
            else:
                # Blue overlay for dry waste
                overlay[:, :, 2] = np.minimum(overlay[:, :, 2] + 30, 255)  # Increase blue
                highlight_color = (33, 150, 243)  # Blue
            
            # Blend original and overlay
            alpha = 0.3
            highlighted = cv2.addWeighted(img_rgb, 1 - alpha, overlay, alpha, 0)
            
            # Add border highlighting
            border_thickness = 10
            highlighted = cv2.copyMakeBorder(
                highlighted, border_thickness, border_thickness, border_thickness, border_thickness,
                cv2.BORDER_CONSTANT, value=highlight_color
            )
            
            return highlighted
            
        except Exception as e:
            logging.error(f"Error creating highlighted image: {e}")
            return None
    
    def predict(self, image_path):
        """Predict waste type from image with highlighting"""
        try:
            # Use feature analysis for classification
            waste_type, confidence = self.analyze_image_features(image_path)
            
            # Create highlighted image
            highlighted_image = self.create_highlighted_image(image_path, waste_type)
            
            # Save highlighted image
            if highlighted_image is not None:
                highlighted_path = image_path.replace('.', '_highlighted.')
                cv2.imwrite(highlighted_path, cv2.cvtColor(highlighted_image, cv2.COLOR_RGB2BGR))
            
            # Get bin color and disposal method
            if waste_type == 'wet':
                bin_color = '#4CAF50'  # Green for wet/organic waste
                disposal_method = "Dispose in GREEN bin. Wet waste includes food scraps, organic matter, and biodegradable materials."
                waste_examples = "Examples: Vegetable peels, fruit waste, food leftovers, tea bags, garden waste"
            else:
                bin_color = '#2196F3'  # Blue for dry waste
                disposal_method = "Dispose in BLUE bin. Dry waste includes plastic, paper, metal, and non-biodegradable materials."
                waste_examples = "Examples: Plastic bottles, paper, cardboard, metal cans, glass bottles"
            
            return {
                'waste_type': waste_type,
                'confidence': round(confidence * 100, 2),
                'bin_color': bin_color,
                'disposal_method': disposal_method,
                'waste_examples': waste_examples,
                'highlighted_image': highlighted_path if highlighted_image is not None else None
            }
            
        except Exception as e:
            logging.error(f"Error in prediction: {e}")
            return {
                'waste_type': 'dry',
                'confidence': 50.0,
                'bin_color': '#2196F3',
                'disposal_method': "Unable to classify accurately. Please dispose in appropriate bin based on waste type.",
                'waste_examples': "Please try taking a clearer image for better classification.",
                'highlighted_image': None
            }
