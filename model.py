# Model architecture for music generation
import torch
import torch.nn as nn

class OrchestrationTransformer(nn.Module):
    def __init__(self, config):
        super().__init__()

        self.embed = nn.Embedding(config.vocab_size, config.d_model)
        self.pos = nn.Parameter(torch.randn(1, config.max_len, config.d_model))

        self.transformer = nn.Transformer(
            d_model=config.d_model,
            nhead=config.n_heads,
            num_encoder_layers=config.n_encoder_layers,
            num_decoder_layers=config.n_decoder_layers,
            dim_feedforward=config.ff_dim,
            dropout=config.dropout,
            batch_first=True
        )

        self.fc = nn.Linear(config.d_model, config.vocab_size)

    def forward(self, src, tgt):
        src = self.embed(src) + self.pos[:, :src.shape[1]]
        tgt = self.embed(tgt) + self.pos[:, :tgt.shape[1]]

        out = self.transformer(src, tgt)
        return self.fc(out)