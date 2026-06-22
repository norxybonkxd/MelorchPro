#!/usr/bin/env python3
"""
MelOrch-Pro Test Suite
Tests the backend API and model functionality
"""

import requests
import json
import pretty_midi
import time
import sys
from pathlib import Path

# Configuration
API_BASE = "http://localhost:5000"
TIMEOUT = 30

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_health():
    """Test API health endpoint"""
    print_header("TEST 1: Health Check")
    
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Status: {data.get('status')}")
            print(f"✓ Device: {data.get('device')}")
            print(f"✓ Model Loaded: {data.get('model_loaded')}")
            return True
        else:
            print(f"✗ HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        print(f"  Make sure backend is running: python app.py")
        return False

def test_info():
    """Test model info endpoint"""
    print_header("TEST 2: Model Information")
    
    try:
        response = requests.get(f"{API_BASE}/api/info", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Model: {data.get('model')}")
            print(f"✓ Version: {data.get('version')}")
            print(f"✓ Styles: {', '.join(data.get('styles', []))}")
            print(f"✓ Instruments: {', '.join(data.get('instruments', []))}")
            print(f"✓ Parameters: {data.get('parameters')}")
            return True
        else:
            print(f"✗ HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def create_test_midi():
    """Create a simple test MIDI file"""
    print_header("Creating Test MIDI")
    
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    instrument = pretty_midi.Instrument(program=0, name='Test Melody')
    
    # Simple C major scale
    notes_data = [60, 62, 64, 65, 67, 69, 71, 72]
    
    for i, pitch in enumerate(notes_data):
        start = i * 0.5
        end = start + 0.4
        note = pretty_midi.Note(
            velocity=80,
            pitch=pitch,
            start=start,
            end=end
        )
        instrument.notes.append(note)
    
    midi.instruments.append(instrument)
    
    test_path = "test_input.mid"
    midi.write(test_path)
    print(f"✓ Created: {test_path} ({len(notes_data)} notes)")
    return test_path

def test_file_upload():
    """Test file upload and orchestration"""
    print_header("TEST 3: File Upload & Orchestration")
    
    # Create test MIDI
    midi_path = create_test_midi()
    
    try:
        with open(midi_path, 'rb') as f:
            files = {'file': f}
            data = {'style': 'EPIC'}
            
            print(f"\nSending request to {API_BASE}/api/orchestrate...")
            start = time.time()
            
            response = requests.post(
                f"{API_BASE}/api/orchestrate",
                files=files,
                data=data,
                timeout=TIMEOUT * 3  # Longer timeout for generation
            )
            
            elapsed = time.time() - start
            
            if response.status_code == 200:
                output_path = "test_output.mid"
                with open(output_path, 'wb') as out:
                    out.write(response.content)
                
                # Verify output
                out_midi = pretty_midi.PrettyMIDI(output_path)
                total_notes = sum(len(i.notes) for i in out_midi.instruments)
                
                print(f"✓ Generation time: {elapsed:.2f}s")
                print(f"✓ Output instruments: {len(out_midi.instruments)}")
                print(f"✓ Total notes: {total_notes}")
                print(f"✓ Saved to: {output_path}")
                return True
            else:
                print(f"✗ HTTP {response.status_code}")
                if response.text:
                    try:
                        error = response.json()
                        print(f"  Error: {error.get('error', response.text)}")
                    except:
                        print(f"  Response: {response.text[:200]}")
                return False
                
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        # Cleanup
        p = Path(midi_path)
        if p.exists():
            p.unlink()

def test_json_input():
    """Test JSON note array input"""
    print_header("TEST 4: JSON Note Array Input")
    
    # Create note array
    notes = [
        {"step": 0, "pitch": 60, "dur": 1.0},
        {"step": 1, "pitch": 62, "dur": 1.0},
        {"step": 2, "pitch": 64, "dur": 1.0},
        {"step": 3, "pitch": 65, "dur": 1.0},
        {"step": 4, "pitch": 67, "dur": 1.0},
    ]
    
    payload = {
        "notes": notes,
        "style": "SOFT",
        "tempo": 120
    }
    
    try:
        print(f"Sending {len(notes)} notes to API...")
        start = time.time()
        
        response = requests.post(
            f"{API_BASE}/api/generate-from-notes",
            json=payload,
            timeout=TIMEOUT * 3
        )
        
        elapsed = time.time() - start
        
        if response.status_code == 200:
            output_path = "test_json_output.mid"
            with open(output_path, 'wb') as out:
                out.write(response.content)
            
            out_midi = pretty_midi.PrettyMIDI(output_path)
            total_notes = sum(len(i.notes) for i in out_midi.instruments)
            
            print(f"✓ Generation time: {elapsed:.2f}s")
            print(f"✓ Instruments: {len(out_midi.instruments)}")
            print(f"✓ Total notes: {total_notes}")
            print(f"✓ Saved to: {output_path}")
            return True
        else:
            print(f"✗ HTTP {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_styles():
    """Test all style conditioning options"""
    print_header("TEST 5: Style Conditioning")
    
    midi_path = create_test_midi()
    styles = ['EPIC', 'SOFT', 'DARK']
    results = []
    
    try:
        for style in styles:
            print(f"\nTesting style: {style}")
            
            with open(midi_path, 'rb') as f:
                files = {'file': f}
                data = {'style': style}
                
                start = time.time()
                response = requests.post(
                    f"{API_BASE}/api/orchestrate",
                    files=files,
                    data=data,
                    timeout=TIMEOUT * 3
                )
                elapsed = time.time() - start
                
                if response.status_code == 200:
                    output_path = f"test_output_{style.lower()}.mid"
                    with open(output_path, 'wb') as out:
                        out.write(response.content)
                    
                    out_midi = pretty_midi.PrettyMIDI(output_path)
                    total_notes = sum(len(i.notes) for i in out_midi.instruments)
                    
                    print(f"  ✓ Time: {elapsed:.2f}s, Notes: {total_notes}")
                    results.append(True)
                else:
                    print(f"  ✗ HTTP {response.status_code}")
                    results.append(False)
                    
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(False)
    finally:
        Path(midi_path).unlink(missing_ok=True)
    
    return all(results)

def main():
    print("\n" + "="*60)
    print("  MelOrch-Pro Backend Test Suite")
    print("="*60)
    
    # Run tests
    results = {
        "Health Check": test_health(),
        "Model Info": test_info(),
        "File Upload": test_file_upload(),
        "JSON Input": test_json_input(),
        "Style Conditioning": test_styles(),
    }
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Backend is ready.")
        return 0
    else:
        print("\n✗ Some tests failed. Check server logs for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
