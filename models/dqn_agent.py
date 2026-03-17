"""
DQN agent equipped with autoencoder latent features for adaptive
license plate image restoration.

Architecture:
    State  = autoencoder bottleneck features (latent vector) + image quality metrics
    Action = {0: pass-through, 1: bicubic upscale, 2: autoencoder restore}
    Reward = change in detection confidence + OCR character accuracy

The autoencoder's encoder is frozen and used as a learned feature extractor.
The DQN's Q-network is a small MLP that learns which restoration action
maximises downstream recognition accuracy at each quality level.
"""

import os
import random
import json
from collections import deque
from typing import Optional, Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import cv2

from models.autoencoder import UNetAutoencoder
from utils.device import resolve_device


# ══════════════════════════════════════════════════════════════════════
# Replay buffer
# ══════════════════════════════════════════════════════════════════════
class ReplayBuffer:
    """Fixed-size circular buffer for experience replay."""

    def __init__(self, capacity: int = 10_000):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        states, actions, rewards, next_states, dones = zip(*batch)
        return (
            torch.stack(states),
            torch.tensor(actions, dtype=torch.long),
            torch.tensor(rewards, dtype=torch.float32),
            torch.stack(next_states),
            torch.tensor(dones, dtype=torch.float32),
        )

    def __len__(self):
        return len(self.buffer)


# ══════════════════════════════════════════════════════════════════════
# Feature extractor — frozen autoencoder encoder
# ══════════════════════════════════════════════════════════════════════
class AutoencoderFeatureExtractor(nn.Module):
    """
    Uses the encoder half of a trained UNet autoencoder to produce
    a compact state representation for the DQN.

    The encoder weights are frozen — only the DQN head trains.
    """

    def __init__(self, autoencoder: UNetAutoencoder):
        super().__init__()
        # Grab encoder blocks + pools + bottleneck from the trained autoencoder
        self.encoders = autoencoder.encoders
        self.pools = autoencoder.pools        # ModuleList of MaxPool2d layers
        self.bottleneck = autoencoder.bottleneck

        # Freeze all encoder weights
        for param in self.parameters():
            param.requires_grad = False

        # Compute output feature size (run a dummy forward pass)
        with torch.no_grad():
            dummy = torch.zeros(1, 3, 128, 256)
            feat = self._encode(dummy)
            self.feature_dim = feat.shape[1]

    def _encode(self, x: torch.Tensor) -> torch.Tensor:
        for encoder, pool in zip(self.encoders, self.pools):
            x = encoder(x)
            x = pool(x)
        x = self.bottleneck(x)
        # Global average pool to get a fixed-length vector
        x = x.mean(dim=[2, 3])  # (B, C)
        return x

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self._encode(x)


# ══════════════════════════════════════════════════════════════════════
# Q-Network
# ══════════════════════════════════════════════════════════════════════
class QNetwork(nn.Module):
    """
    Small MLP Q-network.

    Input:  autoencoder features (latent_dim) + quality metrics (3: psnr, ssim, resolution_scale)
    Output: Q-values for each action
    """

    NUM_ACTIONS = 3  # pass-through, bicubic upscale, autoencoder restore

    def __init__(self, feature_dim: int, hidden_dim: int = 128, num_quality_features: int = 3):
        super().__init__()
        input_dim = feature_dim + num_quality_features
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, self.NUM_ACTIONS),
        )

    def forward(self, features: torch.Tensor, quality: torch.Tensor) -> torch.Tensor:
        x = torch.cat([features, quality], dim=-1)
        return self.net(x)


# ══════════════════════════════════════════════════════════════════════
# DQN Agent
# ══════════════════════════════════════════════════════════════════════
class DQNRestorationAgent:
    """
    Deep Q-Network agent that decides the optimal restoration strategy
    for each license plate image based on its quality level.

    Actions:
        0 = pass-through (no restoration)
        1 = bicubic upscale only
        2 = full autoencoder restoration

    The agent observes the autoencoder's latent representation of the
    plate crop plus image quality metrics, and learns which action
    maximises downstream detection/OCR performance.
    """

    ACTION_NAMES = ["pass_through", "bicubic_upscale", "autoencoder_restore"]

    def __init__(
        self,
        autoencoder: UNetAutoencoder,
        device: str = "cpu",
        lr: float = 1e-3,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.05,
        epsilon_decay: int = 500,
        buffer_size: int = 10_000,
        batch_size: int = 64,
        target_update: int = 50,
    ):
        self.device = device
        self.gamma = gamma
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update = target_update
        self.steps_done = 0

        # Feature extractor (frozen autoencoder encoder)
        self.feature_extractor = AutoencoderFeatureExtractor(autoencoder).to(device)
        self.feature_extractor.eval()

        # Store full autoencoder for restoration action
        self.autoencoder = autoencoder.to(device)
        self.autoencoder.eval()

        # Q-networks
        feat_dim = self.feature_extractor.feature_dim
        self.q_network = QNetwork(feat_dim).to(device)
        self.target_network = QNetwork(feat_dim).to(device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_network.eval()

        self.optimizer = optim.Adam(self.q_network.parameters(), lr=lr)
        self.replay_buffer = ReplayBuffer(buffer_size)
        self.training_history = {"loss": [], "reward": [], "epsilon": []}

    @property
    def epsilon(self):
        """Current exploration rate (decays over training)."""
        return self.epsilon_end + (self.epsilon_start - self.epsilon_end) * \
            np.exp(-self.steps_done / self.epsilon_decay)

    def _preprocess_image(self, image: np.ndarray) -> torch.Tensor:
        """Convert plate crop to tensor for feature extraction."""
        resized = cv2.resize(image, (256, 128))
        tensor = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
        return tensor.unsqueeze(0).to(self.device)

    def _compute_quality_features(
        self, image: np.ndarray, resolution_scale: float
    ) -> torch.Tensor:
        """Compute simple image quality features as part of the state."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
        # Laplacian variance (sharpness proxy)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var() / 1000.0
        # Mean intensity (brightness)
        mean_intensity = gray.mean() / 255.0
        # Resolution scale
        return torch.tensor(
            [laplacian_var, mean_intensity, resolution_scale],
            dtype=torch.float32,
        ).unsqueeze(0).to(self.device)

    def get_state(
        self, image: np.ndarray, resolution_scale: float
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Extract state = (autoencoder features, quality metrics)."""
        img_tensor = self._preprocess_image(image)
        with torch.no_grad():
            features = self.feature_extractor(img_tensor)
        quality = self._compute_quality_features(image, resolution_scale)
        return features.squeeze(0), quality.squeeze(0)

    def select_action(self, features: torch.Tensor, quality: torch.Tensor) -> int:
        """Epsilon-greedy action selection."""
        if random.random() < self.epsilon:
            return random.randrange(QNetwork.NUM_ACTIONS)

        with torch.no_grad():
            q_values = self.q_network(features.unsqueeze(0), quality.unsqueeze(0))
            return q_values.argmax(dim=1).item()

    def apply_action(self, image: np.ndarray, action: int) -> np.ndarray:
        """Apply the chosen restoration action to a plate crop."""
        if action == 0:
            # Pass-through
            return image
        elif action == 1:
            # Bicubic upscale (resize to standard plate size)
            return cv2.resize(image, (256, 128), interpolation=cv2.INTER_CUBIC)
        elif action == 2:
            # Autoencoder restoration
            # Preprocess: normalize to [-1, 1] (matching PlateImageDataset transform)
            resized = cv2.resize(image, (256, 128))
            inp = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
            inp = (inp - 0.5) / 0.5  # Map [0,1] → [-1,1]
            inp = inp.unsqueeze(0).to(self.device)
            with torch.no_grad():
                out = self.autoencoder(inp)
                if isinstance(out, tuple):
                    out = out[0]
            # Post-process: denormalize from Tanh [-1,1] → [0,255]
            restored = out.squeeze(0).permute(1, 2, 0).cpu().numpy()
            restored = (restored * 0.5 + 0.5) * 255.0  # [-1,1] → [0,255]
            restored = np.clip(restored, 0, 255).astype(np.uint8)
            return restored
        else:
            raise ValueError(f"Unknown action: {action}")

    def train_step(self) -> Optional[float]:
        """One gradient step from replay buffer."""
        if len(self.replay_buffer) < self.batch_size:
            return None

        states_feat, actions, rewards, next_feat, dones = self.replay_buffer.sample(
            self.batch_size
        )

        # Split features and quality from combined state
        feat_dim = self.feature_extractor.feature_dim
        states_f = states_feat[:, :feat_dim].to(self.device)
        states_q = states_feat[:, feat_dim:].to(self.device)
        next_f = next_feat[:, :feat_dim].to(self.device)
        next_q = next_feat[:, feat_dim:].to(self.device)
        actions = actions.to(self.device)
        rewards = rewards.to(self.device)
        dones = dones.to(self.device)

        # Current Q-values
        q_values = self.q_network(states_f, states_q).gather(1, actions.unsqueeze(1))

        # Target Q-values (Double DQN: use online net to select, target to evaluate)
        with torch.no_grad():
            next_actions = self.q_network(next_f, next_q).argmax(dim=1, keepdim=True)
            next_q_values = self.target_network(next_f, next_q).gather(1, next_actions)
            target = rewards.unsqueeze(1) + self.gamma * next_q_values * (1 - dones.unsqueeze(1))

        loss = nn.functional.smooth_l1_loss(q_values, target)

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.q_network.parameters(), max_norm=1.0)
        self.optimizer.step()

        return loss.item()

    def update_target_network(self):
        """Copy online network weights to target network."""
        self.target_network.load_state_dict(self.q_network.state_dict())

    def save(self, path: str):
        """Save agent state."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            "q_network": self.q_network.state_dict(),
            "target_network": self.target_network.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "steps_done": self.steps_done,
            "training_history": self.training_history,
        }, path)
        print(f"Agent saved to {path}")

    def load(self, path: str):
        """Load agent state."""
        checkpoint = torch.load(path, map_location=self.device)
        self.q_network.load_state_dict(checkpoint["q_network"])
        self.target_network.load_state_dict(checkpoint["target_network"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.steps_done = checkpoint["steps_done"]
        self.training_history = checkpoint.get("training_history", self.training_history)
        print(f"Agent loaded from {path}")
