import logging
from flask import Flask, render_template, request, jsonify
from flask_bootstrap import Bootstrap
from flask_socketio import SocketIO
from flask_cors import CORS
import threading
import queue
import wave
import sounddevice as sd
from google.cloud import speech
from datetime import datetime
import openai
import requests
import os
import numpy as np
import speech_recognition as sr

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize clients and variables
client = speech.SpeechClient()
openai_client = openai.OpenAI()
recognizer = sr.Recognizer()
sample_rate = 16000
channels = 1
stop_recording_flag = threading.Event()
audio_queue = queue.Queue()
global_transcript = ""
local_transcript_filename = None
transcript_lock = threading.Lock()
filename_lock = threading.Lock()

def record_audio(filename='input', sample_rate=16000, channels=1, duration=None, stop_recording_flag=None):
    local_audio_filename = f"audio/{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    os.makedirs(os.path.dirname(local_audio_filename), exist_ok=True)
    
    audio_data = []

    def callback(indata, frames, time, status):
        if status:
            logging.error(f"Audio callback status: {status}")
        if stop_recording_flag and stop_recording_flag.is_set():
            raise sd.CallbackStop()
        audio_data.append(indata.copy())
    
    with sd.InputStream(samplerate=sample_rate, channels=channels, callback=callback, dtype='int16'):
        logging.info("Recording...")
        while not (stop_recording_flag and stop_recording_flag.is_set()):
            sd.sleep(100)  # Sleep for a short time to check the flag
    
    # Convert list of NumPy arrays to a single NumPy array
    audio_data = np.concatenate(audio_data, axis=0)
    
    # Save the recorded audio data to a file
    with wave.open(local_audio_filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # Assuming 16-bit audio
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    logging.info(f"Audio saved locally to {local_audio_filename}")
    return {"audio_filename": local_audio_filename}


def emit_real_time_updates(transcript, confidence, is_final=False):
    socketio.emit('transcript_update', {'transcript': transcript, 'is_final': is_final})
    socketio.emit('confidence_update', {'confidence': confidence})

def audio_callback(indata, frames, time, status):
    if status:
        logging.error(f"Audio callback status: {status}")
    if not stop_recording_flag.is_set():
        audio_queue.put(bytes(indata))
    else:
        raise sd.CallbackStop()

def request_generator(audio_queue):
    while True:
        if audio_queue.empty():
            logging.info("Audio queue is empty.")
        chunk = audio_queue.get()
        if chunk is None:
            return
        logging.info(f"Yielding audio chunk of size: {len(chunk)}")
        yield speech.StreamingRecognizeRequest(audio_content=chunk)

def handle_responses(responses, local_transcript_filename):
    full_transcript = ""
    confidence_scores = []
    
    for response in responses:
        for result in response.results:
            transcript = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence

            if result.is_final:
                full_transcript += transcript + " "
                confidence_scores.append(confidence)
                average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
                emit_real_time_updates(full_transcript, average_confidence)
                
                with open(local_transcript_filename, 'w') as f:
                    f.write(full_transcript.strip())
                logging.info(f"Transcript saved locally to {local_transcript_filename}")
    
    return {"transcript_filename": local_transcript_filename, "full_transcript": full_transcript}

def stream_audio(filename, phrases, language_code, alternative_language_code):
    global local_transcript_filename
    
    with filename_lock:
        local_transcript_filename = f"transcripts/transcript_{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        os.makedirs(os.path.dirname(local_transcript_filename), exist_ok=True)

    streaming_config = speech.StreamingRecognitionConfig(
        config=speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            language_code=language_code,
            alternative_language_codes=[alternative_language_code] if alternative_language_code else [],
            enable_automatic_punctuation=True,
            enable_word_confidence=True,
            model="latest_long",
            speech_contexts=[speech.SpeechContext(phrases=phrases)] if phrases else []
        ),
        interim_results=True
    )

    global global_transcript
    with sd.RawInputStream(samplerate=sample_rate, blocksize=1024, dtype='int16', channels=channels, callback=audio_callback) as stream:
        logging.info("Recording...")
        requests = request_generator(audio_queue)
        responses = client.streaming_recognize(streaming_config, requests)
        result = handle_responses(responses, local_transcript_filename)
        with transcript_lock:
            global_transcript = result['full_transcript']
                

@app.route('/start_recording', methods=['POST'])
def start_recording():
    try:
        stop_recording_flag.clear()
        audio_queue.queue.clear()
        data = request.json
        filename = data.get('filename', 'input')
        phrases = data.get('phrases', '')
        language_code = data.get('language_code', 'en-US')
        alternative_language_code = data.get('alternative_language_code', None)
        # To stream audio in real-time:
        threading.Thread(target=stream_audio, args=(filename, phrases, language_code, alternative_language_code)).start()
        # To record to a file:
        threading.Thread(target=record_audio, args=(filename, sample_rate, channels, None, stop_recording_flag)).start()
        
        # Return an initial response
        return jsonify({
            "message": "Recording started.",
            "transcript": ""
        })
    
    except Exception as e:
        logging.error(f"An error occurred while starting the recording: {e}")
        return jsonify({"message": "An error occurred while starting the recording."}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    try:
        stop_recording_flag.set()
        return jsonify({"message": "Recording stopped."})
    except Exception as e:
        logging.error(f"An error occurred while stopping recording: {e}")
        return jsonify({"message": "An error occurred while stopping the recording."}), 500

@app.route('/feedback', methods=['POST'])
def process_feedback():
    global local_transcript_filename

    if not local_transcript_filename:
        return jsonify({"message": "No transcript filename set."}), 500

    try:
        if not os.path.exists(local_transcript_filename):
            return jsonify({"message": "Transcript file not found."}), 404

        with open(local_transcript_filename, 'r') as file:
            transcript = file.read().strip()

        if not transcript:
            return jsonify({"message": "Transcript file is empty."}), 400
        
        language_code = request.json.get('language_code', 'en-US').strip()
        if not language_code or not language_code.replace('-', '').isalnum():
            return jsonify({"message": "Invalid language code."}), 400

        def read_transcript(text, language_code):
            try:
                completion = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an assistant that assesses spoken transcriptions. This is the transcript of a spoken text caught by a speech recognizing tool. Simply look for words or phrases that seem to be out of context in the text and might have been mispronounced. Then, display a list of said words/phrases, in case there are any, and the reason why you think they might have been misundertood by the speech recognizer or wrongly pronounced or used innacurately."},
                        {"role": "user", "content": f"{text}"}
                    ],
                    max_tokens=1000,
                )
                return completion.choices[0].message.content
            except Exception as e:
                logging.error(f"An error occurred while improving the transcript: {e}")
                return None

        def check_grammar(text, language_code='en-US'):
            try:
                url = "https://api.languagetool.org/v2/check"
                params = {'text': text, 'language': language_code}
                response = requests.post(url, data=params)
                response.raise_for_status()
                result = response.json()
                corrections = [
                    {
                        "message": match['message'],
                        "suggestions": match['replacements'],
                        "context": match['context']['text'],
                        "offset": match['context']['offset'],
                        "length": match['context']['length'],
                    }
                    for match in result['matches']
                ]
                return corrections
            except Exception as e:
                logging.error(f"An error occurred while checking grammar: {e}")
                return []

        gpt_text = read_transcript(transcript, language_code)
        if not gpt_text:
            return jsonify({"message": "Failed to read the transcript."}), 500

        grammar_issues = check_grammar(transcript, language_code)
        logging.info(f"Grammar issues: {grammar_issues}")

        feedback_content = f"Transcript\n\n{transcript}Pieces to check\n\n{gpt_text}\n\nGrammar Issues\n"
        for issue in grammar_issues:
            context = issue['context']
            suggestions = ', '.join(s['value'] for s in issue['suggestions'])
            feedback_content += f"- **Context**: {context}\n- **Suggestions**: {suggestions}\n- **Issue**: {issue['message']}\n\n"

        feedback_filename_base = os.path.splitext(os.path.basename(local_transcript_filename))[0]
        local_feedback_filename = f"transcripts/feedback/{feedback_filename_base}_feedback.txt"

        os.makedirs(os.path.dirname(local_feedback_filename), exist_ok=True)

        with open(local_feedback_filename, 'w') as f:
            f.write(feedback_content)
        logging.info(f"Feedback saved locally to {local_feedback_filename}")

        return jsonify({
            "message": "Feedback processed successfully.",
            "feedback_url": local_feedback_filename,
            "gpt_text": gpt_text,
            "grammar_issues": grammar_issues
        })

    except Exception as e:
        logging.error(f"An error occurred while processing feedback: {e}")
        return jsonify({"message": "An error occurred while processing feedback."}), 500

@app.route('/retry', methods=['POST'])
def retry():
    global stop_recording_flag, audio_queue
    try:
        stop_recording_flag.clear()
        with audio_queue.mutex:
            audio_queue.queue.clear()
        return jsonify({"message": "Session reset successfully."})
    except Exception as e:
        logging.error(f"An error occurred during retry: {e}")
        return jsonify({"message": "An error occurred while resetting the session."}), 500

if __name__ == "__main__":
    socketio.run(app, debug=True)