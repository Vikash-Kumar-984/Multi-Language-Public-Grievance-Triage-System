import functions_framework
import vertexai
import json
import time
from flask import make_response
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import speech, firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

import google.auth
from google.auth import impersonated_credentials
# -------------------------------------

BUCKET_NAME = "grievance-triage-app-uploads"  # e.g., "grievance-triage-app-uploads"
PROJECT_ID = "grievance-triage-app" # e.g., "grievance-triage-app-12345"
LOCATION = "us-central1"
GRIEVANCE_COLLECTION = "grievances"

COMPUTE_SERVICE_ACCOUNT_EMAIL = "147983210586-compute@developer.gserviceaccount.com" 

# Initialize clients
storage_client = storage.Client()
db = firestore.Client()
vertexai.init(project=PROJECT_ID, location=LOCATION)

gemini_model = GenerativeModel("gemini-1.5-pro-001") 
# --- END OF FIX ---
speech_client = speech.SpeechClient()

# Get the function's default credentials
DEFAULT_CREDENTIALS, _ = google.auth.default()
SCOPES = ["https://www.googleapis.com/auth/devstorage.read_write"]

def add_cors_headers(response):
    """Adds CORS headers to a Flask response."""
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    response.headers.update(response_headers)
    return response

# --- FUNCTION 1: Get Upload URLs ---
@functions_framework.http
def getUploadURLs(request):
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response('', 204))

    try:
        data = request.get_json()
        if not data:
            return add_cors_headers(make_response(json.dumps({"error": "No JSON payload."}), 400))

        image_filename = data.get("image_filename")
        audio_filename = data.get("audio_filename") 

        if not image_filename:
            return add_cors_headers(make_response(json.dumps({"error": "Missing image_filename."}), 400))

        impersonated_creds = impersonated_credentials.Credentials(
            source_credentials=DEFAULT_CREDENTIALS,
            target_principal=COMPUTE_SERVICE_ACCOUNT_EMAIL,
            target_scopes=SCOPES
        )
        
        signing_storage_client = storage.Client(credentials=impersonated_creds)
        bucket = signing_storage_client.bucket(BUCKET_NAME)
        
        unique_image_name = f"uploads/{int(time.time())}-{image_filename}"
        image_blob = bucket.blob(unique_image_name)
        
        image_url = image_blob.generate_signed_url(
            version="v4",
            expiration=900, 
            method="PUT"
        )
        
        response_data = {
            "image_signed_url": image_url,
            "image_gs_path": f"gs://{BUCKET_NAME}/{unique_image_name}",
            "audio_signed_url": None,
            "audio_gs_path": None
        }
        
        if audio_filename:
            unique_audio_name = f"uploads/{int(time.time())}-{audio_filename}"
            audio_blob = bucket.blob(unique_audio_name)
            
            audio_url = audio_blob.generate_signed_url(
                version="v4",
                expiration=900, 
                method="PUT"
            )
            
            response_data["audio_signed_url"] = audio_url
            response_data["audio_gs_path"] = f"gs://{BUCKET_NAME}/{unique_audio_name}"

        return add_cors_headers(make_response(json.dumps(response_data), 200))

    except Exception as e:
        print(f"Error in getUploadURLs: {e}")
        import traceback
        traceback.print_exc()
        return add_cors_headers(make_response(json.dumps({"error": str(e)}), 500))

# --- FUNCTION 2: Process a New Grievance ---
@functions_framework.http
def processGrievance(request):
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response('', 204))
        
    try:
        data = request.get_json()
        if not data:
            return add_cors_headers(make_response(json.dumps({"error": "No JSON payload."}), 400))

        image_path = data.get("image_path")
        audio_path = data.get("audio_path")
        location = data.get("location")
        text_description = data.get("text_description", "")

        if not image_path or not location:
            return add_cors_headers(make_response(json.dumps({"error": "Missing image_path or location."}), 400))

        print(f"Processing new grievance for location: {location}")

        # 1. Analyze Image
        image_analysis = analyze_image_with_gemini(image_path)
        
        # 2. Transcribe Audio (Conditionally)
        audio_analysis = {"transcription": "", "language_code": ""}
        if audio_path:
            print(f"Transcribing audio: {audio_path}")
            audio_analysis = transcribe_audio(audio_path)

        # 3. Save to Firestore
        print("Creating new grievance ticket...")
        geo_location = firestore.GeoPoint(location["lat"], location["lng"])
        
        new_ticket = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "status": "new",
            "location": geo_location,
            "image": {
                "url": image_path,
                "category": image_analysis.get("category", "Other"),
                "ai_description": image_analysis.get("description", ""),
            },
            "audio": {
                "url": audio_path if audio_path else "",
                "transcription": audio_analysis.get("transcription", ""),
                "language": audio_analysis.get("language_code", ""),
            },
            "text_description": text_description
        }

        doc_ref = db.collection(GRIEVANCE_COLLECTION).add(new_ticket)
        ticket_id = doc_ref[1].id
        print(f"Successfully created new grievance ticket: {ticket_id}")

        ticket_data_serializable = new_ticket.copy()
        ticket_data_serializable["timestamp"] = time.time() * 1000 
        ticket_data_serializable["location"] = location 
        
        response_data = {
            "status": "success",
            "ticket_id": ticket_id,
            "ticket_data": ticket_data_serializable
        }
        return add_cors_headers(make_response(json.dumps(response_data), 201))

    except Exception as e:
        print(f"Error processing grievance: {e}")
        import traceback
        traceback.print_exc()
        return add_cors_headers(make_response(json.dumps({"error": str(e)}), 500))

# --- FUNCTION 3: Get All Grievances (NEW) ---
@functions_framework.http
def getGrievances(request):
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response('', 204))

    try:
        print("Fetching recent grievances...")
        docs = db.collection(GRIEVANCE_COLLECTION) \
                 .order_by("timestamp", direction=firestore.Query.DESCENDING) \
                 .limit(20) \
                 .stream()

        issues = []
        for doc in docs:
            issue = doc.to_dict()
            issue["id"] = doc.id
            
            if "timestamp" in issue and issue["timestamp"]:
                issue["timestamp"] = issue["timestamp"].isoformat()
            if "location" in issue and issue["location"]:
                issue["location"] = {
                    "lat": issue["location"].latitude,
                    "lng": issue["location"].longitude
                }
            issues.append(issue)
        
        print(f"Found {len(issues)} issues.")
        return add_cors_headers(make_response(json.dumps(issues), 200))

    except Exception as e:
        print(f"Error in getGrievances: {e}")
        import traceback
        traceback.print_exc()
        return add_cors_headers(make_response(json.dumps({"error": str(e)}), 500))


# --- Helper: Gemini ---
def analyze_image_with_gemini(gs_uri):
    try:
        image_part = Part.from_uri(gs_uri, mime_type="image/jpeg")
        prompt = """
        Analyze this image from a public grievance report.
        Categorize it into one of: 'Pothole', 'Garbage Dump', 'Broken Streetlight', 'Fallen Tree', 'Flooding', 'Other'.
        Provide a one-sentence description of the problem.
        Return your response as a JSON object with "category" and "description" keys.
        """
        vision_model = GenerativeModel("gemini-1.5-pro-001")
        # --- END OF FIX ---
        
        response = vision_model.generate_content(
            [image_part, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error in Gemini analysis: {e}")
        import traceback 
        traceback.print_exc() 
        return {"category": "Other", "description": "AI analysis failed."}

# --- Helper: Speech-to-Text ---
def transcribe_audio(gs_uri):
    try:
        config = speech.RecognitionConfig(
            auto_language_detection=True,
            model="latest_long"
        )
        audio = speech.RecognitionAudio(uri=gs_uri)
        response = speech_client.recognize(config=config, audio=audio)

        if not response.results:
            return {"transcription": "", "language_code": ""}
        result = response.results[0]
        return {
            "transcription": result.alternatives[0].transcript,
            "language_code": result.language_code
        }
    except Exception as e:
        print(f"Error in transcription: {e}")
        return {"transcription": f"Transcription failed: {e}", "language_code": ""}