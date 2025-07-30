from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
# Allow CORS for all origins, you might want to restrict this in production
CORS(app)

# Google Sheets setup
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds_dict = {
    "type": "service_account",
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_CERT_URL")
}
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        print("📥 Received data:", data)

        # Update required fields based on your HTML form's 'required' attributes
        # and what you deem critical for a successful entry.
        # Ensure these keys match the 'name' attributes in your HTML form.
        required_fields = [
            "Name", "Gender", "Father's Name", "Date of Birth", "Category",
            "Blood Group", "Course", "Year of Admission", "Department",
            "Semester", "Enrollment Number", "Background", "Permanent Address",
            "Correspondence Address", "Email", "Mobile Number", "Photo", "Sign"
        ]

        # Check for missing or empty required fields
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify(success=False, message=f"Missing or empty required field: {field}"), 400

        # Construct the row for Google Sheets, ensuring order matches your sheet columns
        row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Timestamp
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
            data.get("Enrollment Number"),
            data.get("Background"),
            data.get("Permanent Address"),
            data.get("Correspondence Address"),
            data.get("Email"),
            data.get("Mobile Number"),
            data.get("Photo"), # This will be the ImgBB URL
            data.get("Sign"),  # This will be the ImgBB URL
        ]

        sheet.append_row(row)
        # Change 'status' to 'success' to match your JS client-side check
        return jsonify(success=True, status="success", message="Registration successful!")
    
    except Exception as e:
        print("❌ ERROR:", str(e))
        # Ensure error response also has 'success: False' and a message
        return jsonify(success=False, status="error", message="Internal server error. Please try again later."), 500

if __name__ == "__main__":
    # Use environment variable PORT, default to 8080 for local development
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)