# MelOrch-Pro: Style-Conditioned Melody-to-Orchestration
#https://huggingface.co/spaces/norxynorzy/Melorch

A full-stack web application that converts melodies into complete orchestrations with style conditioning using a Transformer encoder-decoder model.

## Quick Start (30 seconds)

### Option 1: Windows Users
1. Double-click `start_backend.bat`
2. Wait for "Starting on http://localhost:5000"
3. Open `index.html` in your browser
4. Upload or draw a melody, select a style, click ORCHESTRATE, download MIDI

### Option 2: Command Line
```bash
# Install dependencies
pip install -r requirements-backend.txt

# Start backend
python app.py

# In browser, open index.html
```

## Features

✓ **Style Conditioning**: 3 orchestration styles (EPIC, SOFT, DARK)
✓ **Multi-Instrument**: Generates 4 instruments (Strings, Bass, Brass, Piano)
✓ **Web UI**: Interactive piano roll + real-time visualization
✓ **MIDI Upload**: Upload your own melodies
✓ **Download**: Export orchestrated MIDI files
✓ **Fallback Mode**: Works offline with simulation

## Architecture

### Backend (Python/Flask)
```
app.py              - REST API server
model.py            - Transformer encoder-decoder
tokenizer.py        - MIDI ↔ Token conversion
config.py           - Model configuration
model.pth           - Pre-trained weights (~8M params)
```

### Frontend (HTML5)
```
index.html          - Web UI with canvas visualization
                    - Piano roll input
                    - Style selector
                    - MIDI file upload/download
                    - Real-time visualization
```

## REST API Endpoints

### Health Check
```
GET /api/health
```
Returns: Backend status, device info, model loaded state

### Model Info
```
GET /api/info
```
Returns: Model specs, styles, instruments, parameters

### Upload & Orchestrate
```
POST /api/orchestrate
Content-Type: multipart/form-data

Parameters:
  - file: MIDI file
  - style: "EPIC" | "SOFT" | "DARK"

Returns: Orchestrated MIDI file (binary)
```

**Example with cURL:**
```bash
curl -X POST \
  -F "file=@melody.mid" \
  -F "style=EPIC" \
  http://localhost:5000/api/orchestrate \
  -o orchestrated.mid
```

### Generate from Note Array
```
POST /api/generate-from-notes
Content-Type: application/json

{
  "notes": [
    {"step": 0, "pitch": 60, "dur": 1.0},
    {"step": 1, "pitch": 62, "dur": 1.0}
  ],
  "style": "EPIC",
  "tempo": 120
}

Returns: Orchestrated MIDI file (binary)
```

## Web Interface Guide

### 1. Select Style
Choose between:
- **EPIC**: Wide harmonic sustain, strong brass support
- **SOFT**: Sparse orchestration, light strings
- **DARK**: Lower register focus, bass and brass-forward

### 2. Input Melody
Three options:
1. **Upload MIDI**: Click "CHOOSE FILE" to upload your melody
2. **Use Preset**: Click preset buttons (Ode to Joy, Moonlight, Bach)
3. **Draw Custom**: Click on piano roll to draw notes

### 3. Generate
Click "ORCHESTRATE" button
- Shows real-time generation progress
- Displays 4 instrument tracks with visualization
- Shows metrics (notes, time, style, status)

### 4. Download
Click "DOWNLOAD MIDI" to save the result
- File format: `orchestrated_{style}.mid`
- Contains 4 separate instrument tracks
- Ready to open in any DAW

## Testing

### Run Test Suite
```bash
python test_backend.py
```

Tests:
- ✓ API Health
- ✓ Model Info
- ✓ File Upload & Orchestration
- ✓ JSON Note Input
- ✓ All 3 Styles

### Manual Testing

**Test 1: File Upload**
```bash
curl -X POST \
  -F "file=@test.mid" \
  -F "style=EPIC" \
  http://localhost:5000/api/orchestrate \
  -o result.mid
```

**Test 2: JSON Input**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "notes": [
      {"step": 0, "pitch": 60, "dur": 1.0},
      {"step": 1, "pitch": 62, "dur": 1.0}
    ],
    "style": "SOFT",
    "tempo": 120
  }' \
  http://localhost:5000/api/generate-from-notes \
  -o result.mid
```

## Troubleshooting

### Backend Won't Start
```
Error: ModuleNotFoundError: No module named 'torch'
→ Install dependencies: pip install -r requirements-backend.txt
```

### Connection Refused
```
Error: Connection refused @ localhost:5000
→ Make sure Flask server is running: python app.py
→ Check port 5000 is not in use
```

### "Backend offline - using simulation mode"
```
→ Backend is not running or not accessible
→ Start server: python app.py
→ Check firewall settings
```

### Out of Memory
```
CUDA out of memory error
→ Edit config.py: set device = "cpu"  # Use CPU instead
→ Or reduce batch_size if needed
```

### Generation is slow
```
Using CPU: ~30-60 seconds per melody
Using GPU: ~5-15 seconds per melody
→ Check Device in /api/health endpoint
```

## Model Details

**Architecture:**
- Transformer Encoder: 4 layers, 320 hidden dims, 8 heads
- Transformer Decoder: 4 layers, 320 hidden dims, 8 heads
- FiLM conditioning for style tokens
- Autoregressive token-based generation

**Training:**
- Dataset: LOP + Filtered Lakh (1,062 hybrid samples)
- Final Loss: 0.11
- Total Parameters: ~8M
- Trained for: 15 epochs

**Input/Output:**
- Vocab Size: 400 tokens
- Max Sequence: 384 tokens
- Token Types: NOTE, DUR, INST, STYLE, special tokens
- Instruments: Strings (48), Bass (32), Brass (56), Piano (0)

**Generation:**
- Method: Autoregressive with top-k (k=12) sampling
- Temperature: 1.1
- Repetition penalty: 0.85

## Files

```
melorch_film/
├── app.py                      # Flask backend server
├── model.py                    # Transformer model
├── tokenizer.py                # MIDI tokenizer
├── config.py                   # Configuration
├── model.pth                   # Pre-trained weights
├── index.html                  # Web UI (main interface)
├── requirements-backend.txt    # Python dependencies
├── test_backend.py             # API test suite
├── SETUP.md                    # Detailed setup guide
├── start_backend.bat           # Windows launcher
├── README.md                   # This file
└── data/
    └── raw/
        ├── LOP/                # LOP dataset
        └── lakh_filtered/      # Filtered Lakh MIDI
```

## Usage Examples

### Example 1: Interactive Web Interface
1. Open `index.html` in browser
2. Select "EPIC" style
3. Click preset "Ode to Joy"
4. Click "ORCHESTRATE"
5. Wait ~10 seconds
6. Click "DOWNLOAD MIDI"

### Example 2: Upload Own MIDI
1. Prepare melody MIDI file (single track)
2. Open `index.html`
3. Click "CHOOSE FILE" → select MIDI
4. Select desired style
5. Click "ORCHESTRATE"
6. Download result

### Example 3: Command Line API
```bash
# Simple bash script to orchestrate files
for midi in *.mid; do
  curl -X POST \
    -F "file=@$midi" \
    -F "style=EPIC" \
    http://localhost:5000/api/orchestrate \
    -o "orchestrated_$midi"
done
```

### Example 4: Python Client
```python
import requests

def orchestrate(midi_file, style='EPIC'):
    with open(midi_file, 'rb') as f:
        files = {'file': f}
        data = {'style': style}
        
        response = requests.post(
            'http://localhost:5000/api/orchestrate',
            files=files,
            data=data
        )
        
        if response.status_code == 200:
            with open(f'orchestrated_{style}.mid', 'wb') as out:
                out.write(response.content)
            print("✓ Orchestration complete!")
        else:
            print(f"✗ Error: {response.status_code}")

# Usage
orchestrate('my_melody.mid', style='DARK')
```

## Performance

| Device | Time | Notes/sec |
|--------|------|-----------|
| GPU (RTX 3090) | 5-8s | ~200-300 |
| GPU (RTX 2060) | 8-15s | ~100-150 |
| CPU (i7-10700) | 30-60s | ~20-40 |

## Building from Scratch

If you want to retrain the model:

1. **Prepare Dataset**
   ```bash
   python dataset.py  # Processes LOP + Lakh
   python filter_lakh.py  # Filters Lakh dataset
   ```

2. **Train Model**
   ```bash
   python train.py  # Trains from config
   ```

3. **Generate**
   ```bash
   python generate.py  # Generates with trained model
   ```

## Browser Compatibility

✓ Chrome/Chromium (recommended)
✓ Edge
✓ Firefox
✓ Safari

Requires: HTML5 Canvas, Fetch API, ES6 JavaScript

## Limitations

- Input melody should be: single track, clear note boundaries, 30-120 notes
- Generation time scales with melody length
- CUDA GPU highly recommended for interactive use
- Maximum sequence length: 384 tokens

## Future Improvements

- [ ] MIDI playback in browser
- [ ] Style mixing/blending
- [ ] Real-time streaming generation
- [ ] More styles (Classical, Jazz, etc.)
- [ ] Duration/intensity controls
- [ ] Export as audio (WAV/MP3)

## Citation

If you use MelOrch-Pro in your research, please cite:

```bibtex
@article{melorch2024,
  title={MelOrch-Pro: Style-Conditioned Melody-to-Orchestration 
         using Transformer Encoder-Decoder},
  author={Kiran, G. Uday and Diana, P. Honey and Pentakoti, Ajay},
  institution={BVRIT Hyderabad, Telangana, India},
  year={2024}
}
```

## License

Research prototype - BVRIT, 2026

## Authors 
- **Ajay Pentakoti** - BVRIT, Hyderabad

---

**Need Help?**
- Check `SETUP.md` for detailed installation
- Run `python test_backend.py` to verify setup
- Check browser console for frontend errors
- Check server logs for backend errors

**Quick Links:**
- Web Interface: `index.html`
- Backend: `app.py`
- Tests: `test_backend.py`
- Setup: `SETUP.md`
