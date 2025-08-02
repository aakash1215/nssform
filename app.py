from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import logging
from concurrent.futures import ThreadPoolExecutor

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

# Initialize a ThreadPoolExecutor for background tasks
# The max_workers should be tuned based on your server resources and expected concurrency.
# A common starting point is (number of CPU cores * 2) or more, depending on I/O bound tasks.
executor = ThreadPoolExecutor(max_workers=5) # Adjust max_workers as needed

def _append_data_to_sheet(row_data):
    """Helper function to run the blocking gspread operation in a separate thread."""
    try:
        sheet.append_row(row_data)
        logging.info("✅ Data successfully appended to Google Sheet in background.")
        return True, "Registration successful!"
    except gspread.exceptions.APIError as api_e:
        logging.error(f"❌ Google Sheets API error during append_row in background: {api_e}", exc_info=True)
        return False, f"Failed to save data due to a Google Sheets API error: {api_e}"
    except gspread.exceptions.WorksheetNotFound:
        logging.error("❌ Google Sheets: The specified worksheet was not found in background operation.", exc_info=True)
        return False, "Server configuration error: Worksheet not found."
    except Exception as e:
        logging.error(f"❌ Unhandled ERROR during background append_row: {str(e)}", exc_info=True)
        return False, f"An unexpected error occurred during data saving: {e}"

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
        image_url_fields = ["Photo", "Sign", "Payment Screenshot"]
        for field in image_url_fields:
            url = data.get(field)
            if not isinstance(url, str) or not url.strip().startswith(('http://', 'https://')):
                logging.warning(f"❌ Invalid URL format for field: {field}. Value received: {url}")
                return jsonify(success=False, message=f"Invalid URL format for {field}. Must be a valid HTTP/HTTPS URL."), 400

        # Construct the row for Google Sheets
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

        # Submit the Google Sheet append operation to the thread pool
        # This makes the /register endpoint respond immediately, while the sheet update happens in the background.
        # Note: The client will receive a success message before the data is actually written to the sheet.
        # If strong consistency is needed (i.e., ensure data is written before responding), this approach is not suitable.
        executor.submit(_append_data_to_sheet, row)
        logging.info("🚀 Data submitted for background processing to Google Sheet.")
        
        # Return an immediate success response
        return jsonify(success=True, message="Registration request received and being processed!")
            
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

    # When deploying with a WSGI server like Gunicorn, you would typically
    # let Gunicorn manage the workers/threads, and you wouldn't run app.run() directly.
    # For local development, this is fine.
    app.run(host="0.0.0.0", port=port)
