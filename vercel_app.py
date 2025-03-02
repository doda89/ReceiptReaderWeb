from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import os
from pathlib import Path
import json
from openai import OpenAI
from google.cloud import vision
import base64

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Vision client with credentials from environment variable
vision_client = None
if GOOGLE_CREDENTIALS:
    try:
        credentials_info = json.loads(GOOGLE_CREDENTIALS)
        credentials = vision.Credentials.from_service_account_info(credentials_info)
        vision_client = vision.ImageAnnotatorClient(credentials=credentials)
    except Exception as e:
        print(f"Error initializing Vision client: {e}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_receipt_with_vision(image_path):
    try:
        if not vision_client:
            raise ValueError("Vision client not properly initialized")

        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            raise ValueError("No text found in image")

        return process_receipt_text(texts[0].description)
    except Exception as e:
        print(f"Error in OCR processing: {e}")
        return None

def process_receipt_text(text):
    try:
        format_prompt = f"""Format the following receipt text into JSON with: merchant name, date/time, items (with prices and food flag), subtotal, tax, total, and food items list.
Receipt text: {text}"""

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Format receipt text into JSON with merchant, datetime, items (name, price, is_food), subtotal, tax, total, food_items."},
                {"role": "user", "content": format_prompt}
            ]
        )

        receipt_data = json.loads(response.choices[0].message.content)
        
        if receipt_data.get("food_items"):
            recipe_prompt = f"""Suggest 2-3 recipes using these ingredients: {', '.join(receipt_data['food_items'])}"""

            recipe_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Suggest recipes with name, ingredients, instructions, time, difficulty."},
                    {"role": "user", "content": recipe_prompt}
                ]
            )

            recipes = json.loads(recipe_response.choices[0].message.content)
            receipt_data["recipe_suggestions"] = recipes.get("recipes", [])

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
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        processed_data = process_receipt_with_vision(filepath)
        if not processed_data:
            raise ValueError("Failed to process receipt")

        os.remove(filepath)
        return jsonify({'success': True, 'processed_data': processed_data})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path) 