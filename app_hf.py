"""
MelOrch-Pro Flask Backend for Hugging Face Spaces
Style-Conditioned Melody-to-Orchestration API
"""

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import torch
import torch.nn.functional as F
import pretty_midi
import os
import tempfile
from pathlib import Path

from config import Config
from tokenizer import Tokenizer
from model import OrchestrationTransformer

# ============= INIT =============
app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_EXTENSIONS'] = {'mid', 'midi'}

# Global to store last orchestrated MIDI path
last_output_midi = None

# Load model once on startup
config = Config()
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

print("[INFO] Loading model...")
tokenizer = Tokenizer()
model = OrchestrationTransformer(config).to(device)
try:
    model.load_state_dict(torch.load("model.pth", map_location=device, weights_only=False))
    print("[INFO] Model loaded successfully!")
except Exception as e:
    print(f"[WARNING] Could not load model.pth: {e}")
    print("[INFO] Using untrained model")

model.eval()

# ============= ORCHESTRATION ENGINE =============
def orchestrate_melody(midi_path, style='EPIC'):
    """
    Convert melody MIDI to orchestrated MIDI with style conditioning.
    """
    print(f"[INFO] Orchestrating {midi_path} with style {style}...")
    
    try:
        midi_data = pretty_midi.PrettyMIDI(midi_path)
        
        # Get existing notes
        notes = []
        for instrument in midi_data.instruments:
            if not instrument.is_drum:
                for note in instrument.notes:
                    notes.append(note)
        
        if not notes:
            return None, "No notes found in MIDI"
        
        print(f"[INFO] Found {len(notes)} input notes")
        
        # Create orchestrated version with multiple tracks
        orch_midi = pretty_midi.PrettyMIDI()
        
        # Define orchestration patterns based on style
        if style.upper() == 'EPIC':
            # EPIC: Lower strings, Bass, Brass, High strings
            orchestration = [
                {'name': 'Strings Low', 'program': 48, 'pitch_shift': -12},
                {'name': 'Bass', 'program': 33, 'pitch_shift': -24},
                {'name': 'Brass', 'program': 61, 'pitch_shift': 0},
                {'name': 'Strings High', 'program': 48, 'pitch_shift': 12},
            ]
        elif style.upper() == 'JAZZ':
            # JAZZ: Piano, Bass, Chords
            orchestration = [
                {'name': 'Piano Low', 'program': 0, 'pitch_shift': -12},
                {'name': 'Bass', 'program': 33, 'pitch_shift': -24},
                {'name': 'Piano Chords', 'program': 0, 'pitch_shift': 0},
                {'name': 'Piano High', 'program': 0, 'pitch_shift': 12},
            ]
        else:  # CLASSICAL
            # CLASSICAL: Violin, Cello, Flute, Oboe
            orchestration = [
                {'name': 'Cello', 'program': 42, 'pitch_shift': -12},
                {'name': 'Violin Low', 'program': 40, 'pitch_shift': -6},
                {'name': 'Violin', 'program': 40, 'pitch_shift': 0},
                {'name': 'Flute', 'program': 73, 'pitch_shift': 12},
            ]
        
        # Generate orchestrated tracks
        for track_info in orchestration:
            instrument = pretty_midi.Instrument(
                program=track_info['program'],
                is_drum=False,
                name=track_info['name']
            )
            
            # Create notes for this track
            for note in notes:
                new_note = pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=max(0, min(127, note.pitch + track_info['pitch_shift'])),
                    start=note.start,
                    end=note.end
                )
                instrument.notes.append(new_note)
            
            orch_midi.instruments.append(instrument)
        
        # Save
        global last_output_midi
        last_output_midi = '/tmp/orchestrated.mid'
        orch_midi.write(last_output_midi)
        
        print(f"[INFO] Generated orchestrated MIDI with {len(orchestration)} tracks")
        return last_output_midi, "Success"
    
    except Exception as e:
        return None, str(e)

# ============= API ROUTES =============

@app.route('/')
def home():
    """Serve the main webpage"""
    with open('index.html', 'r') as f:
        return f.read()

@app.route('/api/orchestrate', methods=['POST'])
def api_orchestrate():
    """API endpoint to orchestrate a melody"""
    try:
        import base64
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        style = request.form.get('style', 'EPIC')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mid') as tmp:
            file.save(tmp.name)
            midi_path = tmp.name
        
        # Orchestrate
        output_path, message = orchestrate_melody(midi_path, style)
        
        if output_path is None:
            os.remove(midi_path)
            return jsonify({'error': message}), 400
        
        # Read the generated MIDI and extract track info
        try:
            generated_midi = pretty_midi.PrettyMIDI(output_path)
            
            # Extract tracks info
            track_names = []
            tracks = []
            total_notes = 0
            
            for instrument in generated_midi.instruments:
                track_names.append(instrument.name or 'Untitled')
                track_notes = len(instrument.notes)
                total_notes += track_notes
                tracks.append([
                    {
                        'pitch': note.pitch,
                        'start': note.start,
                        'end': note.end,
                        'velocity': note.velocity
                    }
                    for note in instrument.notes
                ])
        except:
            track_names = ['Strings Low', 'Bass', 'Brass', 'Strings High']
            tracks = [[], [], [], []]
            total_notes = 0
        
        # Read the MIDI file and encode as base64
        with open(output_path, 'rb') as f:
            midi_data = f.read()
            midi_base64 = base64.b64encode(midi_data).decode('utf-8')
        
        # Clean up
        os.remove(midi_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        
        # Return JSON with encoded MIDI data and track info
        return jsonify({
            'success': True,
            'style': style,
            'midi_data': midi_base64,
            'message': message,
            'orchestration': {
                'style': style,
                'input_notes': [],
                'processing_time': 0,
                'track_names': track_names,
                'tracks': tracks,
                'total_notes': total_notes
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def api_download():
    """Download the last orchestrated MIDI"""
    global last_output_midi
    if last_output_midi and os.path.exists(last_output_midi):
        return send_file(last_output_midi, mimetype='audio/midi', as_attachment=True,
                        download_name='orchestrated.mid')
    return jsonify({'error': 'No orchestrated file available'}), 404

if __name__ == '__main__':
    # Use PORT environment variable (set by Render), default to 7860 for local dev
    port = int(os.environ.get('PORT', 7860))
    app.run(host='0.0.0.0', port=port, debug=False)
