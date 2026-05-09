// Global variables
let userLocation = null;
let currentClassification = null;

// DOM elements
const imageInput = document.getElementById('imageInput');
const wasteForm = document.getElementById('wasteForm');
const captureBtn = document.getElementById('captureBtn');
const cameraSection = document.getElementById('cameraSection');
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const snapBtn = document.getElementById('snapBtn');
const stopCameraBtn = document.getElementById('stopCameraBtn');
const imagePreview = document.getElementById('imagePreview');
const previewImg = document.getElementById('previewImg');
const loadingSpinner = document.getElementById('loadingSpinner');
const classificationResult = document.getElementById('classificationResult');
const resultDetails = document.getElementById('resultDetails');
const errorDisplay = document.getElementById('errorDisplay');
const errorMessage = document.getElementById('errorMessage');
const getLocationBtn = document.getElementById('getLocationBtn');
const searchLocationBtn = document.getElementById('searchLocationBtn');
const locationInput = document.getElementById('locationInput');
const locationStatus = document.getElementById('locationStatus');
const locationText = document.getElementById('locationText');
const dustbinsContainer = document.getElementById('dustbinsContainer');
const locationDropdown = document.getElementById('locationDropdown');

// Event listeners
imageInput.addEventListener('change', handleImageSelect);
wasteForm.addEventListener('submit', handleWasteClassification);
captureBtn.addEventListener('click', startCamera);
snapBtn.addEventListener('click', capturePhoto);
stopCameraBtn.addEventListener('click', stopCamera);
getLocationBtn.addEventListener('click', getUserLocation);
searchLocationBtn.addEventListener('click', searchLocation);
locationDropdown.addEventListener('change', handleLocationDropdown);
locationInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        searchLocation();
    }
});

// Handle image selection
function handleImageSelect(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImg.src = e.target.result;
            imagePreview.classList.remove('d-none');
        };
        reader.readAsDataURL(file);
    }
}

// Handle waste classification
async function handleWasteClassification(event) {
    event.preventDefault();
    
    const formData = new FormData();
    const imageFile = imageInput.files[0];
    
    if (!imageFile) {
        showError('Please select an image first.');
        return;
    }
    
    if (!userLocation && !locationInput.value.trim()) {
        showError('Please enter a location or allow GPS access to find nearby dustbins.');
        return;
    }
    
    formData.append('image', imageFile);
    if (userLocation) {
        formData.append('latitude', userLocation.lat);
        formData.append('longitude', userLocation.lng);
    } else if (locationInput.value.trim()) {
        // Will be handled by the server using location name
        formData.append('location_name', locationInput.value.trim());
    }
    
    showLoading(true);
    hideError();
    
    try {
        const response = await fetch('/classify_waste', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            currentClassification = result;
            displayClassificationResult(result);
            displayNearestDustbins(result.nearest_dustbins);
        } else {
            showError(result.error || 'Classification failed. Please try again.');
        }
    } catch (error) {
        console.error('Classification error:', error);
        showError('Network error. Please check your connection and try again.');
    } finally {
        showLoading(false);
    }
}

// Start camera
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'environment' } 
        });
        video.srcObject = stream;
        cameraSection.classList.remove('d-none');
        captureBtn.classList.add('d-none');
    } catch (error) {
        console.error('Camera error:', error);
        showError('Unable to access camera. Please use file upload instead.');
    }
}

// Capture photo from camera
function capturePhoto() {
    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0);
    
    canvas.toBlob(function(blob) {
        const file = new File([blob], 'captured_image.jpg', { type: 'image/jpeg' });
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        imageInput.files = dataTransfer.files;
        
        // Show preview
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImg.src = e.target.result;
            imagePreview.classList.remove('d-none');
        };
        reader.readAsDataURL(file);
        
        stopCamera();
    }, 'image/jpeg', 0.8);
}

// Stop camera
function stopCamera() {
    const stream = video.srcObject;
    if (stream) {
        const tracks = stream.getTracks();
        tracks.forEach(track => track.stop());
    }
    video.srcObject = null;
    cameraSection.classList.add('d-none');
    captureBtn.classList.remove('d-none');
}

// Search for location by name
function searchLocation() {
    const locationName = locationInput.value.trim();
    if (!locationName) {
        showError('Please enter a location name.');
        return;
    }
    
    locationText.textContent = `Searching for "${locationName}"...`;
    
    // Send request to find dustbins by location name
    fetch('/find_nearest_dustbins', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            location_name: locationName,
            waste_type: currentClassification ? currentClassification.waste_type : 'dry'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showError(`Location not found: ${data.error}`);
            locationText.textContent = 'Location not found. Try: KR Circle, Jayanagar, Railway Station, etc.';
        } else {
            userLocation = data.user_location;
            locationText.textContent = `Found: ${locationName} (${userLocation.lat.toFixed(4)}, ${userLocation.lng.toFixed(4)})`;
            locationStatus.className = 'alert alert-success';
            displayNearestDustbins(data.dustbins);
            updateMapLocation(userLocation.lat, userLocation.lng, locationName);
        }
    })
    .catch(error => {
        console.error('Location search error:', error);
        showError('Error searching for location. Please try again.');
    });
}

// Get user location
function getUserLocation() {
    if (!navigator.geolocation) {
        showError('Geolocation is not supported by this browser.');
        return;
    }
    
    locationText.textContent = 'Getting your location...';
    getLocationBtn.disabled = true;
    
    navigator.geolocation.getCurrentPosition(
        function(position) {
            userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };
            
            locationText.textContent = `GPS location: ${userLocation.lat.toFixed(4)}, ${userLocation.lng.toFixed(4)}`;
            locationStatus.className = 'alert alert-success';
            
            // Clear location input since we have GPS
            locationInput.value = '';
            
            // Update map to show current location
            updateMapLocation(userLocation.lat, userLocation.lng, 'Your Location');
        },
        function(error) {
            console.error('Geolocation error:', error);
            locationText.textContent = 'GPS unavailable. Please enter location manually.';
            locationStatus.className = 'alert alert-warning';
            getLocationBtn.disabled = false;
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 60000
        }
    );
}

// Display classification result
function displayClassificationResult(result) {
    const wasteType = result.waste_type;
    const confidence = result.confidence;
    const binColor = result.bin_color;
    const disposalMethod = result.disposal_method;
    const wasteExamples = result.waste_examples || '';
    const highlightedImage = result.highlighted_image;
    
    resultDetails.innerHTML = `
        <div class="classification-highlight ${wasteType}">
            <div class="row align-items-center">
                <div class="col-auto">
                    <div class="waste-color-indicator" style="background-color: ${binColor}; width: 40px; height: 40px;"></div>
                </div>
                <div class="col">
                    <h6 class="mb-1">
                        <strong>${wasteType.toUpperCase()} WASTE</strong>
                        <span class="badge bg-primary ms-2">${confidence}% confidence</span>
                    </h6>
                    <p class="mb-1">${disposalMethod}</p>
                    <small class="text-muted">${wasteExamples}</small>
                </div>
            </div>
        </div>
    `;
    
    // No highlighted image display needed
    
    classificationResult.classList.remove('d-none');
    classificationResult.classList.add('fade-in-up');
}

// Display nearest dustbins
function displayNearestDustbins(dustbins) {
    if (!dustbins || dustbins.length === 0) {
        dustbinsContainer.innerHTML = '<p class="text-muted">No suitable dustbins found nearby.</p>';
        return;
    }
    
    let html = '';
    dustbins.forEach((dustbin, index) => {
        const wasteTypes = dustbin.accepted_waste_types.map(type => 
            `<span class="bin-type-${type}">${type}</span>`
        ).join(', ');
        
        html += `
            <div class="dustbin-item" onclick="focusOnDustbin(${dustbin.latitude}, ${dustbin.longitude})">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${dustbin.name}</h6>
                        <p class="mb-1 text-muted small">${dustbin.address}</p>
                        <p class="mb-0"><strong>Accepts:</strong> ${wasteTypes}</p>
                        <p class="mb-0"><small class="text-info">Facilities: ${dustbin.facilities.join(', ')}</small></p>
                    </div>
                    <span class="badge bg-primary distance-badge">${dustbin.distance} km</span>
                </div>
            </div>
        `;
    });
    
    dustbinsContainer.innerHTML = html;
}

// Update map location dynamically
function updateMapLocation(lat, lng, locationName) {
    const mapContainer = document.querySelector('#mapContainer iframe');
    if (mapContainer) {
        // Update iframe src with new coordinates
        const newMapSrc = `https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d15000!2d${lng}!3d${lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s${lat},${lng}!2s${encodeURIComponent(locationName)}!5e0!3m2!1sen!2sin!4v${Date.now()}!5m2!1sen!2sin`;
        mapContainer.src = newMapSrc;
        
        console.log(`Map updated to show: ${locationName} at ${lat}, ${lng}`);
    }
}

// Focus on dustbin location
function focusOnDustbin(lat, lng) {
    updateMapLocation(lat, lng, 'Selected Dustbin');
    showError(`Focused on dustbin at: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
}

// Utility functions
function showLoading(show) {
    if (show) {
        loadingSpinner.classList.remove('d-none');
        classificationResult.classList.add('d-none');
        document.querySelector('#classifyBtn').disabled = true;
    } else {
        loadingSpinner.classList.add('d-none');
        document.querySelector('#classifyBtn').disabled = false;
    }
}

function showError(message) {
    errorMessage.textContent = message;
    errorDisplay.classList.remove('d-none');
    setTimeout(() => {
        errorDisplay.classList.add('d-none');
    }, 5000);
}

function hideError() {
    errorDisplay.classList.add('d-none');
}

// Handle location dropdown selection
function handleLocationDropdown() {
    const selectedValue = locationDropdown.value;
    if (!selectedValue) return;
    
    // Map dropdown values to location names
    const locationMap = {
        'kr_circle': 'KR Circle',
        'devaraja_market': 'Devaraja Market',
        'jayanagar': 'Jayanagar',
        'railway_station': 'Railway Station',
        'mysore_zoo': 'Mysore Zoo',
        'lakshmipuram': 'Lakshmipuram',
        'nazarbad': 'Nazarbad',
        'gokulam': 'Gokulam',
        'infosys': 'Infosys Campus',
        'chamundi_hill': 'Chamundi Hill',
        'hebbal': 'Hebbal',
        'vijayanagar': 'Vijayanagar',
        'saraswathipuram': 'Saraswathipuram',
        'kuvempunagar': 'Kuvempunagar',
        'manasagangothri': 'Manasagangothri'
    };
    
    const locationName = locationMap[selectedValue];
    if (locationName) {
        locationInput.value = locationName;
        searchLocation();
    }
}

// Theme switching functionality
function toggleTheme() {
    const body = document.body;
    const currentTheme = body.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    body.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Add a nice transition effect
    body.style.transition = 'all 0.5s ease';
    setTimeout(() => {
        body.style.transition = '';
    }, 500);
}

// Load saved theme on page load
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.body.setAttribute('data-theme', savedTheme);
}

// Initialize app when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('AI Waste Management System initialized');
    loadTheme(); // Load the saved theme
    
    // Show initial dustbins for Mysuru center
    const defaultLocation = { lat: 12.2958, lng: 76.6394 };
    userLocation = defaultLocation;
    
    // Load initial dustbins
    fetch('/find_nearest_dustbins', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            latitude: defaultLocation.lat,
            longitude: defaultLocation.lng,
            waste_type: 'dry'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.error) {
            displayNearestDustbins(data.dustbins);
        }
    })
    .catch(error => {
        console.error('Error loading initial dustbins:', error);
    });
});