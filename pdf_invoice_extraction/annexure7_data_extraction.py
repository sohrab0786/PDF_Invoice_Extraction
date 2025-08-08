import re
import json
import pdfplumber
import openai
import io
import pytesseract
import pandas as pd
from PIL import Image
from app.config.config import Config
from pathlib import Path
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=Config.OPEN_AI_KEY)
openai.api_key = Config.OPEN_AI_KEY

# Set the Tesseract OCR path
pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

# Define target fields for output
TARGET_FIELDS = [
    "S No. #",
    "No. of Bill of Entry of the Applicant",
    "Date",
    "Name of Imported Part/ Component",
    "HSN Code of Imported Part/ Component",
    "CIF Value (Rs.)",
    "Quantity"
]

# Synonym map for matching business-relevant terms
SYNONYM_MAP = {
    "Bill of Entry No": "No. of Bill of Entry of the Applicant",
    "Invoice Date": "Date",
    "Date of Invoice": "Date",
    "Dated": "Date",
    "HS Code": "HSN Code of Imported Part/ Component",
    "HS Code of Item": "HSN Code of Imported Part/ Component",
    "CIF Value": "CIF Value (Rs.)",
    "Item": "Name of Imported Part/ Component",
    "Part Description": "Name of Imported Part/ Component",
    "Product Description": "Name of Imported Part/ Component",
    "Qty": "Quantity",
    "Quantity (pcs)": "Quantity"
}

# Validate and correct JSON if necessary
def validate_json(output):
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        #corrected_output = re.sub(r'(?<=:\s)(\d{5,})', r'"\1"', output)
        #corrected_output = re.sub(r'(?<=MC Number":\s)(\d+)', r'"\1"', corrected_output)
        try:
            return json.loads(output)
        except:
            return None
    return None

# Extract text from PDF (fallback to OCR)
def extract_pdf_text(pdf_bytes, max_pages=3):
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        max_pages = min(len(pdf.pages), max_pages)
        for page in pdf.pages[:max_pages]:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
            else:
                # OCR fallback
                img = page.to_image().original
                text += pytesseract.image_to_string(img) + "\n"
    return text.strip() if text else None

# Use GPT to extract data
def process_with_openai(text):
    if not text:
        return None

    synonym_info = "\n".join([f'- "{k}" = "{v}"' for k, v in SYNONYM_MAP.items()])
    prompt = f"""
You are a smart data extraction assistant. Extract the following fields from invoice text and return a valid JSON object.

If any fields are not found or unclear, set their values to null.
Use synonyms based on business context. Here are common mappings:
{synonym_info}

Required fields:
- "S No. #"
- "No. of Bill of Entry of the Applicant"
- "Date"
- "Name of Imported Part/ Component"
- "HSN Code of Imported Part/ Component"
- "CIF Value (Rs.)"
- "Quantity"

Extract from:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You extract structured JSON data from invoice text using business-aware synonym matching."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0
        )
        raw = response.choices[0].message.content.strip().replace("\n", " ")
        return validate_json(raw)
    except Exception as e:
        print(f"⚠️ OpenAI API failed: {e}")
        return None

# Normalize the fields based on synonym map
def normalize_fields(data):
    normalized = {field: None for field in TARGET_FIELDS}
    for key, value in data.items():
        if key in TARGET_FIELDS:
            normalized[key] = value
        elif key in SYNONYM_MAP and SYNONYM_MAP[key] in TARGET_FIELDS:
            normalized[SYNONYM_MAP[key]] = value
    return normalized

# Extract and process single PDF
def extract_data_by_openAI(pdf_bytes):
    pdf_text = extract_pdf_text(pdf_bytes, max_pages=3)
    if not pdf_text:
        return {field: None for field in TARGET_FIELDS}
    json_output = process_with_openai(pdf_text)
    if json_output and isinstance(json_output, dict):
        return normalize_fields(json_output)
    else:
        return {field: None for field in TARGET_FIELDS}

# === MAIN SCRIPT ===
all_data = []

def process_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        pdf_bytes = file.read()
    result = extract_data_by_openAI(pdf_bytes)
    result["S No. #"] = None  # placeholder for serial number
    result["__file__"] = str(pdf_path.name)
    all_data.append(result)
    print(f"✅ Processed: {pdf_path}")

if __name__ == "__main__":
    folder = r"new_data_07_07_2025/GST Invoices"
    pdf_files = list(Path(folder).glob("*.pdf"))

    print(f"📁 {folder} - {len(pdf_files)} files found\n{'='*60}")
    for pdf_file in pdf_files:
        process_pdf(pdf_file)

    if all_data:
        df = pd.DataFrame(all_data)
        df["S No. #"] = range(1, len(df) + 1)
        df = df[TARGET_FIELDS + ["__file__"]]  # Enforce order + file name
        df.to_excel("extracted_invoices_annexure723.xlsx", index=False)
        print("\n✅ All data saved to: extracted_invoices_annexure723.xlsx")
    else:
        print("\n⚠️ No data extracted.")
