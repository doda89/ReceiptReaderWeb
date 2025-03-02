import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pathlib import Path
import base64
from openai import OpenAI
import io
from PIL import Image

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = Path('static/uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_receipt_with_vision(image_path):
    """
    Process receipt using OpenAI's Vision API
    """
    try:
        # Open and encode image
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Create Vision API request
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "This is a receipt image. Please extract all the text and format it into a structured format. Include merchant name, date/time, items with prices, subtotal, tax, and total. Also identify any food items."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # Process the extracted text
        extracted_text = response.choices[0].message.content
        return process_receipt_text(extracted_text)
    except Exception as e:
        print(f"Error in vision processing: {e}")
        return None

def process_receipt_text(text):
    """
    Process receipt text using OpenAI to extract structured information.
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

        Format the response as JSON with this structure:
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

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that processes receipt text and extracts structured information."},
                {"role": "user", "content": format_prompt}
            ],
            response_format={"type": "json_object"}
        )

        receipt_data = response.choices[0].message.content
        
        # Generate recipe suggestions if food items are present
        if "food_items" in receipt_data and receipt_data["food_items"]:
            recipe_prompt = f"""
            Based on these ingredients: {', '.join(receipt_data['food_items'])}
            
            Suggest 2-3 recipes that could be made using some or all of these ingredients.
            For each recipe provide:
            1. Recipe name
            2. Additional ingredients needed
            3. Step-by-step instructions
            4. Estimated cooking time
            5. Difficulty level (Easy/Medium/Hard)

            Format as JSON:
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

            recipe_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful chef that suggests recipes based on available ingredients."},
                    {"role": "user", "content": recipe_prompt}
                ],
                response_format={"type": "json_object"}
            )

            recipes = recipe_response.choices[0].message.content
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
        
        # Process the receipt using Vision API
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