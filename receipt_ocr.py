import cv2
import pytesseract
import numpy as np
from PIL import Image
import os
from pathlib import Path
import requests
import json
from typing import Optional, Dict, Any, List

class ReceiptOCR:
    # Ollama API configuration
    OLLAMA_API_URL = "http://localhost:11434/api/generate"
    DEFAULT_MODEL = "llama3"

    # Common food-related keywords to help identify food items
    FOOD_KEYWORDS = [
        "fresh", "organic", "fruit", "vegetable", "meat", "dairy",
        "produce", "grocery", "ingredients", "food", "spice"
    ]

    def __init__(self, tesseract_cmd=None, llm_model=None):
        """
        Initialize the ReceiptOCR processor.
        Args:
            tesseract_cmd (str, optional): Path to tesseract executable
            llm_model (str, optional): Name of the Ollama model to use
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # Create output directory if it doesn't exist
        self.output_dir = Path("processed_images")
        self.output_dir.mkdir(exist_ok=True)

        # Set LLM model
        self.llm_model = llm_model or self.DEFAULT_MODEL

    def load_image(self, image_path):
        """
        Load an image from the given path.
        Args:
            image_path (str): Path to the image file
        Returns:
            numpy.ndarray: Loaded image
        """
        return cv2.imread(str(image_path))

    def preprocess_image(self, image):
        """
        Preprocess the image to improve OCR accuracy.
        Args:
            image (numpy.ndarray): Input image
        Returns:
            numpy.ndarray: Preprocessed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 21, 10
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh)
        
        return denoised

    def extract_text(self, image):
        """
        Extract text from the preprocessed image using OCR.
        Args:
            image (numpy.ndarray): Preprocessed image
        Returns:
            str: Extracted text
        """
        # Convert numpy array to PIL Image
        pil_image = Image.fromarray(image)
        
        # Extract text using pytesseract
        text = pytesseract.image_to_string(pil_image)
        
        return text

    def save_debug_image(self, image, original_path):
        """
        Save the preprocessed image for debugging purposes.
        Args:
            image (numpy.ndarray): Preprocessed image
            original_path (str): Original image path
        """
        debug_path = self.output_dir / f"preprocessed_{Path(original_path).name}"
        cv2.imwrite(str(debug_path), image)

    def call_ollama_llm(self, text: str, prompt_type: str = "format_receipt") -> Optional[str]:
        """
        Calls the local Ollama LLM API with different prompt types.
        Args:
            text (str): Input text for the LLM
            prompt_type (str): Type of prompt to use ("format_receipt" or "generate_recipe")
        Returns:
            Optional[str]: Processed text or None if the request fails
        """
        if prompt_type == "format_receipt":
            prompt = f"""
            Below is the raw text extracted from a receipt using OCR. Please format this into a clear, structured format.
            Identify and clearly label:
            - Store/Merchant name
            - Date and time
            - Individual items and their prices
            - Subtotal
            - Tax
            - Total amount
            - Any discounts or special offers
            
            Raw receipt text:
            {text}
            
            Please format the response in a clear, readable way and fix any typos.
            Also, please identify and list any food items or ingredients separately at the end under a "Food Items" section.
            """
        elif prompt_type == "generate_recipe":
            prompt = f"""
            Based on the following ingredients and food items from a receipt, suggest a recipe or multiple recipe ideas.
            For each recipe, provide:
            1. Recipe name
            2. Additional ingredients that might be needed
            3. Step-by-step cooking instructions
            4. Estimated cooking time
            5. Difficulty level (Easy, Medium, Hard)
            
            Available ingredients:
            {text}
            
            Please suggest recipes that maximize the use of these ingredients. If there are non-food items, ignore them.
            Format the response in a clear, structured way.
            """
        else:
            raise ValueError(f"Unknown prompt type: {prompt_type}")

        payload = {
            "model": self.llm_model,
            "prompt": prompt,
            "stream": True
        }

        try:
            response = requests.post(self.OLLAMA_API_URL, json=payload, stream=True)
            response.raise_for_status()
            
            result_text = ""
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        data = json.loads(line)
                        result_text += data.get("response", "")
                    except json.JSONDecodeError as e:
                        print(f"Warning: JSON decode error: {e}")
                        continue
            
            return result_text.strip()
        except requests.exceptions.RequestException as e:
            print(f"Error calling Ollama API: {e}")
            return None

    def extract_food_items(self, refined_text: str) -> List[str]:
        """
        Extract food items from the refined receipt text.
        Args:
            refined_text (str): LLM-processed receipt text
        Returns:
            List[str]: List of identified food items
        """
        # First, try to find the "Food Items" section that we asked the LLM to create
        if "Food Items:" in refined_text:
            food_section = refined_text.split("Food Items:")[1].strip()
            # Split by newlines and clean up
            items = [item.strip("- ").strip() for item in food_section.split("\n") if item.strip()]
            return [item for item in items if item]
        
        # If no explicit food section, try to extract from the items list
        items_section = ""
        for line in refined_text.split("\n"):
            if any(keyword in line.lower() for keyword in self.FOOD_KEYWORDS):
                items_section += line + "\n"
        
        # Clean up and return items
        items = [item.strip("- ").strip() for item in items_section.split("\n") if item.strip()]
        return [item for item in items if item]

    def generate_recipe_suggestions(self, food_items: List[str]) -> Optional[str]:
        """
        Generate recipe suggestions based on the food items.
        Args:
            food_items (List[str]): List of food items from the receipt
        Returns:
            Optional[str]: Recipe suggestions or None if generation fails
        """
        if not food_items:
            return "No food items found in the receipt to generate recipes."
        
        # Format food items for the prompt
        ingredients_text = "\n".join(f"- {item}" for item in food_items)
        return self.call_ollama_llm(ingredients_text, prompt_type="generate_recipe")

    def process_receipt(self, image_path: str, save_debug: bool = True, use_llm: bool = True) -> Dict[str, Any]:
        """
        Process a receipt image and extract its text.
        Args:
            image_path (str): Path to the receipt image
            save_debug (bool): Whether to save debug images
            use_llm (bool): Whether to use LLM for text refinement
        Returns:
            Dict[str, Any]: Dictionary containing raw and processed text
        """
        # Load image
        image = self.load_image(image_path)
        if image is None:
            raise ValueError(f"Could not load image from {image_path}")

        # Preprocess image
        processed_image = self.preprocess_image(image)

        # Save debug image if requested
        if save_debug:
            self.save_debug_image(processed_image, image_path)

        # Extract text
        raw_text = self.extract_text(processed_image)
        
        result = {
            "raw_text": raw_text,
            "refined_text": None,
            "food_items": [],
            "recipe_suggestions": None,
            "success": True,
            "error": None
        }

        # Use LLM to refine the text if requested
        if use_llm and raw_text.strip():
            try:
                # First, get refined receipt text
                refined_text = self.call_ollama_llm(raw_text, prompt_type="format_receipt")
                if refined_text:
                    result["refined_text"] = refined_text
                    
                    # Extract food items
                    food_items = self.extract_food_items(refined_text)
                    result["food_items"] = food_items
                    
                    # Generate recipe suggestions
                    if food_items:
                        recipe_suggestions = self.generate_recipe_suggestions(food_items)
                        result["recipe_suggestions"] = recipe_suggestions
                else:
                    result["error"] = "LLM processing failed"
            except Exception as e:
                result["success"] = False
                result["error"] = f"Error in LLM processing: {str(e)}"

        return result

def main():
    # Example usage
    ocr = ReceiptOCR()
    
    # Replace with your image path
    image_path = "test_images/sample_receipt.jpg"
    
    try:
        result = ocr.process_receipt(image_path)
        
        print("\nRaw OCR Text:")
        print("-" * 50)
        print(result["raw_text"])
        
        if result["refined_text"]:
            print("\nRefined Text (LLM Processed):")
            print("-" * 50)
            print(result["refined_text"])
        
        if result["food_items"]:
            print("\nIdentified Food Items:")
            print("-" * 50)
            for item in result["food_items"]:
                print(f"- {item}")
        
        if result["recipe_suggestions"]:
            print("\nRecipe Suggestions:")
            print("-" * 50)
            print(result["recipe_suggestions"])
        
        if result["error"]:
            print("\nError:")
            print("-" * 50)
            print(result["error"])
            
    except Exception as e:
        print(f"Error processing receipt: {e}")

if __name__ == "__main__":
    main() 