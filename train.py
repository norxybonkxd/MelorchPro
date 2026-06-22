# Training script for the model
import torch
from torch.utils.data import DataLoader
from config import Config
from tokenizer import Tokenizer
from dataset import HybridMIDIDataset
from model import OrchestrationTransformer
from tqdm import tqdm

config = Config()
tokenizer = Tokenizer()

from dataset import HybridMIDIDataset
dataset = HybridMIDIDataset("data/raw", tokenizer, max_len=config.max_len)
from torch.nn.utils.rnn import pad_sequence

def collate_fn(batch):
    enc, dec_in, dec_out = zip(*batch)

    enc = pad_sequence(enc, batch_first=True, padding_value=tokenizer.token2id["PAD"])
    dec_in = pad_sequence(dec_in, batch_first=True, padding_value=tokenizer.token2id["PAD"])
    dec_out = pad_sequence(dec_out, batch_first=True, padding_value=tokenizer.token2id["PAD"])

    return enc, dec_in, dec_out

loader = DataLoader(
    dataset,
    batch_size=config.batch_size,
    shuffle=True,
    collate_fn=collate_fn
)

model = OrchestrationTransformer(config).to(config.device)

optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr)
pad_id = tokenizer.token2id["PAD"]
criterion = torch.nn.CrossEntropyLoss(ignore_index=pad_id)
for epoch in range(config.epochs):
    total_loss = 0
    model.train()

    for enc, dec_in, dec_out in tqdm(loader):
        enc, dec_in, dec_out = enc.to(config.device), dec_in.to(config.device), dec_out.to(config.device)

        optimizer.zero_grad()
        logits = model(enc, dec_in)

        loss = criterion(
            logits.view(-1, config.vocab_size),
            dec_out.view(-1)
        )

        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    print(f"Epoch {epoch+1} Loss: {total_loss/len(loader)}")

torch.save(model.state_dict(), "model.pth")