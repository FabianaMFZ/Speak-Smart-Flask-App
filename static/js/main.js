// Initialize Socket.IO client
const socket = io();

// Variables to track recording state
let isRecording = false;
let timerInterval = null;
let timeElapsed = 0
let transcriptHistory = ''; // To keep track of all interim results

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function startTimer() {
    timeElapsed = 0; // Reset timer
    clearInterval(timerInterval); // Clear existing timer interval if any
    timerInterval = setInterval(function() {
        timeElapsed++;
        document.getElementById('recording-time').textContent = `Recording Time: ${formatTime(timeElapsed)}`;
    }, 1000);
}

function stopTimer() {
    clearInterval(timerInterval);
    document.getElementById('recording-time').textContent = `Recording Time: ${formatTime(timeElapsed)}`;
}

// DOM Elements
const startButton = document.getElementById('start-recording');
const stopButton = document.getElementById('stop-recording');
const readyButton = document.getElementById('ready-button');
const retryButton = document.getElementById('retry-button');
const transcriptDisplay = document.getElementById('transcript');
const confidenceDisplay = document.getElementById('confidence');
const recordingStatus = document.getElementById('recording-status');
const recordingTime = document.getElementById('recording-time');
const readTranscriptSection = document.getElementById('gpt-text-section');
const filename = document.getElementById('filename');
const phrases = document.getElementById('phrases');
const language = document.getElementById('language');
const altLanguage = document.getElementById('alt-language');
const grammarFeedbackSection = document.getElementById('grammar-feedback-section');
const feedbackModal = new bootstrap.Modal(document.getElementById('feedbackModal'));


// Start recording button event
startButton.addEventListener('click', function() {
    const trimmedFilename = filename.value.trim();
    if (!trimmedFilename) {
        alert('Please enter a valid filename.');
        return;
    }
    fetch('/start_recording', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            filename: filename.value,
            phrases: phrases.value,
            language_code: language.value,
            alternative_language_code: altLanguage.value
        })
    }).then(response => response.json())
      .then(data => {
        console.log('Recording started:', data);
        isRecording = true;
        startButton.disabled = true;
        stopButton.disabled = false;
                
    }).catch(error => {
        console.error('Error starting recording:', error);
    });
    recordingStatus.textContent = 'Status: Recording...';
    startTimer();
});

// Stop recording button event
stopButton.addEventListener('click', function() {
    fetch('/stop_recording', {
        method: 'POST'
    }).then(response => response.json())
      .then(data => {
        console.log('Recording stopped:', data);
        isRecording = false;
        startButton.disabled = false;
        stopButton.disabled = true;
    }).catch(error => {
        console.error('Error stopping recording:', error);
    });
    recordingStatus.textContent = 'Status: Stopped';
    stopTimer();
    // Show feedback modal
    feedbackModal.show();
});

// Ready button event inside feedback modal
readyButton.addEventListener('click', function() {
    const language = document.getElementById('language').value;
    const transcriptText = transcriptDisplay.textContent; 
    fetch('/feedback', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            transcript: transcriptText,  
            language_code: language
        })
    }).then(response => response.json())
      .then(data => {
        console.log('Feedback received:', data);
        feedbackModal.hide();
        showFeedback(data);
    }).catch(error => {
        console.error('Error processing feedback:', error);
    });
});

// Retry button event to reset without a page reload
retryButton.addEventListener('click', function() {
    fetch('/retry', {
        method: 'POST'
    }).then(response => response.json())
      .then(data => {
        console.log('Session reset:', data);
        resetUI();
        feedbackModal.hide();
    }).catch(error => {
        console.error('Error resetting session:', error);
    });
});

// Reset the UI components
function resetUI() {
    transcriptDisplay.textContent = 'Transcript will appear here...';
    confidenceDisplay.textContent = 'This will be the degree of accuracy of the speech recognizer\'s response';
    recordingStatus.textContent = 'Status: Not recording';
    readTranscriptSection.style.display = 'none';
    grammarFeedbackSection.style.display = 'none';
    filename.textContent = ''
    
}

// Show feedback in UI
function showFeedback(data) {
    console.log('showFeedback data', data);
    document.getElementById('read-transcript').textContent = data.gpt_text || 'No improvements available.';
    let grammarList = document.getElementById('grammar-feedback');
    grammarList.innerHTML = '';
    (data.grammar_issues || []).forEach(issue => {
        let listItem = document.createElement('li');
        listItem.textContent = `${issue.message} - Suggested: ${issue.suggestions.map((suggestion) => suggestion.value).join(', ')}`;
        grammarList.appendChild(listItem);
    });
    readTranscriptSection.style.display = 'block';
    grammarFeedbackSection.style.display = 'block';
}

// Socket.IO events for real-time transcript and confidence updates
socket.on('transcript_update', function(data) {
    console.log(data);  

    // Update transcript history and display
    if (data.is_final) {
        transcriptHistory += data.transcript + " ";
        transcriptDisplay.textContent = transcriptHistory;
    } else {
        // For interim results, you might want to show them in a separate area or handle them differently
        transcriptDisplay.textContent = transcriptHistory + data.transcript;
    }
});

socket.on('confidence_update', function(data) {
    confidenceDisplay.textContent = `Confidence: ${data.confidence.toFixed(2) * 100}%`;
});
