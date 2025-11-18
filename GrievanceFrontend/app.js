// --- CONFIGURATION ---
// PASTE YOUR 3 DEPLOYED CLOUD FUNCTION URLS HERE
const config = {
  getUploadURLs_endpoint: "https://us-central1-grievance-triage-app.cloudfunctions.net/getUploadURLs",
  processGrievance_endpoint: "https://us-central1-grievance-triage-app.cloudfunctions.net/processGrievance",
  getGrievances_endpoint: "https://us-central1-grievance-triage-app.cloudfunctions.net/getGrievances" // We will create this
};
// ---------------------

// --- New UI Element Selectors ---
const formContainer = document.getElementById('form-container');
const successContainer = document.getElementById('success-container');
const reportAnotherButton = document.getElementById('report-another-button');
const ticketDetails = document.getElementById('ticket-details');
const recentIssuesList = document.getElementById('recent-issues-list');

// --- Original Form Selectors ---
const form = document.getElementById('grievance-form');
const imageFile = document.getElementById('image-file');
const audioFile = document.getElementById('audio-file');
const textDescription = document.getElementById('text-description');
const submitButton = document.getElementById('submit-button');
const messageBox = document.getElementById('message-box');

// --- Event Listeners ---
form.addEventListener('submit', handleSubmit);
reportAnotherButton.addEventListener('click', showForm);

// --- Run on Page Load ---
document.addEventListener('DOMContentLoaded', () => {
  loadRecentIssues();
});

// --- Main Form Submission Logic ---
async function handleSubmit(e) {
  e.preventDefault();
  
  const img = imageFile.files[0];
  const aud = audioFile.files[0];
  const desc = textDescription.value.trim();

  // --- THIS IS THE FIXED VALIDATION ---
  if (!img) {
    showMessage('Please select an image file.', 'error');
    return;
  }
  if (!aud && !desc) {
    // This logic is correct: "if no audio AND no description, show error"
    showMessage('Please provide either a voice note or a written description.', 'error');
    return;
  }
  // --- END OF FIX ---

  setLoading(true, '1/4: Getting your location...');

  try {
    const location = await getLocation();
    setLoading(true, '2/4: Preparing secure file upload...');

    const { image_signed_url, audio_signed_url, image_gs_path, audio_gs_path } = 
      await getSignedUrls(img.name, aud ? aud.name : null);
    
    setLoading(true, '3/4: Uploading files...');

    const uploadPromises = [ uploadFile(image_signed_url, img) ];
    if (aud && audio_signed_url) {
      uploadPromises.push(uploadFile(audio_signed_url, aud));
    }
    await Promise.all(uploadPromises);

    setLoading(true, '4/4: Analyzing grievance with AI...');

    const result = await processGrievance(
      image_gs_path, 
      aud ? audio_gs_path : null, 
      location, 
      desc
    );

    // --- NEW SUCCESS LOGIC ---
    showSuccessMessage(result.ticket_data); // Show the success card
    loadRecentIssues(); // Refresh the recent issues list
    form.reset(); // Clear the form

  } catch (err) {
    console.error('Error in handleSubmit:', err);
    showMessage(`An error occurred: ${err.message}`, 'error');
  } finally {
    setLoading(false);
  }
}

// --- NEW FEATURE: Load Recent Issues ---
async function loadRecentIssues() {
  recentIssuesList.innerHTML = `<div class="bg-white p-4 rounded-lg shadow text-gray-500 text-center">Loading recent reports...</div>`;
  
  // Check if the getGrievances_endpoint is filled
  if (!config.getGrievances_endpoint || config.getGrievances_endpoint.includes("PASTE_NEW")) {
    recentIssuesList.innerHTML = `<div class="bg-white p-4 rounded-lg shadow text-yellow-600 text-center">Admin: 'getGrievances_endpoint' is not configured in app.js.</div>`;
    return; // Don't try to fetch
  }

  try {
    const response = await fetch(config.getGrievances_endpoint);
    if (!response.ok) {
      throw new Error('Could not fetch recent issues.');
    }
    const issues = await response.json();
    
    if (issues.length === 0) {
      recentIssuesList.innerHTML = `<div class="bg-white p-4 rounded-lg shadow text-gray-500 text-center">No reports filed yet.</div>`;
      return;
    }

    // Build HTML for each issue
    recentIssuesList.innerHTML = issues.map(issue => `
      <div class="bg-white p-4 rounded-lg shadow">
        <span class="text-xs font-semibold ${issue.status === 'new' ? 'text-blue-600' : 'text-gray-500'} bg-blue-50 px-2 py-1 rounded-full">${issue.status.toUpperCase()}</span>
        <h3 class="font-semibold text-gray-900 mt-2">${issue.image.category} at ${issue.location.lat.toFixed(4)}, ${issue.location.lng.toFixed(4)}</h3>
        <p class="text-sm text-gray-600 mt-1">${issue.text_description || issue.audio.transcription || 'No description provided.'}</p>
        <p class="text-xs text-gray-400 mt-2">Reported: ${new Date(issue.timestamp).toLocaleString()}</p>
      </div>
    `).join('');

  } catch (err) {
    console.error(err);
    recentIssuesList.innerHTML = `<div class="bg-white p-4 rounded-lg shadow text-red-500 text-center">Error loading reports.</div>`;
  }
}

// --- Helper Functions ---

function showSuccessMessage(ticketData) {
  // Populate the success card
  let description = ticketData.text_description || ticketData.audio.transcription || "Your report is being processed.";
  let title = `${ticketData.image.category} at ${ticketData.location.lat.toFixed(4)}, ${ticketData.location.lng.toFixed(4)}`;
  
  ticketDetails.innerHTML = `
    <h3 class="text-lg font-medium text-gray-900">${title}</h3>
    <p class="mt-2 text-gray-600">A formal inspection request has been initiated. The AI-generated description is: "${ticketData.image.ai_description}"</p>
  `;
  
  // Switch the views
  formContainer.style.display = 'none';
  successContainer.style.display = 'block';
  messageBox.style.display = 'none'; // Hide any old messages
}

function showForm() {
  // Switch back to the form
  formContainer.style.display = 'block';
  successContainer.style.display = 'none';
}

function setLoading(isLoading, message = '') {
  submitButton.disabled = isLoading;
  if (isLoading) {
    showMessage(message, 'loading');
  } else {
    messageBox.style.display = 'none';
  }
}

function showMessage(message, type) {
  let bgColor, textColor;
  if (type === 'error') {
    bgColor = 'bg-red-100'; textColor = 'text-red-700';
  } else if (type === 'success') {
    bgColor = 'bg-green-100'; textColor = 'text-green-700';
  } else {
    bgColor = 'bg-blue-100'; textColor = 'text-blue-700';
  }
  messageBox.className = `p-4 rounded-lg ${bgColor} ${textColor}`;
  messageBox.textContent = message;
  messageBox.style.display = 'block';
}

function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported.'));
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude
        });
      },
      () => {
        reject(new Error('Unable to retrieve location.'));
      }
    );
  });
}

async function getSignedUrls(imageName, audioName) {
  const response = await fetch(config.getUploadURLs_endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_filename: imageName,
      audio_filename: audioName
    })
  });
  if (!response.ok) {
    throw new Error('Could not get upload URLs.');
  }
  return await response.json();
}

async function uploadFile(signedUrl, file) {
  const response = await fetch(signedUrl, {
    method: 'PUT',
    headers: { 'Content-Type': file.type },
    body: file
  });
  if (!response.ok) {
    throw new Error(`File upload failed: ${file.name}.`);
  }
}

async function processGrievance(imagePath, audioPath, location, textDescription) {
  const response = await fetch(config.processGrievance_endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_path: imagePath,
      audio_path: audioPath,
      location: location,
      text_description: textDescription
    })
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(`AI processing failed: ${err.error}`);
  }
  return await response.json();
}