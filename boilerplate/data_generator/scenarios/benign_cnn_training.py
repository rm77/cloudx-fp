"""
scenarios/benign_cnn_training.py
===================================
Job BENIGN: training CNN kecil pada data sintetis. Pola telemetri yang
diharapkan: GPU utilization naik-turun mengikuti siklus batch/epoch,
I/O muncul di awal (load data) dan saat checkpoint save.
"""
import argparse

import torch
import torch.nn as nn
import torch.optim as optim

from scenario_base import Scenario
from registry import register


class SmallCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Flatten(),
            nn.Linear(64 * 16 * 16, 128), nn.ReLU(),
            nn.Linear(128, 10),
        )

    def forward(self, x):
        return self.net(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--steps-per-epoch", type=int, default=100)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--checkpoint-every", type=int, default=1)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SmallCNN().to(device)
    opt = optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(args.epochs):
        for step in range(args.steps_per_epoch):
            x = torch.randn(args.batch_size, 3, 32, 32, device=device)
            y = torch.randint(0, 10, (args.batch_size,), device=device)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()

        if (epoch + 1) % args.checkpoint_every == 0:
            torch.save(model.state_dict(), f"/tmp/ckpt_epoch{epoch}.pt")

        print(f"[benign_cnn_training] epoch={epoch} loss={loss.item():.4f}")

    print("[benign_cnn_training] selesai.")


register(Scenario(
    name="benign_cnn_training",
    label="benign",
    script_path="scenarios/benign_cnn_training.py",
    default_args=["--epochs", "5", "--steps-per-epoch", "100"],
    timeout_sec=None,  # berhenti sendiri setelah training selesai
    description="GPU util naik-turun siklik, I/O spike periodik saat checkpoint.",
))


if __name__ == "__main__":
    main()
