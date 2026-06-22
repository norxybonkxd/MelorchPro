import torch
import torch.nn.functional as F
import pretty_midi
from config import Config
from tokenizer import Tokenizer
from model import OrchestrationTransformer

# ======================
# Setup
# ======================
config = Config()
tokenizer = Tokenizer()

model = OrchestrationTransformer(config).to(config.device)
model.load_state_dict(torch.load("model.pth", map_location=config.device))
model.eval()

# ======================
# Load Melody
# ======================
piano_path = "saregam.mid"   # <-- change if needed

midi = pretty_midi.PrettyMIDI(piano_path)

if len(midi.instruments) == 0:
    raise ValueError("MIDI has no instruments.")

melody = midi.instruments[0]

print(f"Loaded melody: {piano_path}")
print(f"Melody notes: {len(melody.notes)}")

# ======================
# Encode Melody
# ======================
enc_tokens = []

for note in melody.notes:
    enc_tokens.append(tokenizer.token2id[f"NOTE_{note.pitch}"])
    dur = min(int((note.end - note.start) * 4), 31)
    enc_tokens.append(tokenizer.token2id[f"DUR_{dur}"])

style_id = tokenizer.token2id["STYLE_EPIC"]
enc_tokens = [style_id] + enc_tokens
enc_tokens = enc_tokens[:config.max_len]

src = torch.tensor([enc_tokens]).to(config.device)

# ======================
# Autoregressive Decoding
# ======================
generated = [tokenizer.token2id["START"]]

# generation length scaled to melody size
max_steps = max(150, len(enc_tokens) * 8)

for step in range(max_steps):

    tgt = torch.tensor([generated]).to(config.device)

    with torch.no_grad():
        logits = model(src, tgt)

    logits = logits[0, -1]

    # --- repetition penalty ---
    for prev_token in set(generated[-25:]):
        logits[prev_token] *= 0.85

    # temperature
    logits = logits / 1.1

    probs = F.softmax(logits, dim=-1)

    # top-k sampling
    top_k = 12
    top_probs, top_indices = torch.topk(probs, top_k)
    top_probs = top_probs / torch.sum(top_probs)

    next_token = top_indices[torch.multinomial(top_probs, 1)].item()
    generated.append(next_token)

    if tokenizer.id2token.get(next_token, "") == "END":
        break

print(f"Generated {len(generated)} tokens")

# ======================
# Convert Tokens → MIDI
# ======================
out_midi = pretty_midi.PrettyMIDI()

# Orchestral mapping
instrument_programs = [
    48,  # Strings
    32,  # Bass
    56,  # Brass
    0    # Piano
]

instruments = [pretty_midi.Instrument(program=p) for p in instrument_programs]

current_inst = 0
time_cursors = [0.0 for _ in range(4)]

i = 0
note_count = 0

while i < len(generated):

    token = tokenizer.id2token.get(generated[i], "")

    if token.startswith("INST_"):
        current_inst = int(token.split("_")[1]) % 4
        i += 1

    elif token.startswith("NOTE_"):
        pitch = int(token.split("_")[1])

        if i + 1 < len(generated):
            next_tok = tokenizer.id2token.get(generated[i + 1], "")

            if next_tok.startswith("DUR_"):
                dur = int(next_tok.split("_")[1]) / 4.0

                # cinematic sustain boost for strings
                if current_inst == 0:
                    dur *= 1.4

                start_time = time_cursors[current_inst]
                end_time = start_time + dur

                velocity = 90
                if current_inst == 0: velocity = 100
                if current_inst == 1: velocity = 110
                if current_inst == 2: velocity = 105

                note = pretty_midi.Note(
                    velocity=velocity,
                    pitch=pitch,
                    start=start_time,
                    end=end_time,
                )

                instruments[current_inst].notes.append(note)
                time_cursors[current_inst] += dur
                note_count += 1

                i += 2
            else:
                i += 1
        else:
            i += 1
    else:
        i += 1

for inst in instruments:
    out_midi.instruments.append(inst)

out_midi.write("generated_orchestration.mid")

print(f"Created {note_count} notes")
print("Saved generated_orchestration.mid")