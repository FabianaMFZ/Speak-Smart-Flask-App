# Speak Smart Web App

![image](https://github.com/user-attachments/assets/efe7a141-6ff2-4d89-a9e0-2593be0abe93)

## Speech Recognition and Feedback Application

### Project Topic
This project focuses on building a web application for real-time speech recognition and feedback processing using Flask, Socket.IO, and various speech-to-text technologies.

### Real life application
-	Helps individuals improve their public speaking skills.
-	Useful for students, professionals, and anyone preparing for presentations or speeches.
-	Can be used in educational settings for language learning and oral presentations.
-	Can be used to transcribe meetings or conferences, providing a real-time record and feedback.
-	Enhances accessibility for individuals with hearing impairments by providing accurate transcriptions and feedback.

### Project Description
This application allows users to record audio in real-time, convert it to text using Google's Speech-to-Text API, and process the transcript for feedback. The feedback includes suggestions for improvements using GPT-based models and grammar checks using LanguageTool. Users can start and stop recording, view real-time transcription updates, and get detailed feedback on the transcript.

#### Key Features
- Real-time audio recording and streaming.
- Real-time transcription updates via Socket.IO.
- Feedback processing for the transcript using GPT-based models.
- Grammar checking using LanguageTool.
- User-friendly web interface with Bootstrap.

#### Here's a brief flow of how the web app operates:

**User Interface Interaction:**

    Start Recording: User clicks the "Start Recording" button.
        The app sends a request to /start_recording with parameters like filename, phrases, and language codes.
        The server begins recording audio and streaming it to the Google Cloud Speech API.
        Real-time updates are sent to the client via Socket.IO, including transcript and confidence updates.
  
    Stop Recording: User clicks the "Stop Recording" button.
        The app sends a request to /stop_recording.
        The server stops recording, saves the audio, and updates the interface.
        The feedback modal is shown for the user to review and provide feedback.
  
    Submit Feedback: User clicks the "Ready" button in the feedback modal.
        The app sends a request to /feedback with the transcript and language code.
        The server processes the feedback, checks grammar, and uses OpenAI to analyze the transcript.
        The feedback, including any grammar issues and improvement suggestions, is returned and displayed in the UI.
  
    Retry: User clicks the "Retry" button.
        The app sends a request to /retry to reset the session.
        The server clears the audio queue and recording state.
        The UI is reset to allow for a new recording session.

**Real-Time Updates:**
  Transcript and Confidence Updates: During recording, the server sends real-time updates about the transcript and confidence scores to the client via Socket.IO.
  The UI updates the transcript and confidence display accordingly.

**Final Processing:**  
Transcript and Feedback Handling: Once recording stops, the app provides the option to review and process the transcript, integrating feedback and grammar checks before displaying the results.

### Installation and Setup
    Clone the repository: git clone https://github.com/
    Create a virtual environment and activate it: python -m venv venv; venv\Scripts\activate
    Install dependencies: pip install -r requirements.txt
    Set up environment variables for Google Cloud credentials and OpenAI API key.
    Run the application: python app.py
    Access the application in your browser at http://localhost:5000.


