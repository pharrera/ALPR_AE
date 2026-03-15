"""
Train the character classification CNN.

Usage:
    python train_classifier.py --config configs/config.yaml
    python train_classifier.py --char-dir data/openalpr/characters

This trains a lightweight CNN to classify individual characters (0-9, A-Z)
extracted from detected license plate regions.
"""

import argparse
import os
import json
import torch

from utils.data_loader import load_config, CharacterDataset
from utils.device import resolve_device, use_pinned_memory
from utils.visualization import plot_training_history
from models.classifier import CharacterClassifier, CharacterClassifierTrainer
from torch.utils.data import DataLoader, random_split


def main():
    parser = argparse.ArgumentParser(description="Train character classifier")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--char-dir", default="data/openalpr/characters")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument(
        "--device",
        default=None,
        help="Device to train on: auto, cuda, mps, or cpu",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    cls_config = config["classification"]

    epochs = args.epochs or cls_config["epochs"]
    batch_size = args.batch_size or cls_config["batch_size"]
    device = resolve_device(args.device)
    pin_memory = use_pinned_memory(device)

    # Load dataset
    train_dir = os.path.join(args.char_dir, "train")
    val_dir = os.path.join(args.char_dir, "val")

    if os.path.exists(train_dir) and os.path.exists(val_dir):
        train_ds = CharacterDataset(train_dir, img_size=cls_config["input_size"])
        val_ds = CharacterDataset(val_dir, img_size=cls_config["input_size"])
    else:
        # Single directory: split automatically
        print(f"No train/val split found. Splitting {args.char_dir} 80/20.")
        full_ds = CharacterDataset(args.char_dir, img_size=cls_config["input_size"])
        n_val = max(1, int(len(full_ds) * 0.2))
        n_train = len(full_ds) - n_val
        train_ds, val_ds = random_split(
            full_ds,
            [n_train, n_val],
            generator=torch.Generator().manual_seed(config["project"]["seed"]),
        )

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=min(4, os.cpu_count() or 1), pin_memory=pin_memory, drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=min(4, os.cpu_count() or 1), pin_memory=pin_memory,
    )

    # Create model
    model = CharacterClassifier(
        num_classes=cls_config["num_classes"],
        input_channels=cls_config["channels"],
        input_size=cls_config["input_size"],
        conv_channels=cls_config["architecture"]["conv_layers"],
        fc_sizes=cls_config["architecture"]["fc_layers"],
        dropout=cls_config["dropout"],
    )

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {total_params:,}")

    # Train
    trainer = CharacterClassifierTrainer(
        model=model, device=device, learning_rate=cls_config["learning_rate"]
    )

    save_dir = "results/classification"
    print("\n" + "=" * 60)
    print("TRAINING CHARACTER CLASSIFIER")
    print("=" * 60)

    history = trainer.train(
        train_loader, val_loader, epochs=epochs, save_dir=save_dir
    )

    plot_training_history(
        history,
        save_path=os.path.join(save_dir, "training_history.png"),
        title="Character Classifier Training",
    )

    with open(os.path.join(save_dir, "training_results.json"), "w") as f:
        json.dump(
            {k: v for k, v in history.items() if not isinstance(v, list) or len(v) < 200},
            f,
            indent=2,
        )

    print(f"\nBest val accuracy: {history['best_val_acc']:.4f}")
    print("Training complete!")


if __name__ == "__main__":
    main()
