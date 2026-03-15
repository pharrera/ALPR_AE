"""
Character classification CNN for license plate OCR.

A custom CNN that classifies individual characters (0-9, A-Z) extracted
from detected license plate regions. Designed to be lightweight for
edge deployment while maintaining high accuracy.

Architecture based on the second reference paper's custom CNN design:
Conv2D(32) -> BN -> Pool -> Conv2D(64) -> BN -> Pool ->
Conv2D(128) -> BN -> Pool -> Flatten -> FC(512) -> FC(256) -> Output(36)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple


class CharacterClassifier(nn.Module):
    """
    CNN for single character classification (0-9, A-Z = 36 classes).

    Input: grayscale character image (1 x H x W)
    Output: class probabilities (36,)
    """

    def __init__(
        self,
        num_classes: int = 36,
        input_channels: int = 1,
        input_size: int = 64,
        conv_channels: List[int] = None,
        fc_sizes: List[int] = None,
        dropout: float = 0.3,
    ):
        super().__init__()

        if conv_channels is None:
            conv_channels = [32, 64, 128]
        if fc_sizes is None:
            fc_sizes = [512, 256]

        self.input_size = input_size
        self.num_classes = num_classes

        # Build convolutional layers
        conv_layers = []
        in_ch = input_channels
        for out_ch in conv_channels:
            conv_layers.extend([
                nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2, 2),
            ])
            in_ch = out_ch

        self.features = nn.Sequential(*conv_layers)

        # Calculate flattened size after convolutions
        # Each MaxPool2d halves spatial dims
        num_pools = len(conv_channels)
        spatial = input_size // (2 ** num_pools)
        flatten_size = conv_channels[-1] * spatial * spatial

        # Build fully connected layers
        fc_layers = []
        in_features = flatten_size
        for i, fc_size in enumerate(fc_sizes):
            fc_layers.extend([
                nn.Linear(in_features, fc_size),
                nn.ReLU(inplace=True),
                nn.Dropout(dropout + (i * 0.1)),  # Increasing dropout
            ])
            in_features = fc_size

        fc_layers.append(nn.Linear(in_features, num_classes))
        self.classifier = nn.Sequential(*fc_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = x.view(x.size(0), -1)  # Flatten
        x = self.classifier(x)
        return x

    def predict(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Get predictions with confidence scores.

        Returns:
            (predicted_classes, confidences)
        """
        with torch.no_grad():
            logits = self.forward(x)
            probs = F.softmax(logits, dim=1)
            confidences, predictions = probs.max(dim=1)
        return predictions, confidences


class CharacterClassifierTrainer:
    """Training wrapper for the character classifier."""

    def __init__(
        self,
        model: CharacterClassifier,
        device: str = "cuda",
        learning_rate: float = 0.001,
    ):
        self.model = model.to(device)
        self.device = device
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="max", factor=0.5, patience=5, verbose=True
        )

    def train_epoch(self, dataloader) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for images, labels in dataloader:
            images = images.to(self.device)
            labels = labels.to(self.device)

            self.optimizer.zero_grad()
            outputs = self.model(images)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)

        return {
            "loss": total_loss / total,
            "accuracy": correct / total,
        }

    @torch.no_grad()
    def evaluate(self, dataloader) -> Dict[str, float]:
        """Evaluate on validation set."""
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        all_preds = []
        all_labels = []

        for images, labels in dataloader:
            images = images.to(self.device)
            labels = labels.to(self.device)

            outputs = self.model(images)
            loss = self.criterion(outputs, labels)

            total_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)

            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

        accuracy = correct / total
        self.scheduler.step(accuracy)

        return {
            "loss": total_loss / total,
            "accuracy": accuracy,
            "predictions": all_preds,
            "labels": all_labels,
        }

    def train(
        self,
        train_loader,
        val_loader,
        epochs: int = 30,
        save_dir: str = "results/classification",
        early_stop_patience: int = 10,
    ) -> Dict:
        """
        Full training loop with validation and early stopping.

        Returns training history dict.
        """
        import os
        os.makedirs(save_dir, exist_ok=True)

        history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
        best_acc = 0.0
        patience_counter = 0

        for epoch in range(epochs):
            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.evaluate(val_loader)

            history["train_loss"].append(train_metrics["loss"])
            history["train_acc"].append(train_metrics["accuracy"])
            history["val_loss"].append(val_metrics["loss"])
            history["val_acc"].append(val_metrics["accuracy"])

            print(
                f"Epoch [{epoch+1}/{epochs}] "
                f"Train Loss: {train_metrics['loss']:.4f} "
                f"Train Acc: {train_metrics['accuracy']:.4f} "
                f"Val Loss: {val_metrics['loss']:.4f} "
                f"Val Acc: {val_metrics['accuracy']:.4f}"
            )

            # Save best model
            if val_metrics["accuracy"] > best_acc:
                best_acc = val_metrics["accuracy"]
                torch.save(
                    self.model.state_dict(),
                    os.path.join(save_dir, "best_classifier.pth"),
                )
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= early_stop_patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break

        # Save final model
        torch.save(
            self.model.state_dict(),
            os.path.join(save_dir, "final_classifier.pth"),
        )

        history["best_val_acc"] = best_acc
        return history
