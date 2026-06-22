print(">>> USING HYBRID DATASET FILE <<<")
import os
import torch
import pretty_midi
from torch.utils.data import Dataset
import random


class HybridMIDIDataset(Dataset):
    def __init__(self, root_folder, tokenizer, max_len=384):
        self.samples = []
        self.tokenizer = tokenizer
        self.max_len = max_len

        # --- LOP paired ---
        lop_path = os.path.join(root_folder, "lop")

        for piece in os.listdir(lop_path):
            piece_path = os.path.join(lop_path, piece)
            if os.path.isdir(piece_path):
                piano = os.path.join(piece_path, "piano.mid")
                orchestra = os.path.join(piece_path, "orchestra.mid")

                if os.path.exists(piano) and os.path.exists(orchestra):
                    self.samples.append(("lop", piano, orchestra))

        # --- Lakh filtered ---
        lakh_path = os.path.join(root_folder, "lakh_filtered")

        for file in os.listdir(lakh_path):
            if file.endswith(".mid"):
                self.samples.append(("lakh", os.path.join(lakh_path, file), None))

        print("Total hybrid samples:", len(self.samples))

    def midi_to_tokens(self, midi_path, add_inst=False):
        midi = pretty_midi.PrettyMIDI(midi_path)
        tokens = []

        for inst_id, inst in enumerate(midi.instruments[:4]):
            for note in inst.notes:
                if add_inst:
                    tokens.append(self.tokenizer.token2id[f"INST_{inst_id % 8}"])

                tokens.append(self.tokenizer.token2id[f"NOTE_{note.pitch}"])

                dur = min(int((note.end - note.start) * 4), 31)
                tokens.append(self.tokenizer.token2id[f"DUR_{dur}"])

        return tokens[:self.max_len]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        source_type, file1, file2 = self.samples[idx]

        if source_type == "lop":
            enc_tokens = self.midi_to_tokens(file1, add_inst=False)
            dec_tokens = self.midi_to_tokens(file2, add_inst=True)
        else:
            # For Lakh: split first track as pseudo-melody
            midi = pretty_midi.PrettyMIDI(file1)

            melody = midi.instruments[0]
            enc_tokens = []
            for note in melody.notes:
                enc_tokens.append(self.tokenizer.token2id[f"NOTE_{note.pitch}"])
                dur = min(int((note.end - note.start) * 4), 31)
                enc_tokens.append(self.tokenizer.token2id[f"DUR_{dur}"])

            dec_tokens = self.midi_to_tokens(file1, add_inst=True)

        style = random.choice(["STYLE_EPIC", "STYLE_SOFT", "STYLE_DARK"])
        style_id = self.tokenizer.token2id[style]

        enc_tokens = [style_id] + enc_tokens
        enc_tokens = enc_tokens[:self.max_len]

        start_id = self.tokenizer.token2id["START"]

        dec_tokens = dec_tokens[:self.max_len]
        dec_in = [start_id] + dec_tokens[:-1]
        dec_out = dec_tokens

        return (
            torch.tensor(enc_tokens),
            torch.tensor(dec_in),
            torch.tensor(dec_out),
        )