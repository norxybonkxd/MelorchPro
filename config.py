# Configuration settings
import torch

class Config:
    vocab_size = 400

    d_model = 256
    n_heads = 8
    n_encoder_layers = 3
    n_decoder_layers = 3
    ff_dim = 512
    dropout = 0.1

    max_len = 512   # Total context window

    batch_size = 2  # important for 6GB GPU
    lr = 3e-4
    epochs = 4      # start with 4 only

    device = "cuda"