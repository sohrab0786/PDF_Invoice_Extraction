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
    "PLI Request No",
    "IFCI No",
    "File Name",
    "invoice issued to",
    "invoice issued to GSTIN",
    "#",
    "IRN#",
    "Invoice#",
    "Date",
    "Name of Local Supplier",
    "GSTIN of Local Supplier",
    "Name of Part/Component",
    "HSN Code of Part/Component",
    "Value (net of GST)(Rs.)",
    "Quantity",
    "Value per piece (net of GST) (Rs.)"
]
# Synonym map for matching business-relevant terms
SYNONYM_MAP = {
    "IRN Number": "IRN#",
    "IRN No": "IRN#",
    "Invoice Number": "Invoice#",
    "Invoice No": "Invoice#",
    "Invoice Date": "Date",
    "Dated": "Date",
    "Name of Supplier": "Name of Local Supplier",
    "Supplier Name": "Name of Local Supplier",
    "GSTIN of Supplier": "GSTIN of Local Supplier",
    "HS Code": "HSN Code of Part/Component",
    "HS Code of Item": "HSN Code of Part/Component",
    "Part Description": "Name of Part/Component",
    "Product Description": "Name of Part/Component",
    "Qty": "Quantity",
    "QTY": "Quantity",
    "Net Value": "Value (net of GST)(Rs.)",
    "Value Without GST": "Value (net of GST)(Rs.)",
    "Unit Value": "Value per piece (net of GST) (Rs.)",
    "Rate per piece": "Value per piece (net of GST) (Rs.)"
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
- "PLI Request No"
- "IFCI No"
- "File Name"
- "invoice issued to"
- "invoice issued to GSTIN"
- "#"
- "IRN#"
- "Invoice#"
- "Date"
- "Name of Local Supplier"
- "GSTIN of Local Supplier"
- "Name of Part/Component"
- "HSN Code of Part/Component"
- "Value (net of GST)(Rs.)"
- "Quantity"
- "Value per piece (net of GST) (Rs.)"

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
        std_key = SYNONYM_MAP.get(key, key)
        if std_key in normalized:
            normalized[std_key] = value
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
    result["File Name"] = Path(pdf_path).name
    result["__file__"] = str(pdf_path.name)  # <-- This was missing

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
        df.to_excel("extracted_invoices_annexure6.xlsx", index=False)
        print("\n✅ All data saved to: extracted_invoices_annexure6.xlsx")
    else:
        print("\n⚠️ No data extracted.")
