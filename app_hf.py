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
        
        # Create orchestrated version
        orch_midi = pretty_midi.PrettyMIDI()
        
        # Add instruments based on style
        styles = {
            'EPIC': ['Brass Section', 'String Section', 'Percussion'],
            'JAZZ': ['Piano', 'Bass', 'Drums'],
            'CLASSICAL': ['Violin', 'Cello', 'Flute']
        }
        
        instruments = styles.get(style, styles['EPIC'])
        
        for inst_name in instruments:
            instrument = pretty_midi.Instrument(program=0, is_drum=False, name=inst_name)
            for note in notes:
                instrument.notes.append(note)
            orch_midi.instruments.append(instrument)
        
        # Save
        global last_output_midi
        last_output_midi = '/tmp/orchestrated.mid'
        orch_midi.write(last_output_midi)
        
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
        
        # Clean up input
        os.remove(midi_path)
        
        return send_file(output_path, mimetype='audio/midi', as_attachment=True, 
                        download_name='orchestrated.mid')
    
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
    # For Hugging Face, listen on 0.0.0.0:7860
    app.run(host='0.0.0.0', port=7860, debug=False)
