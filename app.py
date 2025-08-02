from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# --- Configuration & Initialization ---
# Ensure your environment variables are correctly set:
# GOOGLE_PROJECT_ID
# GOOGLE_PRIVATE_KEY_ID
# GOOGLE_PRIVATE_KEY (must include actual newlines, not escaped \n)
# GOOGLE_CLIENT_EMAIL
# GOOGLE_CLIENT_ID
# GOOGLE_CLIENT_CERT_URL
# GOOGLE_SPREADSHEET_ID
# PORT (optional, defaults to 8080)

app = Flask(__name__)
# Allow CORS for all origins.
# IMPORTANT: In production, consider restricting this to your specific frontend domain(s)
# Example: CORS(app, resources={r"/register": {"origins": "https://your-frontend-domain.com"}})
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Google Sheets setup
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Construct credentials dictionary from environment variables
creds_dict = {
    "type": "service_account",
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"), # Ensure newlines are correctly interpreted, handle missing key gracefully
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_CERT_URL")
}

client = None
sheet = None

try:
    # Basic validation of critical creds fields before attempting connection
    if not all(creds_dict.get(key) for key in ["project_id", "private_key", "client_email", "client_id", "client_x509_cert_url"]):
        raise ValueError("One or more critical Google Sheets credentials environment variables are missing or empty.")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")

    if not SPREADSHEET_ID:
        raise ValueError("GOOGLE_SPREADSHEET_ID environment variable is not set.")

    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    logging.info("✅ Google Sheets connection established successfully.")
except ValueError as ve:
    logging.error(f"❌ Configuration Error: {ve}")
    # In a production environment, you might want to prevent the app from starting
    # sys.exit(1)
except gspread.exceptions.SpreadsheetNotFound:
    logging.error(f"❌ Error connecting to Google Sheets: Spreadsheet with ID '{SPREADSHEET_ID}' not found or inaccessible.")
except gspread.exceptions.APIError as api_e:
    logging.error(f"❌ Google Sheets API Error: {api_e}. Check service account permissions and API enablement.")
except Exception as e:
    logging.error(f"❌ General Error connecting to Google Sheets: {e}", exc_info=True)

@app.route("/register", methods=["POST"])
def register():
    if sheet is None:
        logging.error("Attempted registration, but Google Sheets connection not established.")
        return jsonify(success=False, message="Server not configured for registration. Please try again later."), 503 # Service Unavailable

    try:
        data = request.get_json()
        if not data:
            logging.warning("Received empty or non-JSON request.")
            return jsonify(success=False, message="Invalid request: Expected JSON data."), 400

        logging.info("📥 Received data for registration.")

        # Define all required fields based on your frontend form
        required_fields = [
            "Name", "Gender", "Father's Name", "Date of Birth", "Category",
            "Blood Group", "Course", "Year of Admission", "Department",
            "Semester", "Background", "Permanent Address",
            "Correspondence Address", "Email", "Mobile Number",
            "Photo", "Sign", "Payment Screenshot", "Transaction ID"
        ]

        # Check for missing or empty required fields
        for field in required_fields:
            if field not in data or not data[field]:
                logging.warning(f"❌ Missing or empty required field: {field}")
                return jsonify(success=False, message=f"Missing or empty required field: {field}"), 400

        # Optional: Add basic validation for URL fields
        # This checks if they are non-empty strings. More robust URL validation
        # (e.g., using regex or a dedicated library) could be added if needed.
        image_url_fields = ["Photo", "Sign", "Payment Screenshot"]
        for field in image_url_fields:
            url = data.get(field)
            if not isinstance(url, str) or not url.strip().startswith(('http://', 'https://')):
                logging.warning(f"❌ Invalid URL format for field: {field}. Value received: {url}")
                return jsonify(success=False, message=f"Invalid URL format for {field}. Must be a valid HTTP/HTTPS URL."), 400

        # Construct the row for Google Sheets
        # IMPORTANT: The order here MUST match the column order in your Google Sheet.
        # If your sheet has columns like "Timestamp", "Full Name", "Gender", etc.,
        # ensure this list's order reflects that.
        row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp for when registration was received
            data.get("Name"),
            data.get("Gender"),
            data.get("Father's Name"),
            data.get("Date of Birth"),
            data.get("Category"),
            data.get("Blood Group"),
            data.get("Course"),
            data.get("Year of Admission"),
            data.get("Department"),
            data.get("Semester"),
            # Ensure "Enrollment Number" is handled. If it's not a required_field
            # but is expected in the row, use .get() gracefully.
            # If it IS a required field, add it to required_fields list above.
            data.get("Enrollment Number", ""), # Assuming it might be optional, provide default empty string
            data.get("Background"),
            data.get("Permanent Address"),
            data.get("Correspondence Address"),
            data.get("Email"),
            data.get("Mobile Number"),
            data.get("Photo"), # URL from ImgBB
            data.get("Sign"),    # URL from ImgBB
            data.get("Payment Screenshot"), # URL from ImgBB
            data.get("Transaction ID") # Plain text
        ]

        # Append the row to the Google Sheet
        sheet.append_row(row)
        logging.info("✅ Data successfully appended to Google Sheet.")
        
        # Return a success response
        return jsonify(success=True, message="Registration successful!")
        
    except gspread.exceptions.APIError as api_e:
        logging.error(f"❌ Google Sheets API error during append_row: {api_e}. Check sheet permissions or quota.", exc_info=True)
        return jsonify(success=False, message=f"Failed to save data due to a Google Sheets API error. Please try again later."), 500
    except gspread.exceptions.WorksheetNotFound:
        logging.error("❌ Google Sheets: The specified worksheet was not found. Check sheet name/index.", exc_info=True)
        return jsonify(success=False, message="Server configuration error: Worksheet not found."), 500
    except TypeError as te:
        logging.error(f"❌ Data Type Error during registration: {te}. Likely an issue with data format or missing key.", exc_info=True)
        return jsonify(success=False, message=f"Invalid data format received. Please check your input."), 400
    except Exception as e:
        logging.error(f"❌ Unhandled ERROR during registration: {str(e)}", exc_info=True)
        # Return a generic error message in production for security.
        return jsonify(success=False, message="An unexpected error occurred during registration. Please try again."), 500

if __name__ == "__main__":
    # Use environment variable PORT, default to 8080 for local development
    port = int(os.getenv("PORT", 8080))
    logging.info(f"🚀 Starting Flask app on http://0.0.0.0:{port}")

    app.run(host="0.0.0.0", port=port)
