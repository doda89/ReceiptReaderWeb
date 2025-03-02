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
# Use /tmp for Vercel's serverless environment
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client
openai_client = OpenAI()  # It will automatically use OPENAI_API_KEY from environment

# Initialize Vision client with credentials from environment variable
try:
    import json
    google_creds = os.getenv('GOOGLE_CREDENTIALS')
    if google_creds:
        creds_path = '/tmp/google-credentials.json'
        with open(creds_path, 'w') as f:
            f.write(google_creds)
        vision_client = vision.ImageAnnotatorClient.from_service_account_file(creds_path)
        os.remove(creds_path)  # Clean up after initialization
    else:
        vision_client = vision.ImageAnnotatorClient.from_service_account_file('receiptreader-452521-728df5344329.json')
    print("Vision client initialized successfully")
except Exception as e:
    print(f"Error initializing Vision client: {str(e)}")
    vision_client = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_receipt_with_vision(image_path):
    try:
        if not vision_client:
            print("Vision client is not initialized")
            raise ValueError("Vision client not properly initialized")

        print(f"Processing image at path: {image_path}")
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        print("Image loaded successfully, sending to Vision API")
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            print("No text found in the image")
            raise ValueError("No text found in image")

        print(f"Text detected in image: {texts[0].description[:100]}...")
        return process_receipt_text(texts[0].description)
    except Exception as e:
        print(f"Error in OCR processing: {str(e)}")
        return None

def process_receipt_text(text):
    try:
        print("Processing receipt text with OpenAI")
        format_prompt = f"""Format the following receipt text into JSON with: merchant name, date/time, items (with prices and food flag), subtotal, tax, total, and food items list.
Receipt text: {text}"""

        print("Sending request to OpenAI")
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Format receipt text into JSON with merchant, datetime, items (name, price, is_food), subtotal, tax, total, food_items. Ensure the response is valid JSON."},
                {"role": "user", "content": format_prompt}
            ]
        )

        print("Received response from OpenAI")
        response_content = response.choices[0].message.content.strip()
        print(f"Raw OpenAI response: {response_content}")
        
        try:
            receipt_data = json.loads(response_content)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print("Attempting to fix JSON format...")
            # Try to extract JSON from the response if it's wrapped in backticks or has extra text
            import re
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                try:
                    receipt_data = json.loads(json_match.group())
                except json.JSONDecodeError as e:
                    print(f"Second JSON parsing attempt failed: {str(e)}")
                    raise
            else:
                raise ValueError("Could not find valid JSON in the response")
        
        print(f"Parsed receipt data: {json.dumps(receipt_data, indent=2)}")
        
        if receipt_data.get("food_items"):
            print("Food items found, generating recipe suggestions")
            recipe_prompt = """Generate a JSON array of 2-3 recipe suggestions using these ingredients: {}. 
Format the response as a JSON object with a 'recipes' array containing objects with 'name', 'ingredients', 'instructions', 'time', and 'difficulty' fields.""".format(', '.join(receipt_data['food_items']))

            recipe_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Generate recipe suggestions in valid JSON format with the structure: {'recipes': [{'name': string, 'ingredients': string[], 'instructions': string[], 'time': string, 'difficulty': string}]}"},
                    {"role": "user", "content": recipe_prompt}
                ]
            )

            recipe_content = recipe_response.choices[0].message.content.strip()
            print(f"Raw recipe response: {recipe_content}")
            
            try:
                recipe_data = json.loads(recipe_content)
                receipt_data["recipe_suggestions"] = recipe_data.get("recipes", [])
                print("Recipe suggestions generated successfully")
            except json.JSONDecodeError as e:
                print(f"Recipe JSON parsing error: {str(e)}")
                receipt_data["recipe_suggestions"] = []

        return receipt_data

    except Exception as e:
        print(f"Error in text processing: {str(e)}")
        print(f"Full error details: {type(e).__name__}: {str(e)}")
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
        print(f"Saving file to: {filepath}")
        file.save(filepath)
        
        processed_data = process_receipt_with_vision(filepath)
        if not processed_data:
            print("Receipt processing failed")
            raise ValueError("Failed to process receipt")

        os.remove(filepath)
        return jsonify({'success': True, 'processed_data': processed_data})
    
    except Exception as e:
        print(f"Error in process_receipt route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=True) 