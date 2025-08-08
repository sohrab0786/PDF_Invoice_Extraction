Use Case- use to extract invoice informations from the Invoice.pdf 

Clone this repo and configure it then run the pdf_invoice_extraction/openai_extract_pdf.py
1. git clone https://github.com/sohrab0786/PDF_Invoice_Extraction.git
2. cd PDF_Invoice_Extraction.git
3. create venv and activate it 
4. install requirements pip install -r requirements.txt
5. install tesseract and check its version then put its path in openai_extract_pdf.py and in Config.py give openai api key 
6. put pdf in required folder inside the new_data_07_07_2025/GST Invoices
7. run the code python openai_extract_pdf.py
