# Receipt Reader & Recipe Generator

A web application that processes receipt images using OCR, extracts text, and generates recipe suggestions using a local LLM.

## Features

- Upload receipt images via drag-and-drop or file selection
- Extract text from receipts using OCR
- Process and format receipt text for better readability
- Identify food items from the receipt
- Generate recipe suggestions based on identified ingredients
- Modern, responsive web interface

## Prerequisites

- Python 3.7 or higher
- Tesseract OCR
- Ollama (for local LLM)

### Installing Tesseract OCR

#### macOS
```bash
brew install tesseract
```

#### Ubuntu/Debian
```bash
sudo apt-get install tesseract-ocr
```

#### Windows
1. Download the installer from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install and add the installation directory to your system PATH

### Installing Ollama

Follow the instructions at [Ollama's website](https://ollama.ai) to install and set up Ollama on your system.

## Local Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd receipt-reader
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

4. Start the Flask development server:
```bash
python app.py
```

5. Visit `http://localhost:5000` in your browser

## Deployment to Vercel

1. Install the Vercel CLI:
```bash
npm install -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

3. Deploy the application:
```bash
vercel
```

4. Follow the prompts to complete the deployment

## Environment Variables

The following environment variables need to be set in your Vercel project:

- `PYTHONPATH`: Set to "." for proper module imports
- `TESSERACT_CMD`: Path to Tesseract executable (if not in system PATH)

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
    "raw_text": "Original OCR text",
    "refined_text": "Formatted receipt text",
    "food_items": ["List", "of", "food", "items"],
    "recipe_suggestions": "Generated recipe suggestions",
    "success": true,
    "error": null
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 