# Tokenizer for MIDI data
class Tokenizer:
    def __init__(self):
        self.token2id = {}
        self.id2token = {}
        self.build()

    def build(self):
        idx = 0

        for i in range(128):
            self.token2id[f"NOTE_{i}"] = idx; idx += 1

        for i in range(32):
            self.token2id[f"DUR_{i}"] = idx; idx += 1

        for i in range(8):
            self.token2id[f"INST_{i}"] = idx; idx += 1

        styles = ["STYLE_EPIC", "STYLE_SOFT", "STYLE_DARK"]
        for s in styles:
            self.token2id[s] = idx; idx += 1

        specials = ["START", "END", "PAD"]
        for s in specials:
            self.token2id[s] = idx; idx += 1

        self.id2token = {v:k for k,v in self.token2id.items()}