# Placeholder: statement_analyzer/pdf_extractor.py
# YOU NEED TO IMPLEMENT THIS BASED ON YOUR PDF EXTRACTION TECHNIQUE.

# Example: If you are using a library like PyPDF2 or pdfplumber
# import PyPDF2 # or other relevant library

from pathlib import Path
import sys # For better error output
import sys
import re
from pathlib import Path
from typing import List
import tempfile
import pdfplumber
import os
import re
import json
import fitz
from io import BytesIO
# --- Assuming these imports from docling are correct ---
from .data_extractor import BankStatementParser
from .enhancement import enhancement_logic
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    PipelineOptions,
    EasyOcrOptions,
    TesseractCliOcrOptions,
    RapidOcrOptions
    # Keep other OCR options commented out
    # TesseractOcrOptions, RapidOcrOptions, OcrMacOptions
)

from docling.document_converter import (
    ConversionResult,
    DocumentConverter,
    InputFormat,
    PdfFormatOption,
    ImageFormatOption
)


from pdf2image import convert_from_bytes
from PIL import Image
import os
import uuid
import json

DOCLING_AVAILABLE = True  # Make sure this is properly managed in your actual code






# def run_layout_aware_ocr(pdf_file_obj, output_dir="output"):
#     # Convert PDF bytes to PIL Images
#     images = convert_from_bytes(pdf_file_obj.read())
#
#     # Initialize PaddleOCR
#     ocr = PaddleOCR(use_angle_cls=True, lang='en')

#     # ✅ Use PaddleDetectionLayoutModel instead of Detectron2
#     model = lp.PaddleDetectionLayoutModel(
#         model_path='lp://ppyolov2_r50vd_dcn_365e_publaynet',
#         label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
#         enforce_cpu=True
#     )

#     os.makedirs(output_dir, exist_ok=True)
#     final_results = []

#     for i, image in enumerate(images):
#         layout = model.detect(image)
#         image_results = []

#         for block in layout:
#             if block.type in ["Text", "Title", "List"]:
#                 segment = image.crop(block.coordinates)
#                 segment_path = os.path.join(output_dir, f"page_{i+1}_{uuid.uuid4().hex}.png")
#                 segment.save(segment_path)

#                 result = ocr.ocr(segment_path)
#                 os.remove(segment_path)

#                 for line in result:
#                     for word in line:
#                         text = word[1][0]
#                         bbox = word[0]
#                         image_results.append({
#                             "text": text,
#                             "bbox": bbox,
#                             "block_type": block.type
#                         })

#         # Save per-page JSON
#         output_json = os.path.join(output_dir, f"page_{i+1}_layout_ocr.json")
#         with open(output_json, "w") as f:
#             json.dump(image_results, f, indent=2)

#         final_results.append(image_results)
#         print(final_results)

    # return final_results

def is_image_based_pdf(uploaded_file, text_threshold=50):
    file_buffer = BytesIO(uploaded_file.read())
    doc = fitz.open(stream=file_buffer, filetype="pdf")

    total_text_chars = 0
    total_images = 0

    for page in doc:
        text = page.get_text().strip()
        total_text_chars += len(text)
        total_images += len(page.get_images(full=True))

    uploaded_file.seek(0)  # Reset for reuse

    if total_text_chars < text_threshold and total_images > 0:
        return True  # Likely image-based
    else:
        return False  # Likely text-based or hybrid

def extract_data_from_pdf_2(uploaded_file_object):
    """
    Extracts data from the uploaded PDF file using Docling and RapidOCR.
    Args:
        uploaded_file_object: An in-memory file object from Django's request.FILES.
    Returns:
        Extracted markdown text as string, or None if extraction fails.
    """
    print("Starting PDF extraction...", uploaded_file_object)

    is_image_only = is_image_based_pdf(uploaded_file_object)

    if is_image_only:
        raw_text = extract_data_from_pdf(uploaded_file_object)
    else:
        raw_text = extract_using_pdfplumber(uploaded_file_object)
    # updated_file_object = enhancement_logic(uploaded_file_object)  # Enhance the PDF if needed (e.g., fix skew)
    # raw_text =extract_using_pdfplumber(uploaded_file_object)  # Extract text using pdfplumber for initial analysis
    # if not raw_text:
    # raw_text = extract_data_from_pdf(uploaded_file_object)  # Call the main extraction function
    print("raw text :############# \n", raw_text)
    # extracted_data = BankStatementParser().extract_transactions_gpt(raw_text)  # Use the BankStatementParser to extract transactions
    # print("Extracted Data:#############", extracted_data)
    return raw_text
    # # run_layout_aware_ocr(uploaded_file_object)  # Run OCR on the PDF file
    # # Save the in-memory uploaded file to a temporary file

def extract_using_pdfplumber(uploaded_file_object):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(uploaded_file_object.read())
        temp_path = temp_file.name

    input_path = Path(temp_path)
    with pdfplumber.open(input_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text(layout=True) + "\n"
        print("text from plumber ", text)
        return text


def extract_data_from_pdf(uploaded_file_object):
    """
    Extracts data from the uploaded PDF file using Docling and RapidOCR.
    Args:
        uploaded_file_object: An in-memory file object from Django's request.FILES.
    Returns:
        Extracted markdown text as string, or None if extraction fails.
    """
    print("Starting PDF extraction...", uploaded_file_object)
    try:
        # Save the in-memory uploaded file to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(uploaded_file_object.read())
            temp_path = temp_file.name

        input_path = Path(temp_path)
        suffix = input_path.suffix.lower()
        format_options = {}
        input_format = None
        pipeline_options_instance = None

        if suffix == '.pdf':
            input_format = InputFormat.PDF
            pipeline_options_instance = PdfPipelineOptions()
            format_options[InputFormat.PDF] = PdfFormatOption(pipeline_options=pipeline_options_instance)
            print(f"Detected PDF input: {input_path}", file=sys.stderr)
        else:
            print(f"Unsupported file format: {suffix}", file=sys.stderr)
            return None

        pipeline_options_instance.do_ocr = True
        pipeline_options_instance.do_table_structure = True

        if hasattr(pipeline_options_instance, 'table_structure_options') and pipeline_options_instance.table_structure_options is not None:
            pipeline_options_instance.table_structure_options.do_cell_matching = True

        ocr_options = RapidOcrOptions(force_full_page_ocr=False)
        pipeline_options_instance.ocr_options = ocr_options

        converter = DocumentConverter(format_options=format_options)
        conversion_result = converter.convert(input_path)
        doc = conversion_result.document

        if doc:
            # print(f"Docling extracted data \n", doc.export_to_markdown())
            return doc.export_to_markdown()
        else:
            print("Docling returned empty document.", file=sys.stderr)
            return None

    except Exception as e:
        print(f"Error in PDF extraction: {e}", file=sys.stderr)
        return None



def extract_transactions_from_text(text):
    """
    Extracts structured transaction records from raw bank statement text (e.g., from pdfplumber).
    Assumes multiline string input.
    """
    # Normalize extra spaces
    text = re.sub(r'[ ]{2,}', ' ', text)
    lines = text.split('\n')

    transactions = []

    # Regex to capture one full transaction line
    pattern = re.compile(
        r'(\d{2}-\d{2}-\d{4})\s+'            # date
        r'(.+?)\s+'                          # details
        r'(nan|\S+)\s+'                      # cheque number
        r'(\d{2}-\d{2}-\d{4})\s+'            # value date
        r'(nan|\d+\.\d+)\s+'                 # withdrawal
        r'(nan|\d+\.\d+)\s+'                 # deposit
        r'(\d+)'                             # balance
    )

    for line in lines:
        match = pattern.match(line.strip())
        if match:
            date, details, cheque_no, value_date, withdrawal, deposit, balance = match.groups()
            transactions.append({
                "date": date,
                "details": details.strip(),
                "cheque_no": cheque_no or "nan",
                "value_date": value_date,
                "withdrawal": withdrawal if withdrawal != "nan" else "nan",
                "deposit": deposit if deposit != "nan" else "nan",
                "balance": balance
            })

    return transactions



def clean_and_structure_data(raw_text_data):
    """
    Cleans the raw extracted text and converts important fields into a
    list of dictionaries (or your desired data structure).
    Args:
        raw_text_data: The string output from extract_data_from_pdf.
    Returns:
        A list of dictionaries, where each dictionary represents a transaction.
        Example: [{'date': 'YYYY-MM-DD', 'description': '...', 'debit': 0.0, 'credit': 0.0, 'running_balance': 0.0}, ...]
        Return an empty list if no data can be structured.
    """
    transactions = []
    if not raw_text_data or not isinstance(raw_text_data, str):
        return []

    lines = raw_text_data.strip().split('\n')
    if len(lines) <= 1: # Only header or no data
        print("Cleaner: Not enough lines to process.")
        return []
        
    # Dynamically find header, assuming first non-empty line is header
    header_line = ""
    data_lines_start_index = 0
    for i, line in enumerate(lines):
        if line.strip(): # Found first non-empty line
            header_line = line
            data_lines_start_index = i + 1
            break
    
    if not header_line:
        print("Cleaner: No header line found.")
        return []

    # Normalize header names (example: "Date", "Transaction Details", "Withdrawals", "Deposits", "Running Balance")
    # This part is VERY bank-specific and needs robust parsing.
    # For simplicity, assuming CSV-like structure from the dummy data.
    header = [h.strip().lower() for h in header_line.split(',')]
    print(f"Cleaner: Detected Headers: {header}")

    # --- YOUR DATA CLEANING AND STRUCTURING LOGIC HERE ---
    # This needs to be robust to handle variations in PDF text output.
    # Consider using regex, string manipulation, or more advanced parsing.
    
    expected_headers = ['date', 'description', 'debit', 'credit', 'balance'] # Adjust to your actual needs
    # Simple check if essential headers are present
    if not all(eh in header for eh in ['date', 'balance']): # At least date and balance should be there
        print(f"Cleaner: Essential headers ('date', 'balance') not found in {header}")
        # return [] # Or try to infer columns

    for line_number, line_content in enumerate(lines[data_lines_start_index:], start=data_lines_start_index):
        if not line_content.strip(): # Skip empty lines
            continue
            
        values = [v.strip() for v in line_content.split(',')]
        
        if len(values) == len(header): # Basic check for column count
            try:
                transaction_dict = {}
                # Try to map values based on header names
                for i, col_name in enumerate(header):
                    # Basic normalization, you might need more complex mapping
                    if 'date' in col_name: transaction_dict['date'] = values[i]
                    elif 'desc' in col_name: transaction_dict['description'] = values[i]
                    elif 'debit' in col_name or 'withdraw' in col_name:
                        transaction_dict['debit'] = float(values[i]) if values[i] else 0.0
                    elif 'credit' in col_name or 'deposit' in col_name:
                        transaction_dict['credit'] = float(values[i]) if values[i] else 0.0
                    elif 'bal' in col_name:
                        transaction_dict['running_balance'] = float(values[i]) if values[i] else 0.0
                
                # Ensure all core fields exist, even if with default values
                transaction = {
                    'date': transaction_dict.get('date', 'N/A'),
                    'description': transaction_dict.get('description', 'N/A'),
                    'debit': transaction_dict.get('debit', 0.0),
                    'credit': transaction_dict.get('credit', 0.0),
                    'running_balance': transaction_dict.get('running_balance', 0.0) # Default to 0 if not found
                }
                
                # A basic validation: if running_balance is crucial and missing, skip
                if 'running_balance' not in transaction_dict and not transaction.get('running_balance'):
                    print(f"Cleaner: Skipping row due to missing balance: {line_content}")
                    continue

                transactions.append(transaction)
            except ValueError as e:
                print(f"Cleaner: Skipping row due to data conversion error: '{line_content}' - {e}")
            except IndexError:
                print(f"Cleaner: Skipping row due to column mismatch: '{line_content}'")
        else:
            print(f"Cleaner: Skipping row due to unexpected number of columns: '{line_content}' (expected {len(header)}, got {len(values)})")
            
    print(f"Cleaner: Structured {len(transactions)} transactions.")
    return transactions