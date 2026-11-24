"""Model factory: custom CNN baseline + torchvision transfer models.

Pretrained weights (torchvision ImageNet-1k): code BSD-3-Clause; the weights were trained
on ImageNet, whose terms restrict use to non-commercial research. Commercial use of a
model fine-tuned from them needs separate review (see MODEL_CARD).
"""

from __future__ import annotations

import torch
from torch import nn
from torchvision import models


def _block(cin: int, cout: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(True),
        nn.Conv2d(cout, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(True),
        nn.MaxPool2d(2),
    )


class SmallCNN(nn.Module):
    """5 double-conv blocks (32->512 channels), BN + ReLU, max-pool, global average pool,
    dropout, linear head. Trained from scratch (no external weights)."""

    def __init__(self, num_classes: int, dropout: float = 0.3) -> None:
        super().__init__()
        chans = [3, 32, 64, 128, 256, 512]
        self.features = nn.Sequential(
            *[_block(a, b) for a, b in zip(chans[:-1], chans[1:], strict=True)]
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(dropout), nn.Linear(512, num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.pool(self.features(x)))


def build_model(arch: str, num_classes: int, pretrained: bool = True) -> nn.Module:
    if arch == "small_cnn":
        return SmallCNN(num_classes)
    if arch == "efficientnet_b0":
        w = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        m = models.efficientnet_b0(weights=w)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, num_classes)
        return m
    if arch == "mobilenet_v3_large":
        w = models.MobileNet_V3_Large_Weights.IMAGENET1K_V2 if pretrained else None
        m = models.mobilenet_v3_large(weights=w)
        m.classifier[3] = nn.Linear(m.classifier[3].in_features, num_classes)
        return m
    raise ValueError(f"unknown arch {arch}")


def head_parameters(model: nn.Module, arch: str) -> list[nn.Parameter]:
    if arch == "small_cnn":
        return list(model.parameters())
    return list(model.classifier.parameters())  # type: ignore[union-attr]


def gradcam_layer(model: nn.Module, arch: str) -> nn.Module:
    if arch == "small_cnn":
        return model.features[-1][5]  # type: ignore[index]  # last ReLU before the max-pool
    return model.features[-1]  # type: ignore[index]


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
