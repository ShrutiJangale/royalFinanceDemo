#!/usr/bin/env python3
"""
Bank Statement Transaction Extractor
This script uses Claude API to extract transaction data from bank statements
and generates an HTML interface with Excel download functionality.
"""
import cv2
import numpy as np
from PIL import Image
import json
import ast
import re
import os
import base64
import io
from typing import List, Dict, Any, Tuple
from openai import OpenAI
import google.generativeai as genai
from tiktoken import encoding_for_model


from PIL import Image

from dotenv import load_dotenv

load_dotenv()
OPENAI_KEY=os.getenv("KEY_OPENAI")
GEMINI_KEY=os.getenv("GEMINI_API_KEY")
OPEN_AI_MODEL = os.getenv("OPEN_AI_MODEL")
MAX_TOKEN_LIMIT = int(os.getenv("MAX_TOKEN_LIMIT"))  # Default to 4096 if not set


client = OpenAI(api_key=OPENAI_KEY)
genai.configure(api_key=GEMINI_KEY)


class BankStatementParser:
    def __init__(self):
        """
        Initialize the BankStatementParser.
        """
        self.combined_prompt = """
        You are a financial auditing and data extraction AI.

        Your task is twofold:
        1. **Fraud Detection:** Analyze the bank statement images and report any:
        - formatting anomalies (weird spacing, fonts, alignment)
        - duplicate or missing transactions
        - any other visual fraud signs

        ➤ Return fraud issues in this format:
        "fraud_details": [
            {
            "issue_type": "formatting_anomaly | duplicate_transaction | missing_transaction | other",
            "description": "Explanation of the issue",
            "related_transaction_image_snippet": "Visible text around the issue (or null)"
            }
        ]

        2. **Transaction Extraction:** Extract structured transaction info:
        Ensure:
        - All monetary values must be parsed as clean float numbers, using proper positive or negative signs (e.g., 1200.50, -450.75), and must not include any symbols, commas, or placeholders like '-' or 'Rs.'.
        - Credit values are the positive amount added to customers account(e.g., money received or deposit or money in or Deposites).
        - Debit values are negative amount taken out from customers account (e.g., money paid or withdrawn or Money out or Payments).
        - Even if the original labels vary (e.g., "deposit", "withdrawn", "payment", "added", "subtracted"), identify the correct type.
        - Combine credit and debit into a single "amount" field with correct sign.
        - Balance values must always be returned as float numbers with an explicit sign:
            1) A positive balance must be returned as it is (e.g., 1025.50). If the balance has a suffix like "Cr" or prefix "+", it is positive amount.
            2) A negative balance must include a "-" sign (e.g., -450.75). If the balance has a suffix like "Dr" or prefix "-", it is negative (-) amount.
            3) Never omit the negative sign in negative balance (e.g., 1025.50 → ❌, -1025.50 → ✅)
        - Use best judgment if labels are missing or ambiguous. Understand the suffix or prefix of amounts , it might be a currency symbol or a +/- sign or under a different context.


        ➤ Return extracted data in the following structure:
        "extracted_data": {
            "account_info": {
            "holder_name": "string",
            "account_number": "string",
            "period": "string",
            "final_balance": float
            },
            "transactions": [
            {
                "id": "string or integer",
                "details": "string",
                "date": "DD-MM-YYYY",
                "amount": float,
                "balance": float
            }
            ]
        }

        Respond only with a valid JSON object like:
        {
        "fraud_details": [...],
        "extracted_data": {...}
        }
        
        Ensure the JSON is valid and does not contain markdown or explanations.
        """

    def extract_transactions_gemini(self, statement_text: str):
        """
        Extracts transaction data from bank statement text using the Gemini API and returns cleaned float values.
        """
        prompt = f"""
        You are an intelligent financial data extraction engine. Your task is to extract structured transaction data from the provided bank statement text.

        Here are the strict rules for extraction and formatting:
        1.  **Monetary Values**: All monetary values (e.g., credit , debit, balances) must be parsed as **clean float numbers**.
            * Do NOT include any currency symbols (like '₹', '$'), commas (','), or placeholders ('-').
            * Credit values are positive (e.g., 1200.50). These represent money received, deposits, or money coming into the account.
            * Debit values are negative (e.g., -450.75). These represent money paid, withdrawals, or money going out of the account.
            * Combine credit and debit into a single "amount" field with the correct positive or negative sign.
        2.  **Balance Values**: Always return balances as float numbers with an explicit sign.
            * Positive balances (e.g., 1025.50) should be returned as is. If a balance has a "Cr" suffix or "+" prefix, it's positive.
            * Negative balances (e.g., -450.75) **must** include a "-" sign. If a balance has a "Dr" suffix or "-" prefix, it's negative.
            * Never omit the negative sign for negative balances.
        3.  **JSON Format - CRITICAL**:
            * The entire response **must be a single JSON object**.
            * **All keys and all string values MUST be enclosed in double quotes (`"`).**
            * **DO NOT use single quotes (`'`).**
            * **DO NOT include any text, explanations, or markdown formatting (like ```json) before or after the JSON object.**

        Strict JSON schema to follow for the response:
        {{
            "account_info": {{
                "holder_name": "string",
                "account_number": "string",
                "period": "string",
                "final_balance": "float"
            }},
            "transactions": [
                {{
                    "id": "integer",
                    "details": "string",
                    "date": "DD-MM-YYYY",
                    "amount": "float",
                    "balance": "float"
                }}
            ]
        }}

        The Raw extracted text of the bank statement to process is below:
        ---
        {statement_text}
        ---
        """

        model = genai.GenerativeModel(model_name="gemini-1.5-flash")

        try:
            response = model.generate_content(prompt)
            content = response.text

            # Robust cleanup: Remove any leading/trailing whitespace and common markdown enclosures
            content = content.strip()
            if content.startswith("```json"):
                content = content[len("```json"):].strip()
            if content.endswith("```"):
                content = content[:-len("```")].strip()

            # Attempt to parse the JSON. This is where your error usually occurs.
            data = json.loads(content)

            return data

        except json.JSONDecodeError as e:
            print(f"JSON Decoding Error in extract_transactions_gemini: {e}")
            print(f"Problematic content around error: {content[max(0, e.pos-50):min(len(content), e.pos+50)]}")
            print("Full problematic content:")
            print(content)
            return None
        except Exception as e:
            print(f"An unexpected error occurred in extract_transactions_gemini: {e}")
            return None

    def process_bank_statement(self, images: List[Image.Image]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        try:
            messages = [{
                "role": "user",
                "content": [{"type": "text", "text": self.combined_prompt}]
            }]

            for img in images:
                messages[0]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": self.image_to_base64_data_uri(img),
                        "detail": "high"
                    }
                })

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=4000,
                temperature=0.2
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
                content = re.sub(r"```$", "", content).strip()

            result = json.loads(content)
            fraud_details = result.get("fraud_details", [])
            extracted_data = result.get("extracted_data", {})

            return fraud_details, extracted_data

        except Exception as e:
            print(f"Error during unified processing: {e}")
            return [], {}

    def detect_visual_anomalies_opencv(self, img_pil: Image.Image) -> List[Dict[str, Any]]:
        import base64
        from io import BytesIO

        img_gray = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(img_gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        anomalies = []
        img_np = np.array(img_pil)

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 25 < w < 250 and 10 < h < 50:
                # Crop the region from the original color image
                snippet_np = img_np[y:y+h, x:x+w]
                snippet_pil = Image.fromarray(snippet_np)

                # Convert cropped region to base64
                buffered = BytesIO()
                snippet_pil.save(buffered, format="PNG")
                encoded_snippet = base64.b64encode(buffered.getvalue()).decode("utf-8")
                base64_image = f"data:image/png;base64,{encoded_snippet}"

                anomalies.append({
                    "issue_type": "formatting_anomaly",
                    "description": f"Suspicious visual block at ({x},{y},{w},{h}) — possible tampering or masked text.",
                    "related_transaction_image_snippet": base64_image
                })

        return anomalies


    def detect_frauds(self, images: List[Image.Image]) -> List[Dict[str, Any]]:
        final_issues = []

        # 1. Visual issues from OpenCV
        for img in images:
            for issue in self.detect_visual_anomalies_opencv(img):
                final_issues.append({
                    "issue_type": issue["issue_type"],
                    "description": issue["description"],
                    "related_transaction_image_snippet": issue["related_transaction_image_snippet"],
                    "related_transaction_text_snippet": None
                })

        # 2. Contextual issues from GPT
        gpt_issues = self.detect_fraud_from_bank_images(images)
        for issue in gpt_issues:
            final_issues.append({
                "issue_type": issue["issue_type"],
                "description": issue["description"],
                "related_transaction_image_snippet": None,
                "related_transaction_text_snippet": issue.get("related_transaction_image_snippet")
            })

        return final_issues

    def detect_fraud_from_bank_images(self, images: List[Image.Image]) -> List[Dict[str, Any]]:
        """
        Uses GPT-4o with vision to deeply analyze bank statement images and detect signs of tampering, fraud, or anomalies.
        Returns a list of structured fraud issue reports as JSON objects.
        """
        system_prompt = (
            "You are a forensic financial auditor AI built to inspect bank statements for fraud, tampering, or inconsistencies. "
            "Your job is to visually analyze scanned or digital bank statement images with expert-level precision. "
            "Focus on detecting even the subtlest signs of manipulation, such as duplicated entries, altered figures, or misaligned formats. "
            "You must output only valid JSON — do not include markdown, explanations, or non-JSON text."
        )

        user_prompt = """
        Carefully review the attached bank statement images. Detect and report any:
        - Duplicate transactions (same timestamp, description, amount).
        - Missing or skipped transactions (unexpected gaps in balance progression).
        - Doctored entries: altered font, spacing inconsistencies, pasted text, pixel-level mismatches.
        - Anomalies in serial numbers, transaction IDs, or timestamps.
        - Evidence of layout tampering: overlapping characters, misalignments, reprinting.
        - Suspicious spending patterns (e.g. repeated identical transactions or amounts).
        - Any issue suggesting forgery, manipulation, or non-standard formatting.

        Output strictly in this JSON format:
        [
            {
                "issue_type": "duplicate_transaction | formatting_anomaly | missing_transaction | other",
                "description": "Detailed explanation of the suspicious observation.",
                "related_transaction_image_snippet": "Visible text near the issue, e.g., 'Prepaid electricity for George, 27/12/2024' or null if unclear"
            }
        ]

        Only return this JSON — no commentary, markdown, or explanation.
        """

        try:
            # Construct messages with system and user roles
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_prompt}]
                }
            ]

            # Append each image as high-detail input
            for img in images:
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": self.image_to_base64_data_uri(img),
                        "detail": "high"
                    }
                })

            # Send to GPT-4o
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=4096,
                temperature=0.2
            )

            content = response.choices[0].message.content.strip()

            # Clean JSON output (in case GPT wraps it in ```json)
            if content.startswith("```json"):
                content = re.sub(r"^```json", "", content)
                content = re.sub(r"```$", "", content).strip()

            return json.loads(content)

        except Exception as e:
            print(f"Error during fraud detection: {e}")
            return []

    def image_to_base64_data_uri(self, image: Image.Image) -> str:
        """
        Converts a PIL image to a base64-encoded data URI string for use with GPT-4o Vision API.
        """
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")  # Use PNG for best clarity
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"

    def extract_transactions_gpt(self, images: List[Image.Image], raw_text) -> Dict[str, Any]:
        """
        Extracts normalized transaction data from a list of bank statement images using GPT-4o's vision capabilities.
        Assumes GPT handles value categorization and float conversion with correct signs.
        """

        prompt = f"""
        You are an intelligent financial data extraction engine.

        From the given bank statement images, extract structured transaction data. 
        You can also use the raw text provided to assist in extraction. So that any wrongly extracted, missing or ambiguous data can be filled in.

        The Raw extracted text from images is:
        {raw_text}

        Ensure:
        - All monetary values must be parsed as clean float numbers, using proper positive or negative signs (e.g., 1200.50, -450.75), and must not include any symbols, commas, or placeholders like '-' or 'Rs.'.
        - Credit values are the positive amount added to customers account(e.g., money received or deposit or money in or Deposites).
        - Debit values are negative amount taken out from customers account (e.g., money paid or withdrawn or Money out or Payments).
        - Even if the original labels vary (e.g., "deposit", "withdrawn", "payment", "added", "subtracted"), identify the correct type.
        - Combine credit and debit into a single "amount" field with correct sign.
        - Balance values must always be returned as float numbers with an explicit sign:
            1) A positive balance must be returned as it is (e.g., 1025.50). If the balance has a suffix like "Cr" or prefix "+", it is positive amount.
            2) A negative balance must include a "-" sign (e.g., -450.75). If the balance has a suffix like "Dr" or prefix "-", it is negative (-) amount.
            3) Never omit the negative sign in negative balance (e.g., 1025.50 → ❌, -1025.50 → ✅)
        - Use best judgment if labels are missing or ambiguous. Understand the suffix or prefix of amounts , it might be a currency symbol or a +/- sign or under a different context.


        Respond only in this strict JSON format (no markdown or explanations):
        {
        "account_info": {
            "holder_name": "string",
            "account_number": "string",
            "period": "string",
            "final_balance": float
        },
        "transactions": [
            {
            "id": "string or integer",
            "details": "string",
            "date": "DD-MM-YYYY",
            "amount": "float",
            "balance": "float"
            }
        ]
        }
        """
        try:
            # Encode all images to base64 image_url format
            image_messages = []
            for img in images:
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="PNG")
                img_byte_arr.seek(0)
                b64_img = base64.b64encode(img_byte_arr.read()).decode("utf-8")
                image_messages.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64_img}"}
                })

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": [{"type": "text", "text": prompt}] + image_messages}
                ],
                max_tokens=4000,
                temperature=0.2
            )

            content = response.choices[0].message.content.strip()

            if content.startswith("```json"):
                content = re.sub(r"^```json", "", content)
                content = re.sub(r"```$", "", content).strip()

            data = json.loads(content)
            return data

        except Exception as e:
            print(f"Error in extract_transactions_gpt: {e}")
            return None

    def extract__from_text_transactions_gpt(self, statement_text: str) -> Dict[str, Any]:
        """
        Extracts transaction data from bank statement text using the OpenAI GPT API and returns cleaned float values.
        """
        prompt = """
        - All monetary values must be parsed as clean float numbers, using proper positive or negative signs (e.g., 1200.50, -450.75), and must not include any symbols, commas, or placeholders like '-' or 'Rs.'.
        - Credit values are the positive amount added to customers account(e.g., money received or deposit or money in or Deposites).
        - Debit values are negative amount taken out from customers account (e.g., money paid or withdrawn or Money out or Payments).
        - Even if the original labels vary (e.g., "deposit", "withdrawn", "payment", "added", "subtracted"), identify the correct type.
        - Combine credit and debit into a single "amount" field with correct sign.
        - Balance values must always be returned as float numbers with an explicit sign:
            1) A positive balance must be returned as it is (e.g., 1025.50). If the balance has a suffix like "Cr" or prefix "+", it is positive amount.
            2) A negative balance must include a "-" sign (e.g., -450.75). If the balance has a suffix like "Dr" or prefix "-", it is negative (-) amount.
            3) Never omit the negative sign in negative balance (e.g., 1025.50 → ❌, -1025.50 → ✅)
        - Use best judgment if labels are missing or ambiguous. Understand the suffix or prefix of amounts , it might be a currency symbol or a +/- sign or under a different context.


        Respond only in this strict JSON format (no markdown or explanations):
        
        {
        "account_info": {
            "bank_name":"string",
            "branch_code":"string",
            "branch_address":"string"
            "holder_name": "string",
            "account_number": "string",
            "period": "string",
            "final_balance": "float"
        },
        "transactions": [
            {
            "id": "integer",
            "details": "string",
            "date": "DD-MM-YYYY",
            "amount": "float",
            "balance": "float"
            },
            ...
        ]
        }
        """
        messages = [
            {
                "role": "system",
                "content": "You are an intelligent financial data extraction engine that extracts account information and transaction data from bank statement text and returns a dictionary. "
                        "Your response must strictly be a valid JSON dictionary with double-quoted keys and values as given in the prompt."
                        "Ensure that negative signs (-) are accurately captured when extracting numeric values. "
                        "If a requested field is not found, return 'null' for that field."
                        "Do not include any markdown formatting, extra characters, explanations, comments, or formatting beyond the dictionary itself."
            },
            {
                "role": "user",
                "content": f"From the following bank statement text {prompt}, extract and return only the requested data in dictionary format. "
                        f"If a field is not present, return 'null' for that field."
                        f"If extracted field is 0.00 or 0 then return 0.00 for that field"
                        f"Ensure the first entry on transactions is the opening balance entry only."
                        f"Ensure the response is strictly a dictionary. The bank statement text is: {statement_text}."
            }
        ]


        try:
            response = {}
            # try:
            #     tokenizer = encoding_for_model(OPEN_AI_MODEL)
            #     print(f"Loaded tokenizer: {type(tokenizer)}")  # Debug line
            # except KeyError:
            #     raise ValueError(f"Tokenizer for {OPEN_AI_MODEL} is not available.")

            # input_tokens = sum(len(tokenizer.encode(message["content"])) for message in messages)


            # if MAX_TOKEN_LIMIT - input_tokens - 50  >0:
            #     max_tokens=input_tokens + 50

            response = client.chat.completions.create(
                model=OPEN_AI_MODEL,
                messages=messages,
                max_tokens=MAX_TOKEN_LIMIT
            )
            
            if not response:
                print("No response received from OpenAI API.")
                return {}

            content = response.choices[0].message.content
            print("content", content)

            # Handle JSON wrapped in markdown
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()

            
            # try:
            #     response_dict = response.model_dump()
            #     content =  response_dict['choices'][0]['message']['content']
            #     data =  self.safe_parse_json(content)
            # except Exception:
            #     print("here")
            #     data = eval(response.choices[0].message.content)  # Fallback


        except Exception as e:
            print(f"Error in extract_transactions_gpt: {e}")
            return None
    
        return json.loads(content)

    def safe_parse_json(self, content: str) -> dict:
        """
        Safely parses a JSON-like string from OpenAI responses, even if wrapped in markdown.
        """
        # Remove markdown code block if present
        print("in safe parse_json")
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(content)
            except Exception:
                print(" Failed to parse GPT response as JSON.")
                return {}
