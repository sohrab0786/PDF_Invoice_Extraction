import re
import json
import pdfplumber
import openai
import io
import pytesseract
from PIL import Image
from app.config.config import Config
from pathlib import Path
from openai import OpenAI
client = OpenAI(api_key=Config.OPEN_AI_KEY)
# Set the Tesseract OCR path
pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

# OpenAI API Key
openai.api_key = Config.OPEN_AI_KEY

import json
import re
def validate_json(output):
    """Validate and correct OpenAI's JSON response format."""
    try:
        return json.loads(output)  # Try loading JSON directly
    except json.JSONDecodeError as e:
        #print(f"JSON Decode Error: {e}\nRaw Response: {output}")

        # Fix common issue: Wrap unquoted large numbers in double quotes
        corrected_output = re.sub(r'(?<=:\s)(\d{5,})', r'"\1"', output)  

        # Fix potential leading zero issue in MC Number (prevents it from being treated as octal)
        corrected_output = re.sub(r'(?<=MC Number":\s)(\d+)', r'"\1"', corrected_output)

        # Try reloading the corrected JSON
        try:
            return json.loads(corrected_output)
        except json.JSONDecodeError as e:
            #print(f"Still Invalid JSON: {e}")
            return None  # Return None if still invalid

    return None  # If all attempts fail, return None


def extract_pdf_text(pdf_bytes, max_pages=3):
    """
    Extracts text from the first two pages of a PDF.
    If no text is found, applies OCR on images.
    """
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total_pages = len(pdf.pages)
        max_pages = min(total_pages, 3) 
        for i, page in enumerate(pdf.pages[:max_pages]):  # Process only first 3 pages
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
            else:
                # If no text is found, extract images and apply OCR
                img = page.to_image().annotated
                text += pytesseract.image_to_string(img) + "\n"

    return text.strip() if text else None  # Return None if no text is found

def process_with_openai(text):
    if not text:
        return None  # Avoid calling OpenAI with empty text

    response = client.chat.completions.create(
        model="gpt-4",  # or "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": "You are an assistant that extracts structured key-value pairs from text and returns a valid JSON object."},
            {"role": "user", "content": f"Extract key-value pairs from the following text and return a valid JSON object:\n\n{text}"}
        ],
        max_tokens=1000,
        temperature=0
    )

    raw_response = response.choices[0].message.content.strip()
    
    #print("\n===== OpenAI Raw Response =====\n", raw_response, "\n==============================")

    # Ensure response is cleaned before JSON validation
    raw_response = raw_response.replace("\n", " ").strip()

    # Validate JSON
    return validate_json(raw_response)

def extract_data_by_openAI(pdf_bytes):
    """
    Extracts key-value pairs from a PDF file (first two pages) and returns structured JSON.
    """
    pdf_text = extract_pdf_text(pdf_bytes, max_pages=3)  # Process only first 2 pages

    if not pdf_text:
        return json.dumps({"error": "No extractable text found in the pdf."})

    json_output = process_with_openai(pdf_text)
    
    if json_output and isinstance(json_output, dict):
        return json.dumps(json_output, indent=4)
    else:
        return json.dumps({"error": "Invalid JSON response from OpenAI"})

# Function to process a single PDF file
def process_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        pdf_bytes = file.read()
    
    result_json = extract_data_by_openAI(pdf_bytes)
    print(f"\nProcessed: {pdf_path}")
    print(result_json)
    print("=" * 80)  # Separator for readability

# Folder containing PDF files
if __name__ == "__main__":
    pdf_folder = r"new_data_07_07_2025/GST Invoices"
    # Iterate over all PDF files in the folder
    print(f'{pdf_folder} processing started')
    print(f'length of pdf_folder {len(list(Path(pdf_folder).glob("*.pdf")))}')
    for pdf_file in Path(pdf_folder).glob("*.pdf"):  # Searches for all .pdf files
        #print(f'processing file {pdf_file}')
        process_pdf(pdf_file)