# Receipt Reader & Recipe Generator

A web application that processes receipt images using Google Cloud Vision OCR and OpenAI to extract text, identify food items, and generate recipe suggestions.

## Features

- Upload receipt images via drag-and-drop or file selection
- Extract text from receipts using Google Cloud Vision OCR
- Process and format receipt text using OpenAI
- Identify food items from the receipt
- Generate recipe suggestions based on identified ingredients
- Modern, responsive web interface

## Prerequisites

- Python 3.9 or higher
- Google Cloud Vision API credentials
- OpenAI API key

## Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/doda89/ReceiptReaderWeb.git
cd ReceiptReaderWeb
```

2. Create a virtual environment and activate it:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up credentials:

   a. Get your OpenAI API key from https://platform.openai.com/api-keys
   
   b. Set up Google Cloud Vision:
      - Create a project in Google Cloud Console
      - Enable the Cloud Vision API
      - Create a service account and download the JSON key file
      - Save the key file as `google-credentials.json` in your project root

5. Create a `.env` file in the project root:
```bash
GOOGLE_APPLICATION_CREDENTIALS=./google-credentials.json
OPENAI_API_KEY=your-openai-api-key-here
```

6. Start the Flask development server:
```bash
python app.py
```

7. Visit `http://127.0.0.1:5000` in your browser

## API Endpoints

### POST /api/process-receipt

Process a receipt image and return extracted information.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: Form data with 'file' field containing the image

**Response:**
```json
{
    "success": true,
    "processed_data": {
        "merchant": "Store name",
        "datetime": "Date and time",
        "items": [
            {"name": "item name", "price": "price", "is_food": true/false}
        ],
        "subtotal": "amount",
        "tax": "amount",
        "total": "amount",
        "food_items": ["list of food items"],
        "recipe_suggestions": [
            {
                "name": "Recipe name",
                "additional_ingredients": ["ingredients needed"],
                "instructions": ["step by step instructions"],
                "cooking_time": "estimated time",
                "difficulty": "difficulty level"
            }
        ]
    }
}
```

## Deployment

### Vercel Deployment

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Configure environment variables in Vercel:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `GOOGLE_APPLICATION_CREDENTIALS`: Contents of your google-credentials.json file

3. Deploy using Vercel CLI:
```bash
vercel
```

## Environment Variables

Required environment variables:
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google Cloud credentials JSON file
- `OPENAI_API_KEY`: Your OpenAI API key

## Security Notes

- Never commit `.env` or credential files to the repository
- Keep your API keys secure and rotate them regularly
- Monitor your API usage to prevent unexpected charges

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License. 