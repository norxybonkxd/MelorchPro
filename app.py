"""
MelOrch-Pro Flask Backend
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
    
    Args:
        midi_path: Path to input melody MIDI
        style: One of 'EPIC', 'SOFT', 'DARK'
    
    Returns:
        Path to output orchestrated MIDI
    """
    
    # Load input MIDI
    try:
        midi = pretty_midi.PrettyMIDI(midi_path)
    except Exception as e:
        raise ValueError(f"Could not load MIDI: {e}")
    
    if len(midi.instruments) == 0:
        raise ValueError("Input MIDI has no instruments")
    
    melody = midi.instruments[0]
    if len(melody.notes) == 0:
        raise ValueError("First instrument has no notes")
    
    print(f"[INFO] Loaded melody with {len(melody.notes)} notes")
    
    # ========= ENCODING =========
    enc_tokens = []
    
    # Add style token at start
    style_token = f"STYLE_{style}"
    if style_token not in tokenizer.token2id:
        style_token = "STYLE_EPIC"
    
    enc_tokens.append(tokenizer.token2id[style_token])
    
    # Distribute input melody across instruments
    melody_len = len(melody.notes)
    notes_per_inst = max(1, melody_len // 4)
    
    for melody_idx, note in enumerate(melody.notes):
        # Determine which instrument gets this note
        inst_idx = min(melody_idx // notes_per_inst, 3)
        
        # Add instrument token
        inst_token = tokenizer.token2id.get(f"INST_{inst_idx}", tokenizer.token2id.get("INST_0"))
        enc_tokens.append(inst_token)
        
        # Add pitch
        pitch_token = f"NOTE_{int(note.pitch)}"
        if pitch_token in tokenizer.token2id:
            enc_tokens.append(tokenizer.token2id[pitch_token])
        
        # Add duration
        dur = min(int((note.end - note.start) * 4), 31)
        dur_token = f"DUR_{dur}"
        if dur_token in tokenizer.token2id:
            enc_tokens.append(tokenizer.token2id[dur_token])
    
    # Truncate to max length
    enc_tokens = enc_tokens[:config.max_len]
    
    print(f"[INFO] Encoded {len(melody.notes)} melody notes distributed across 4 instruments → {len(enc_tokens)} tokens")
    
    if len(enc_tokens) == 0:
        raise ValueError("Could not encode melody")
    
    src = torch.tensor([enc_tokens]).to(device)
    
    # ========= DECODING =========
    # Generate rich orchestration with style conditioning
    all_generated_tokens = []
    
    style_params = {
        'EPIC': {
            'density': 0.7,
            'harmonic_intervals': [0, 4, 7, 12, 16, 19],
            'temp': 0.95,
            'top_k': 20,
            'sustain_mult': 1.6,
            'vel_base': 100
        },
        'SOFT': {
            'density': 0.4,
            'harmonic_intervals': [0, 4, 7],
            'temp': 1.2,
            'top_k': 12,
            'sustain_mult': 1.8,
            'vel_base': 75
        },
        'DARK': {
            'density': 0.6,
            'harmonic_intervals': [0, 3, 7, 10],
            'temp': 0.9,
            'top_k': 18,
            'sustain_mult': 1.5,
            'vel_base': 90
        }
    }
    
    params = style_params.get(style, style_params['EPIC'])
    # Reserve space proportionally: melody gets ~40% of context, generation gets ~60%
    max_generation_tokens = int((config.max_len - len(enc_tokens)) * 0.85)
    tokens_per_inst = max(20, max_generation_tokens // 4)  # Divide equally among 4 instruments
    
    print(f"[INFO] Token budget: {max_generation_tokens} total ({tokens_per_inst} per instrument)")
    
    for inst_idx in range(4):
        print(f"[INFO] Generating {['Strings', 'Bass', 'Brass', 'Piano'][inst_idx]} (max {tokens_per_inst} tokens)...")
        
        generated = [tokenizer.token2id["START"]]
        inst_token = tokenizer.token2id.get(f"INST_{inst_idx}", tokenizer.token2id["START"])
        generated.append(inst_token)
        
        max_steps = min(tokens_per_inst - 2, 80)  # Limit generation steps
        step_count = 0
        
        for step in range(max_steps):
            # Safety check: don't exceed total budget
            if len(all_generated_tokens) + len(generated) >= config.max_len:
                print(f"[INFO]   → Reached token budget at step {step}")
                break
            
            tgt = torch.tensor([generated]).to(device)
            
            with torch.no_grad():
                logits = model(src, tgt)
            
            logits = logits[0, -1]
            
            # ===== STYLE-SPECIFIC LOGIT BIASING =====
            # Apply harmonic interval preferences based on style
            for note_token in tokenizer.token2id.keys():
                if note_token.startswith("NOTE_"):
                    try:
                        note_pitch = int(note_token.split("_")[1])
                        token_id = tokenizer.token2id[note_token]
                        
                        # Check if this pitch matches harmonic intervals for the style
                        is_harmonic = False
                        for interval in params['harmonic_intervals']:
                            if note_pitch % 12 == interval % 12:
                                is_harmonic = True
                                break
                        
                        # Boost harmonic tones, suppress dissonant ones
                        if is_harmonic:
                            logits[token_id] *= 1.3 * params['density']  # Boost harmonically relevant notes
                        else:
                            logits[token_id] *= 0.5 * (1 - params['density'])  # Suppress non-harmonic
                    except:
                        pass
            
            # Soft repetition penalty
            for prev_token in set(generated[-12:]):
                logits[prev_token] *= 0.82
            
            # Style-based temperature
            logits = logits / params['temp']
            probs = F.softmax(logits, dim=-1)
            
            # Top-K sampling with style-specific k
            top_k = min(params['top_k'], 50)
            top_probs, top_indices = torch.topk(probs, top_k)
            top_probs = top_probs / torch.sum(top_probs)
            
            next_token = top_indices[torch.multinomial(top_probs, 1)].item()
            next_token_str = tokenizer.id2token.get(next_token, "")
            
            generated.append(next_token)
            step_count += 1
            
            if next_token_str == "END":
                break
        
        all_generated_tokens.extend(generated[1:])
        print(f"[INFO]   → {step_count} steps, total tokens now: {len(all_generated_tokens)}")
    
    # Add final END and ensure we don't exceed limit
    all_generated_tokens.append(tokenizer.token2id.get("END", tokenizer.token2id["START"]))
    all_generated_tokens = all_generated_tokens[:max_generation_tokens]
    
    generated = all_generated_tokens
    print(f"[INFO] Final generated sequence: {len(generated)} tokens")
    
    print(f"[INFO] Generated {len(generated)} tokens")
    
    # ========= MIDI CONVERSION =========
    out_midi = pretty_midi.PrettyMIDI()
    
    # Orchestral mapping
    instrument_programs = [
        48,  # Strings - vivid strings
        32,  # Bass
        56,  # Brass
        0    # Piano
    ]
    
    instrument_names = ["Strings", "Bass", "Brass", "Piano"]
    instruments = [
        pretty_midi.Instrument(program=p, name=n)
        for p, n in zip(instrument_programs, instrument_names)
    ]
    
    # ========= FIRST: ADD INPUT MELODY TO STRINGS WITH SUSTAIN ==========
    print("[INFO] Adding input melody to Strings with cinematic sustain...")
    for note in melody.notes:
        # Extend duration for cinematic effect
        sustain_mult = params['sustain_mult'] if style == 'EPIC' else (1.8 if style == 'SOFT' else 1.5)
        extended_dur = note.end - note.start
        
        instruments[0].notes.append(
            pretty_midi.Note(
                velocity=params['vel_base'] + 5,  # Strings slightly louder
                pitch=int(note.pitch),
                start=note.start,
                end=note.start + extended_dur * sustain_mult  # Extended sustain
            )
        )
    
    # Add harmonic support in strings (add octaves and harmonies)
    for note in melody.notes:
        if style in ['EPIC', 'DARK']:  # Full harmonics for dramatic styles
            # Add 5th above
            fifth_pitch = (note.pitch + 7) % 12 + (note.pitch // 12) * 12
            if fifth_pitch < 128:
                sustained_dur = (note.end - note.start) * params['sustain_mult']
                instruments[0].notes.append(
                    pretty_midi.Note(
                        velocity=params['vel_base'] - 10,  # Slightly softer
                        pitch=int(fifth_pitch),
                        start=note.start,
                        end=note.start + sustained_dur
                    )
                )
    
    print(f"[INFO]   → Strings: {len(instruments[0].notes)} notes (melody + harmonics)")
    
    # ========= SECOND: GENERATE INTELLIGENT ORCHESTRATION ==========
    print(f"[INFO] Generating intelligent {style} orchestration for other instruments...")
    
    # Parse generated tokens and build rich orchestration
    current_inst = 1  # Start from Bass
    inst_time_cursors = [note.end for note in melody.notes]
    inst_time_cursors = [max(inst_time_cursors) if inst_time_cursors else 0 for _ in range(4)]
    
    i = 0
    notes_added = 0
    
    while i < len(generated):
        token = tokenizer.id2token.get(generated[i], "")
        
        # Instrument switch
        if token.startswith("INST_"):
            try:
                inst_num = int(token.split("_")[1]) % 4
                if inst_num > 0:
                    current_inst = inst_num
            except:
                pass
            i += 1
        
        # Note parsing
        elif token.startswith("NOTE_"):
            try:
                pitch = int(token.split("_")[1])
            except:
                i += 1
                continue
            
            # Look ahead for duration
            if i + 1 < len(generated):
                next_tok = tokenizer.id2token.get(generated[i + 1], "")
                
                if next_tok and next_tok.startswith("DUR_"):
                    try:
                        dur_val = int(next_tok.split("_")[1])
                        dur = max(0.15, dur_val / 4.0)
                    except:
                        dur = 0.5
                    
                    # Cinematic sustain based on instrument and style
                    sustain_map = {
                        1: 0.8,   # Bass - shorter accents
                        2: 1.1,   # Brass - moderate sustain
                        3: 0.7    # Piano - short percussive
                    }
                    sustain_mult = sustain_map.get(current_inst, 1.0)
                    final_dur = dur * sustain_mult
                    
                    if 0 <= pitch < 128 and current_inst > 0:
                        # Velocity variation per instrument and style
                        vel_map = {
                            1: {'EPIC': 115, 'SOFT': 80, 'DARK': 100},    # Bass
                            2: {'EPIC': 105, 'SOFT': 70, 'DARK': 95},    # Brass
                            3: {'EPIC': 90, 'SOFT': 65, 'DARK': 85}      # Piano
                        }
                        base_velocity = vel_map.get(current_inst, {}).get(style, 90)
                        
                        # Add style-specific velocity variation
                        if style == 'EPIC':
                            velocity = base_velocity + torch.randint(-15, 20, (1,)).item()
                        elif style == 'SOFT':
                            velocity = base_velocity + torch.randint(-8, 8, (1,)).item()
                        else:  # DARK
                            velocity = base_velocity + torch.randint(-10, 5, (1,)).item()
                        
                        velocity = max(30, min(127, velocity))  # Clamp to valid range
                        
                        start_time = inst_time_cursors[current_inst]
                        
                        note = pretty_midi.Note(
                            velocity=velocity,
                            pitch=pitch,
                            start=start_time,
                            end=start_time + final_dur
                        )
                        
                        instruments[current_inst].notes.append(note)
                        inst_time_cursors[current_inst] = start_time + final_dur * 0.8
                        notes_added += 1
                    
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1
    
    # ========= FALLBACK: Generate rich supporting voices ==========
    if notes_added < len(melody.notes) * 2:  # If orchestration is sparse
        print(f"[INFO] Enriching orchestration with harmonic accompaniment...")
        
        # Define sustain and velocity maps
        sustain_map = {
            1: 0.8,   # Bass
            2: 1.1,   # Brass
            3: 0.7    # Piano
        }
        
        vel_map = {
            1: {'EPIC': 115, 'SOFT': 80, 'DARK': 100},    # Bass
            2: {'EPIC': 105, 'SOFT': 70, 'DARK': 95},    # Brass
            3: {'EPIC': 90, 'SOFT': 65, 'DARK': 85}      # Piano
        }
        
        harmonic_rules = {
            1: (-12, 0.95),   # Bass - octave down
            2: (7, 1.0),      # Brass - perfect 5th
            3: (-5, 0.85)     # Piano - perfect 4th down
        }
        
        for note in melody.notes:
            for inst_idx in [1, 2, 3]:
                transpose, vel_factor = harmonic_rules[inst_idx]
                harm_pitch = note.pitch + transpose
                
                if 0 <= harm_pitch < 128:
                    sustained = (note.end - note.start) * sustain_map.get(inst_idx, 1.0)
                    vel_base = vel_map.get(inst_idx, {}).get(style, 90)
                    
                    instruments[inst_idx].notes.append(
                        pretty_midi.Note(
                            velocity=int(vel_base * vel_factor),
                            pitch=int(harm_pitch),
                            start=note.start,
                            end=note.start + sustained
                        )
                    )
                    notes_added += 1
        
        print(f"[INFO]   → Added harmonic backup (total now {notes_added} accompaniment notes)")
    
    # ========= ADD ALL INSTRUMENTS TO OUTPUT ==========
    for inst in instruments:
        out_midi.instruments.append(inst)
        print(f"[INFO] → {inst.name}: {len(inst.notes)} notes")
    
    # Save to temp file
    output_path = tempfile.NamedTemporaryFile(suffix='.mid', delete=False).name
    out_midi.write(output_path)
    
    total_notes = sum(len(inst.notes) for inst in out_midi.instruments)
    print(f"[INFO] ✓ Cinematic orchestration complete!")
    print(f"[INFO]   → Total: {total_notes} notes")
    print(f"[INFO]   → Strings:  {len(out_midi.instruments[0].notes)} (melody + harmonics)")
    print(f"[INFO]   → Bass:     {len(out_midi.instruments[1].notes)} (foundation)")
    print(f"[INFO]   → Brass:    {len(out_midi.instruments[2].notes)} (accent)")
    print(f"[INFO]   → Piano:    {len(out_midi.instruments[3].notes)} (support)")
    
    # Return note_count including melody + all generated
    return output_path, len(melody.notes) + notes_added

# ============= STATIC ROUTES =============

@app.route('/', methods=['GET'])
def index():
    """Serve the HTML demo interface"""
    return send_file('index.html', mimetype='text/html')

@app.route('/index.html', methods=['GET'])
def index_direct():
    """Direct access to index.html"""
    return send_file('index.html', mimetype='text/html')

# ============= API ROUTES =============

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'device': str(device),
        'model_loaded': True
    })

@app.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main orchestration endpoint.
    
    Expects:
        - file: MIDI file upload
        - style: Style token (epic, soft, dark) - default epic
    
    Returns:
        - JSON with orchestration data and tracks
    """
    
    global last_output_midi
    
    try:
        import time
        start_time = time.time()
        
        # Check file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Validate extension
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in app.config['UPLOAD_EXTENSIONS']):
            return jsonify({'error': 'File must be .mid or .midi'}), 400
        
        # Get style (convert lowercase from frontend to uppercase)
        style = request.form.get('style', 'epic').upper()
        if style not in ['EPIC', 'SOFT', 'DARK']:
            style = 'EPIC'
        
        # Save temp input
        input_path = tempfile.NamedTemporaryFile(suffix='.mid', delete=False).name
        file.save(input_path)
        
        print(f"\n[API] Orchestrating with style: {style}")
        
        # Orchestrate
        output_path, note_count = orchestrate_melody(input_path, style)
        last_output_midi = output_path  # Store for download
        
        # Clean up input
        try:
            os.unlink(input_path)
        except:
            pass
        
        # Parse output MIDI to extract track data
        try:
            out_midi = pretty_midi.PrettyMIDI(output_path)
            
            tracks = []
            for inst_idx, instrument in enumerate(out_midi.instruments[:4]):  # First 4 instruments
                track_notes = []
                for note in instrument.notes:
                    step = int(note.start * 4)  # Convert seconds to steps
                    track_notes.append({
                        'step': step,
                        'pitch': int(note.pitch),
                        'velocity': note.velocity / 127.0,
                        'duration': note.end - note.start
                    })
                tracks.append(track_notes)
            
            # Pad to 4 tracks if fewer
            while len(tracks) < 4:
                tracks.append([])
            
            processing_time = time.time() - start_time
            
            response_data = {
                'success': True,
                'orchestration': {
                    'style': style,
                    'input_notes': note_count,
                    'tracks': tracks,
                    'track_names': ['Strings', 'Bass', 'Brass', 'Piano']
                },
                'processing_time': processing_time
            }
            
            return jsonify(response_data)
        
        except Exception as parse_err:
            print(f"[ERROR] Failed to parse output MIDI: {parse_err}")
            return jsonify({
                'error': f'Generated MIDI but parsing failed: {str(parse_err)}'
            }), 500
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/download-midi', methods=['GET'])
def download_midi():
    """Download the last orchestrated MIDI file"""
    global last_output_midi
    
    if not last_output_midi or not os.path.exists(last_output_midi):
        return jsonify({'error': 'No orchestration generated yet'}), 400
    
    try:
        return send_file(
            last_output_midi,
            mimetype='audio/midi',
            as_attachment=True,
            download_name='orchestration.mid'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-from-notes', methods=['POST'])
def generate_from_notes():
    """
    Generate orchestration from raw note data (for HTML demo).
    
    Expects JSON:
        {
            "notes": [{"step": 0, "pitch": 60, "dur": 1}, ...],
            "style": "EPIC",
            "tempo": 120
        }
    
    Returns:
        JSON with generated orchestration data or MIDI file
    """
    
    try:
        data = request.get_json()
        
        if 'notes' not in data or not isinstance(data['notes'], list):
            return jsonify({'error': 'Invalid notes format'}), 400
        
        style = data.get('style', 'EPIC').upper()
        if style not in ['EPIC', 'SOFT', 'DARK']:
            style = 'EPIC'
        
        tempo = int(data.get('tempo', 120))
        
        # Create temporary MIDI from note array
        temp_midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
        instrument = pretty_midi.Instrument(program=0, name='Melody')
        
        for note_data in data['notes']:
            try:
                step = int(note_data['step'])
                pitch = int(note_data['pitch'])
                dur = float(note_data.get('dur', 0.5))
                
                # Convert step to time (assuming 16th note subdivision)
                start_time = step * (60.0 / tempo / 4)
                end_time = start_time + dur
                
                note = pretty_midi.Note(
                    velocity=80,
                    pitch=pitch,
                    start=start_time,
                    end=end_time
                )
                instrument.notes.append(note)
            except Exception as e:
                print(f"[WARNING] Could not parse note: {e}")
                continue
        
        temp_midi.instruments.append(instrument)
        
        # Save and orchestrate
        input_path = tempfile.NamedTemporaryFile(suffix='.mid', delete=False).name
        temp_midi.write(input_path)
        
        print(f"\n[API] Generating orchestration for {len(data['notes'])} notes, style: {style}")
        
        output_path, note_count = orchestrate_melody(input_path, style)
        
        # Clean up
        try:
            os.unlink(input_path)
        except:
            pass
        
        # Return MIDI file
        return send_file(
            output_path,
            mimetype='audio/midi',
            as_attachment=True,
            download_name=f'orchestrated_{style.lower()}.mid'
        )
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/info', methods=['GET'])
def info():
    """Model info endpoint"""
    return jsonify({
        'model': 'MelOrch-Pro',
        'version': '1.0',
        'styles': ['EPIC', 'SOFT', 'DARK'],
        'instruments': ['Strings', 'Bass', 'Brass', 'Piano'],
        'parameters': config.d_model,
        'encoder_layers': config.n_encoder_layers,
        'decoder_layers': config.n_decoder_layers,
        'vocab_size': config.vocab_size,
        'device': str(device)
    })

# ============= MAIN =============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n[INIT] MelOrch-Pro API Server")
    print(f"[INIT] Device: {device}")
    print(f"[INIT] Starting on http://localhost:{port}\n")
    
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
