import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pathlib import Path
import base64
from openai import OpenAI
import io
from PIL import Image
import json
from google.cloud import vision

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = Path('static/uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
vision_client = vision.ImageAnnotatorClient()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_receipt_with_vision(image_path):
    """
    Process receipt using Google Cloud Vision API
    """
    try:
        # Read the image file
        with open(image_path, 'rb') as image_file:
            content = image_file.read()

        # Create image object
        image = vision.Image(content=content)

        # Perform OCR
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            raise ValueError("No text found in image")

        # Extract full text (first element contains all text)
        extracted_text = texts[0].description
        
        # Process the extracted text
        return process_receipt_text(extracted_text)
    except Exception as e:
        print(f"Error in OCR processing: {e}")
        return None

def process_receipt_text(text):
    """
    Process receipt text using GPT-3.5-turbo
    """
    try:
        format_prompt = f"""
        Format the following receipt text into a structured JSON format.
        Identify and clearly label:
        - Store/Merchant name
        - Date and time
        - Individual items and their prices
        - Subtotal
        - Tax
        - Total amount
        - Any food items

        Receipt text:
        {text}

        You must respond with ONLY valid JSON that matches this structure exactly, with no additional text or explanation:
        {{
            "merchant": "store name",
            "datetime": "date and time",
            "items": [
                {{"name": "item name", "price": "price", "is_food": true/false}}
            ],
            "subtotal": "amount",
            "tax": "amount",
            "total": "amount",
            "food_items": ["list of food items only"]
        }}
        """

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that processes receipt text and extracts structured information. Always respond with valid JSON only."},
                {"role": "user", "content": format_prompt}
            ]
        )

        receipt_data = json.loads(response.choices[0].message.content)
        
        # Generate recipe suggestions if food items are present
        if receipt_data.get("food_items"):
            recipe_prompt = f"""
            Based on these ingredients: {', '.join(receipt_data['food_items'])}
            
            Suggest 2-3 recipes that could be made using some or all of these ingredients.
            For each recipe provide:
            1. Recipe name
            2. Additional ingredients needed
            3. Step-by-step instructions
            4. Estimated cooking time
            5. Difficulty level (Easy/Medium/Hard)

            You must respond with ONLY valid JSON that matches this structure exactly, with no additional text or explanation:
            {{
                "recipes": [
                    {{
                        "name": "recipe name",
                        "additional_ingredients": ["list of additional ingredients needed"],
                        "instructions": ["list of steps"],
                        "cooking_time": "estimated time",
                        "difficulty": "difficulty level"
                    }}
                ]
            }}
            """

            recipe_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful chef that suggests recipes based on available ingredients. Always respond with valid JSON only."},
                    {"role": "user", "content": recipe_prompt}
                ]
            )

            recipes = json.loads(recipe_response.choices[0].message.content)
            receipt_data["recipe_suggestions"] = recipes["recipes"]

        return receipt_data

    except Exception as e:
        print(f"Error in text processing: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process-receipt', methods=['POST'])
def process_receipt():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        # Save the uploaded file
        filename = secure_filename(file.filename)
        filepath = app.config['UPLOAD_FOLDER'] / filename
        file.save(str(filepath))
        
        # Process the receipt using Google Cloud Vision API
        processed_data = process_receipt_with_vision(filepath)
        if not processed_data:
            raise ValueError("Failed to process receipt")

        # Clean up the uploaded file
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'processed_data': processed_data
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True) 