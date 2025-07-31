from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

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
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace("\\n", "\n"), # Ensure newlines are correctly interpreted
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_CERT_URL")
}

try:
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    print("✅ Google Sheets connection established successfully.")
except Exception as e:
    print(f"❌ Error connecting to Google Sheets: {e}")
    # In a real application, you might want to exit or log this error more critically
    # rather than just printing. For development, this is fine.

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        print("📥 Received data:", data)

        # Define all required fields based on your frontend form
        # Make sure these keys exactly match the 'name' attributes in your HTML form
        # and the keys sent in the JSON payload from the frontend.
        required_fields = [
            "Name", "Gender", "Father's Name", "Date of Birth", "Category",
            "Blood Group", "Course", "Year of Admission", "Department",
            "Semester", "Background", "Permanent Address",
            "Correspondence Address", "Email", "Mobile Number",
            "Photo", "Sign", "Payment Screenshot", "Transaction ID" # Added new fields
        ]

        # Check for missing or empty required fields
        for field in required_fields:
            if field not in data or not data[field]:
                print(f"❌ Missing or empty required field: {field}")
                return jsonify(success=False, message=f"Missing or empty required field: {field}"), 400

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
            data.get("Blood Group"), # Moved to match expected order
            data.get("Course"),
            data.get("Year of Admission"),
            data.get("Department"),
            data.get("Semester"),
            data.get("Enrollment Number"),
            data.get("Background"),
            data.get("Permanent Address"),
            data.get("Correspondence Address"),
            data.get("Email"),
            data.get("Mobile Number"),
            data.get("Photo"), # URL from ImgBB
            data.get("Sign"),   # URL from ImgBB
            data.get("Payment Screenshot"), # URL from ImgBB
            data.get("Transaction ID") # Plain text
        ]

        # Append the row to the Google Sheet
        sheet.append_row(row)
        print("✅ Data successfully appended to Google Sheet.")
        
        # Return a success response
        return jsonify(success=True, message="Registration successful!")
    
    except Exception as e:
        print(f"❌ ERROR during registration: {str(e)}")
        # Return a more descriptive error message in development,
        # but a generic one in production for security.
        return jsonify(success=False, message=f"Internal server error: {str(e)}"), 500

if __name__ == "__main__":
    # Use environment variable PORT, default to 8080 for local development
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Starting Flask app on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)