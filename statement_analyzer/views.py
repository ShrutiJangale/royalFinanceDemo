from io import BytesIO
import json
import base64
from PIL import Image # Make sure Pillow is installed: pip install Pillow
from django.shortcuts import render
from django.conf import settings
from pymongo import MongoClient, errors as pymongo_errors
from .forms import UploadFileForm
from pdf2image import convert_from_bytes, exceptions
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


from .data_extractor import BankStatementParser
# from .fraud_detector import detect_fraud_from_bank_images  # your GPT-based analyzer

import io
import traceback

# --- Import your custom scripts (adjust paths/names as needed) ---
# Option 1: If they are simple .py files in the same directory
from . import pdf_extractor
from . import transaction_verifier

# Option 2: If they are structured as modules or you prefer explicit calls
# import statement_analyzer.pdf_extractor as pdf_extractor_module
# import statement_analyzer.transaction_verifier as transaction_verifier_module


# --- Helper function to connect to MongoDB ---
def get_mongo_collection():
    try:
        client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000) # Added timeout
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster') # Verify connection
        db = client[settings.MONGO_DATABASE_NAME]
        collection = db[settings.MONGO_COLLECTION_NAME]
        return collection
    except pymongo_errors.ServerSelectionTimeoutError as err:
        # Handle connection error to MongoDB
        print(f"MongoDB Connection Error: {err}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred with MongoDB connection: {e}")
        return None

# def upload_and_analyze_statement(request):
#     form = UploadFileForm()
#     result_message = None
#     error_message = None
#     doctored_transactions_list = []

#     if request.method == 'POST':
#         form = UploadFileForm(request.POST, request.FILES)
#         if form.is_valid():
#             uploaded_file = request.FILES['file']

#             # --- 0. Basic File Check (Optional but good) ---
#             # if not uploaded_file.name.lower().endswith('.pdf'):
#             #     error_message = "Invalid file type. Please upload a PDF file."
#             #     return render(request, 'statement_analyzer/upload_statement.html', {
#             #         'form': form, 'error': error_message
#             #     })

#             try:
#                 # --- 1. PDF Extraction (Using your script) ---
#                 # Assuming your pdf_extractor.py has a function like `extract_data_from_pdf`
#                 # that takes a file object.
#                 final_data = pdf_extractor.extract_data_from_pdf_2(uploaded_file)
#                 # Example: raw_text_data = pdf_extractor_module.your_function(uploaded_file)

#                 if not final_data: # Check if extraction yielded anything
#                     error_message = "Could not extract text from the PDF. It might be empty or an image-based PDF without OCR."
#                     # No point proceeding if no raw data
#                     return render(request, 'statement_analyzer/upload_statement.html', {
#                         'form': form, 'error': error_message
#                     })

#                 # --- 2. Data Cleaning and Structuring ---
#                 # Assuming your pdf_extractor.py (or another script) also has a function
#                 # to clean and structure this raw text.
#                 # For this example, let's say it's also in pdf_extractor.
#                 # structured_transactions = pdf_extractor.clean_and_structure_data(raw_text_data)
#                 # transaction_new = pdf_extractor.extract_transactions_from_text(raw_text_data) # If you have a specific function for this
#                 # # Example: structured_transactions = data_parser_module.your_function(raw_text_data)
#                 # print("Parsed Transactions: ", transaction_new)

#                 # if not transaction_new:
#                 #     error_message = "Could not structure any transactions from the extracted data. Please check the PDF content and format."
#                 # else:
#                 #     # --- 3. Store in MongoDB ---
#                 #     collection = get_mongo_collection()
#                 #     if collection is None:
#                 #         message = "Database connection failed. Please try again later."
#                 #         print(message)

#                     # Optional: Clear previous data for this user/statement if needed
#                     # collection.delete_many({'statement_id': some_unique_id_for_this_upload})
                    
#                     # Add a unique upload ID to each transaction if you want to group them
#                     # import uuid
#                     # upload_id = str(uuid.uuid4())
#                     # for t in structured_transactions:
#                     #    t['upload_id'] = upload_id

#                     # insert_result = collection.insert_many(list(transaction_new)) # Ensure it's a list
#                     # You might want to confirm insert_result.inserted_ids count matches

#                     # --- 4. Run Verification Logic ---
#                     # Pass the structured_transactions (which are now also in DB)
#                     # to your verification script.
#                     # Ensure your verifier can handle the exact structure.
#                 all_good, flagged_entries = transaction_verifier.verify_transactions(final_data.get('transactions', [])) # Adjust based on your actual data structure

#                 if all_good:
#                     result_message = "All good, check passed!"
#                 else:
#                     result_message = "Edited/Doctored statement suspected."
#                     doctored_transactions_list = flagged_entries

#             except FileNotFoundError: # If your script expects a path and can't find it
#                 error_message = "Error: A required file for processing was not found."
#                 # Log the details for yourself
#             except IsADirectoryError: # If a file operation was attempted on a directory
#                 error_message = "Error: Expected a file but found a directory during processing."
#             except Exception as e:
#                 error_message = f"An unexpected error occurred during processing: {str(e)}"
#                 # It's good to log the full traceback for debugging
#                 import traceback
#                 print(f"Error in upload_and_analyze_statement: {e}")
#                 traceback.print_exc()

#     return render(request, 'statement_analyzer/upload_statement.html', {
#         'form': form,
#         'result': result_message,
#         'error': error_message,
#         'doctored_transactions': doctored_transactions_list
#     })



def upload_and_analyze_statement(request):
    form = UploadFileForm()
    result_message = None
    error_message = None
    fraud_issues = []
    # dummy_data = r"C:\Fraud_detection\bankstatement_project\statement_analyzer\dummy_data.json"
    # with open(dummy_data ,"r") as f:
    #     extracted_data = json.load(f)
    
    # extracted_data = {'account_info': {'bank_name': 'Nedbank', 'branch_code': 'null', 'branch_address': 'null', 'holder_name': 'MR GEORGE VAN DEVENTER', 'account_number': '1285935551', 'period': '18/12/2024 - 18/01/2025', 'final_balance': 43.57}, 'transactions': [{'id': 1, 'details': 'Openingbalance', 'date': '19-12-2024', 'amount': 0.0, 'balance': 2649.13}, {'id': 2, 'details': 'Prepaid electricity for George', 'date': '19-12-2024', 'amount': -50.0, 'balance': 2599.13}, {'id': 3, 'details': 'SASOL DAVEST 518103XXXXXX0883', 'date': '19-12-2024', 'amount': -312.0, 'balance': 2287.13}, {'id': 4, 'details': 'S2S*FRANCISLIQ518103XXXXXX0883', 'date': '19-12-2024', 'amount': -121.0, 'balance': 2166.13}, {'id': 5, 'details': 'S2S*FRANCISLIQ518103XXXXXX0883', 'date': '19-12-2024', 'amount': -40.0, 'balance': 2126.13}, {'id': 6, 'details': 'Instant payment fee', 'date': '19-12-2024', 'amount': -10.0, 'balance': 2116.13}, {'id': 7, 'details': 'SS-AFRIMOB32053900827024241220', 'date': '20-12-2024', 'amount': -582.95, 'balance': 1533.18}, {'id': 8, 'details': 'Prepaid electricity for George', 'date': '20-12-2024', 'amount': -50.0, 'balance': 1483.18}, {'id': 9, 'details': 'CORGI HARDWARE518103XXXXXX0883', 'date': '20-12-2024', 'amount': -286.5, 'balance': 1196.68}, {'id': 10, 'details': 'HPY*SA FRIENDL518103XXXXXX0883', 'date': '20-12-2024', 'amount': -100.0, 'balance': 1096.68}]}
    extracted_data = {}
    transactions_extracted = False  # Flag to indicate if transactions were extracted
    

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
    if form.is_valid():
        uploaded_file = request.FILES['file']

        try:
            # --- Read file content once ---
            file_bytes = uploaded_file.read()

            # Encode the bytes to Base64
            encoded_file_bytes = base64.b64encode(file_bytes).decode('utf-8')
            # Store the Base64 encoded string in the session
            request.session['file_bytes'] = encoded_file_bytes
            if not extracted_data:
                extracted_text = pdf_extractor.extract_data_from_pdf_2(BytesIO(file_bytes))
                extracted_data = BankStatementParser().extract__from_text_transactions_gpt(extracted_text)
            # request.session['fraud_issues'] = []
            if 'fraud_issues' in request.session:
                value = request.session.pop('fraud_issues')
            print(f"Extracted Data: {extracted_data}")


            # --- 3. Store extracted transaction data ---
            if extracted_data:
                request.session['extracted_transactions_data'] = extracted_data
                transactions_extracted = True
            else:
                error_message = "Failed to extract transaction data."

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_message = f"An unexpected error occurred: {str(e)}"

    # in_progress = request.session.get('in_progress', False)
    return render(request, 'statement_analyzer/new_viewer.html', {
        'form': form,
        # 'result': result_message,
        'error': error_message,
        # 'fraud_issues': fraud_issues,
        'transactions_extracted': transactions_extracted, # Pass this to the template
        # 'in_progress': in_progress,
    })

def view_transactions_data(request):
    """
    Renders the extracted account information and transactions in a table.
    Retrieves data from the session.
    """
    extracted_data = request.session.get('extracted_transactions_data')

    if not extracted_data:
        # Handle case where no data is found (e.g., user navigated directly or session expired)
        error_message = "No transaction data found. Please upload and analyze a statement first."
        return render(request, 'statement_analyzer/transaction_viewer.html', {'error': error_message})

    account_info = extracted_data.get('account_info', {})
    transactions = extracted_data.get('transactions', [])
    _, transactions = transaction_verifier.verify_transactions(transactions)
    print(f"Extracted Data in view_transactions_data: {transactions}")


    return render(request, 'statement_analyzer/transaction_viewer.html', {
        'account_info': account_info,
        'transactions': transactions,
    })


@csrf_exempt
def revalidate_transactions(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        print("found the edited data \n", data)
        transactions = data.get('transactions', [])

        # Revalidate
        _, transactions = transaction_verifier.verify_transactions(transactions)

        #  Update the session with new values
        extracted_data = request.session.get('extracted_transactions_data', {})
        extracted_data['transactions'] = transactions
        request.session['extracted_transactions_data'] = extracted_data
        request.session.modified = True  # Force save

        return JsonResponse(transactions, safe=False)



def view_other_issue(request):
    """
    Renders the extracted account information and transactions in a table.
    Retrieves data from the session.
    """
    # Retrieve the SINGLE Base64 encoded string from the session
    fraud_issues = request.session.get('fraud_issues', [])
    print("fraud issue from cache ", fraud_issues)
    if fraud_issues:
        if fraud_issues != "N/A":
            return render(request, 'statement_analyzer/doctored.html', {
            'result': f"Found {len(fraud_issues)} issues with this statement",
            'fraud': fraud_issues,
        })

        else:
            return render(request, 'statement_analyzer/doctored.html', {
            'result': f"Found {len(fraud_issues)} issues with this statement",
            'fraud': [],
        })

    else:

        encoded_pdf_bytes_str = request.session.get('file_bytes')

        # Initialize list for PIL images (this will be populated by BankStatementParser)
        pil_images_list = [] 

        # --- Step 1: Handle the case where no data is found in the session initially ---
        if not encoded_pdf_bytes_str:
            result_message = "No statement data found in session. Please upload a statement first."
            # Render doctored.html with a clear message and an empty fraud list
            return render(request, 'statement_analyzer/doctored.html', {'result': result_message, 'fraud': []})

        pdf_bytes = None
        try:
            # 2. Base64 decode the SINGLE string back to raw PDF bytes
            # The .encode('utf-8') is crucial here to convert the string back to bytes for b64decode
            pdf_bytes = base64.b64decode(encoded_pdf_bytes_str.encode('utf-8'))
        except Exception as e:
            print(f"Error decoding Base64 PDF data from session: {e}")
            result_message = "Corrupted statement data found in session. Please re-upload."
            return render(request, 'statement_analyzer/doctored.html', {'result': result_message, 'fraud': []})

        # Ensure PDF bytes were successfully decoded
        if not pdf_bytes:
            result_message = "Failed to retrieve statement data. Please re-upload."
            return render(request, 'statement_analyzer/doctored.html', {'result': result_message, 'fraud': []})

        try:
            pil_images_list = convert_from_bytes(pdf_bytes, fmt='PNG')
            
        except Exception as e:
            print(f"Error converting PDF bytes to PIL images: {e}")
            result_message = "Error processing document for image extraction. Please check document format."
            return render(request, 'statement_analyzer/doctored.html', {'result': result_message, 'fraud': []})


        # Now, pil_images_list should be a list of PIL.Image objects
        if not pil_images_list:
            result_message = "No images could be extracted from the provided statement."
            return render(request, 'statement_analyzer/doctored.html', {'result': result_message, 'fraud': []})


        # Pass the list of PIL Image objects to your parser
        fraud_issues = BankStatementParser().detect_fraud_from_bank_images(pil_images_list)
        # fraud_issues = BankStatementParser().detect_frauds(pil_images_list)

        print(f"Extracted Data in view_other_issue: {fraud_issues}")
        result_message = f"Found {len(fraud_issues)} issues with this statement"
        if not len(fraud_issues):
            request.session['fraud_issues'] = "N/A"
        else:
            request.session['fraud_issues'] = fraud_issues

        return render(request, 'statement_analyzer/doctored.html', {
            'result': result_message,
            'fraud': fraud_issues,
        })