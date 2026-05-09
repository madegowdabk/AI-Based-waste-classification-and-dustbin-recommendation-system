import os
import json
import logging
from flask import Flask, render_template, request, jsonify, url_for, redirect
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import tensorflow as tf
import numpy as np
from PIL import Image
import cv2
from geopy.distance import geodesic
from waste_classifier import WasteClassifier

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "waste-management-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize waste classifier
waste_classifier = WasteClassifier()

# Load dustbin data
def load_dustbin_data():
    try:
        with open('dustbin_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Dustbin data file not found")
        return []

dustbin_data = load_dustbin_data()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def find_nearest_dustbins(user_lat, user_lng, waste_type, max_distance=10):
    """Find nearest dustbins based on user location and waste type"""
    suitable_dustbins = []
    
    for dustbin in dustbin_data:
        # Calculate distance
        user_location = (user_lat, user_lng)
        dustbin_location = (dustbin['latitude'], dustbin['longitude'])
        distance = geodesic(user_location, dustbin_location).kilometers
        
        # Check if dustbin is within range and accepts the waste type
        if distance <= max_distance and waste_type.lower() in [wt.lower() for wt in dustbin['accepted_waste_types']]:
            dustbin_info = dustbin.copy()
            dustbin_info['distance'] = round(distance, 2)
            suitable_dustbins.append(dustbin_info)
    
    # Sort by distance
    suitable_dustbins.sort(key=lambda x: x['distance'])
    return suitable_dustbins[:5]  # Return top 5 nearest

@app.route('/')
def index():
    return redirect("https://techguru278.github.io/Wmanagment/")

@app.route('/classify_waste', methods=['POST'])
def classify_waste():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        user_lat = float(request.form.get('latitude', 0))
        user_lng = float(request.form.get('longitude', 0))
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and file.filename and allowed_file(file.filename):
            # Save uploaded file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Classify waste
            prediction_result = waste_classifier.predict(filepath)
            
            # Find nearest dustbins
            nearest_dustbins = find_nearest_dustbins(user_lat, user_lng, prediction_result['waste_type'])
            
            # Clean up uploaded file
            os.remove(filepath)
            
            return jsonify({
                'waste_type': prediction_result['waste_type'],
                'confidence': prediction_result['confidence'],
                'bin_color': prediction_result['bin_color'],
                'disposal_method': prediction_result['disposal_method'],
                'waste_examples': prediction_result.get('waste_examples', ''),
                'nearest_dustbins': nearest_dustbins
            })
        
        return jsonify({'error': 'Invalid file type'}), 400
    
    except Exception as e:
        logging.error(f"Error in waste classification: {str(e)}")
        return jsonify({'error': 'An error occurred during classification'}), 500

@app.route('/get_dustbins')
def get_dustbins():
    """Get all dustbin locations for map display"""
    return jsonify(dustbin_data)

@app.route('/find_nearest_dustbins', methods=['POST'])
def find_nearest_dustbins_endpoint():
    try:
        data = request.get_json()
        user_lat = data.get('latitude')
        user_lng = data.get('longitude')
        waste_type = data.get('waste_type', 'dry')
        location_name = data.get('location_name', '')
        
        # If location name is provided, try to find coordinates
        if location_name and not (user_lat and user_lng):
            # Simple location matching for Mysuru areas
            location_coords = get_location_coordinates(location_name)
            if location_coords:
                user_lat, user_lng = location_coords
        
        if not user_lat or not user_lng:
            return jsonify({'error': 'Location coordinates or area name required'}), 400
        
        nearest_dustbins = find_nearest_dustbins(user_lat, user_lng, waste_type)
        return jsonify({
            'dustbins': nearest_dustbins,
            'user_location': {'lat': user_lat, 'lng': user_lng}
        })
    
    except Exception as e:
        logging.error(f"Error finding nearest dustbins: {str(e)}")
        return jsonify({'error': 'An error occurred while finding dustbins'}), 500

def get_location_coordinates(location_name):
    """Get coordinates for common Mysuru location names"""
    location_map = {
        'kr circle': (12.305443, 76.654743),
        'devaraja market': (12.307318, 76.653684),
        'lakshmipuram': (12.302421, 76.660829),
        'jayanagar': (12.295237, 76.65932),
        'mysore zoo': (12.300607, 76.665328),
        'nazarbad': (12.300536, 76.665227),
        'railway station': (12.313675, 76.645917),
        'saraswathipuram': (12.30182, 76.641424),
        'kuvempunagar': (12.275096, 76.643297),
        'vontikoppal': (12.32743, 76.631268),
        'manasagangothri': (12.315305, 76.62234),
        'chamundi hill': (12.273873, 76.670712),
        'gokulam': (12.330838, 76.629327),
        'ramakrishna nagar': (12.28129, 76.620483),
        'lalitha mahal': (12.279196, 76.689449),
        'brindavan extension': (12.341386, 76.626853),
        'infosys': (12.257447, 76.654516),
        'alanahalli': (12.264384, 76.686222),
        'metagalli': (12.351613, 76.628753),
        'hebbal': (12.353687, 76.621863),
        'bogadi': (12.28977, 76.591344),
        'vijayanagar': (12.328719, 76.591136)
    }
    
    location_lower = location_name.lower().strip()
    for key, coords in location_map.items():
        if key in location_lower or location_lower in key:
            return coords
    return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
