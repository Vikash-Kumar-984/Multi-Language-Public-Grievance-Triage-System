
# Civic Issue Reporter: A Multimodal AI Triage System

This project is a Google Cloud-based web application that allows citizens to report public grievances (like potholes or garbage) using photos and multilingual voice notes. It uses a serverless backend with Vertex AI and the Speech-to-Text API to intelligently categorize, transcribe, and file these reports, turning unstructured chaos into actionable data for municipal corporations.

This project was built for the Google Cloud & Blog Competition.

### Live Demo

**(Link to your live Firebase app: (`[https://civic-issue-reporter-248736505026.us-west1.run.app/`)**

## 1. The Problem Statement

Municipal corporations are overwhelmed by a high volume of public complaints. These reports arrive in a chaotic, unstructured manner, making them difficult to manage:

* **Multilingual:** In a diverse city, reports can be in any number of local languages (e.g., Hindi, Kannada, Tamil, English), often in the same report.

* **Unstructured:** A report might be a blurry photo, a frantic voice note, or a vague text. There is no standard format.

* **Duplicate:** The same pothole might be reported 50 times by 50 different people, creating redundant work.

* **Manual Labor:** City employees must manually look at every photo, listen to every voice note, and try to categorize the problem and location, which is slow, expensive, and inefficient.

## 2. Our Solution

We built a simple, mobile-first web app that acts as an intelligent "first line of defense." It makes reporting easy for the citizen and provides perfectly structured data for the city.

**How it works for the user:**

1. **Open App:** The user opens the web app. The browser gets their current **GPS location**.

2. **Snap Photo:** The user uploads a photo of the problem.

3. **Describe Issue:** The user has two options:

   * **Record/Upload a Voice Note** in their native language.

   * **Type a brief description** in any language.

4. **Submit:** The user hits "Submit." The app handles the rest.

The system then automatically analyzes the media, creates a structured ticket, and saves it to a central database.



## 3. Technology Stack

This project is built 100% on Google Cloud, using a scalable, serverless architecture.

* **Frontend:**

  * **Firebase Hosting:** Hosts the static HTML, CSS (Tailwind), and JavaScript files on a global CDN.

* **Backend (Serverless):**

  * **Cloud Functions (2nd Gen):** Three separate Python functions that act as our entire backend logic.

* **Storage:**

  * **Cloud Storage:** Stores all user-uploaded media (photos and audio files).

  * **Firestore:** A NoSQL database to store the final, structured grievance "tickets."

* **Artificial Intelligence (AI):**

  * **Vertex AI (Gemini Models):** Used for image analysis. It "looks" at the photo and returns a JSON object with the category (e.g., "Pothole") and a short description.

  * **Cloud Speech-to-Text API:** Transcribes the user's voice note. Its most powerful feature is **auto-language detection**, which was critical for this project.

## 4. Solution Architecture

The entire application is event-driven and decoupled.



**Step-by-Step Data Flow:**

1. **Client (Browser):** The user fills out the form on the **Firebase Hosting** website. The JavaScript on the page gets the user's location.

2. **Get Signed URLs:** The browser first calls our `getUploadURLs` **Cloud Function**. This function uses its "Service Account" identity to create secure, temporary "signed URLs" for **Cloud Storage**. This is a best practice, as the user uploads files *directly* to the bucket without the files ever touching our backend.

3. **File Upload:** The browser receives the signed URLs and uploads the photo and audio files directly to the **Cloud Storage** bucket.

4. **Process Grievance:** Once the uploads are complete, the browser calls our second Cloud Function, `processGrievance`, and sends it the `gs://` paths to the new files, the user's location, and the typed text.

5. **AI Analysis:** The `processGrievance` function now runs two AI jobs:

   * **Vision:** It sends the image path to the **Vertex AI (Gemini) API** to get a category and AI description.

   * **Speech:** If an audio file was uploaded, it sends the audio path to the **Speech-to-Text API** to get a transcription.

6. **Create Ticket:** The function combines all this data (location, AI category, AI description, transcription, text description) into a single, structured Python dictionary.

7. **Save to DB:** This "perfect ticket" is saved as a new document in our **Firestore** database.

8. **Fetch Reports:** The user's app also calls the third Cloud Function, `getGrievances`, which securely reads the **Firestore** database (10 most recent) to display the "Recently Reported Issues" list.

## 5. How to Deploy This Project

Re-creating this project involves three phases: setting up the cloud environment, deploying the backend, and deploying the frontend.

### Prerequisites

1. A Google Cloud Project with billing enabled.

2. [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/install) installed and authenticated.

3. [Firebase CLI (`firebase-tools`)](https://firebase.google.com/docs/cli) installed (`npm install -g firebase-tools`).

### Phase 1: Configure Google Cloud

1. **Enable APIs:** In your GCP Console, go to "APIs & Services" > "Library" and enable all 6 of these APIs:

   * `Cloud Functions API`

   * `Cloud Run API` (for Cloud Functions 2nd Gen)

   * `Vertex AI API`

   * `Cloud Speech-to-Text API`

   * `Cloud Storage`

   * `Firestore API`

2. **Create Storage Bucket:** Go to "Cloud Storage" and create a new bucket (e.g., `my-grievance-uploads`).

3. **Create Firestore:** Go to "Firestore" and create a new database in "Native mode."

4. **Set CORS:** Create a file named `cors.json` with the following content:

   ```json
   [
     {
       "origin": ["*"],
       "method": ["GET", "PUT"],
       "responseHeader": ["Content-Type"],
       "maxAgeSeconds": 3600
     }
   ]
