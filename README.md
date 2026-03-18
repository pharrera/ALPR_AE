# License Plate Recognition with Autoencoder-Based Image Restoration

**Resolution Degradation Study: Can autoencoders recover detection and OCR accuracy lost to low image resolution?**

## Project Overview

This project investigates the impact of image resolution degradation on license plate recognition (LPR) systems and evaluates whether a convolutional autoencoder can restore lost performance. The pipeline consists of:

1. **Plate Detection** — YOLOv8 fine-tuned on OpenALPR/CCPD datasets
2. **Character Recognition** — Custom CNN classifier (0-9, A-Z) + EasyOCR
3. **Image Restoration** — U-Net autoencoder trained to recover degraded plate images
4. **Resolution Experiment** — Systematic ablation across 7 resolution levels

The key experiment compares three conditions at each resolution:
- **Baseline**: Feed degraded image directly to the pipeline
- **Upscale Only**: Bicubic upscale to native resolution, then process
- **Autoencoder**: Restore with trained autoencoder, then process

## Student Information

- **Name**: Peter Herrera
- **Group Collaborators**: [LIST_COLLABORATORS]
- **Resources**: See references section below

## Setup

### Requirements

```bash
# Python 3.9+
pip install -r requirements.txt
```

On Apple Silicon, PyTorch will now auto-select `mps` so the M1 Pro GPU is used by default. You can still override it explicitly with `--device mps`, `--device cpu`, or `--device cuda` on the training and experiment scripts.

### Dataset Access

The project uses the **OpenALPR** dataset available on Roboflow:

```bash
# Option 1: Download via Roboflow API
export ROBOFLOW_API_KEY="your_api_key"
# Dataset will auto-download on first run

# Option 2: Manual download
# Visit: https://universe.roboflow.com/ and search for OpenALPR
# Download in YOLOv8 format, place in data/openalpr/
```

Expected directory structure after download:
```
data/openalpr/
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
```

## Running the Pipeline

### Step 1: Train Plate Detector

```bash
python train_detector.py --data-dir data/openalpr --config configs/config.yaml --epochs 50
```

### Step 2: Extract Plate Crops

```bash
python extract_plates.py --data-dir data/openalpr --output-dir data/openalpr/plates
```

### Step 3: Train Autoencoder

```bash
# U-Net autoencoder (recommended)
python train_autoencoder.py --config configs/config.yaml --model unet --epochs 100 --device mps

# Standard conv autoencoder (for comparison)
python train_autoencoder.py --config configs/config.yaml --model conv --epochs 100 --device mps
```

### Step 4: Train Character Classifier (optional, EasyOCR is fallback)

```bash
python train_classifier.py --config configs/config.yaml --char-dir data/openalpr/characters --device mps
```

### Step 5: Run Resolution Experiment

```bash
python run_experiment.py \
    --detector-weights results/detection/plate_detection/weights/best.pt \
    --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
    --test-dir data/openalpr/test \
    --output-dir results/experiment \
    --device mps
```

## Project Structure

```
lpr-autoencoder-project/
├── configs/
│   └── config.yaml              # All hyperparameters and settings
├── data/                        # Dataset directory (not committed)
├── models/
│   ├── detector.py              # YOLOv8 plate detection wrapper
│   ├── classifier.py            # Character classification CNN
│   └── autoencoder.py           # ConvAutoencoder + U-Net autoencoder
├── utils/
│   ├── data_loader.py           # Dataset classes and data loading
│   ├── degradation.py           # Image degradation utilities
│   ├── metrics.py               # Detection and OCR metrics
│   └── visualization.py         # Plotting and visualization
├── experiments/
│   └── resolution_experiment.py # Main experimental framework
├── results/                     # Training outputs and plots (not committed)
├── train_detector.py            # Train YOLOv8 detector
├── train_autoencoder.py         # Train autoencoder
├── train_classifier.py          # Train character classifier
├── extract_plates.py            # Extract plate crops for autoencoder
├── run_experiment.py            # Run full resolution experiment
├── requirements.txt
└── README.md
```

## GitHub Repository

**Code repository**: [YOUR_GITHUB_REPO_URL]

> CODE WILL NOT BE ACCEPTED IF SUBMITTED DIRECTLY TO CANVAS.
> Submit only the PDF write-up and this README to Canvas.

## References and Resources

- Putluru et al., "An Optimized YOLO-based License Plate Recognition System with Integrated Privacy Safeguards," ICMLAS 2025
- Ruseno et al., "An Enhanced YOLOv8 Model Integrated with CNN for Real-Time Vehicle License Plate Recognition," JOIV 2026
- Ultralytics YOLOv8: https://github.com/ultralytics/ultralytics
- OpenALPR Dataset: https://github.com/openalpr
- Roboflow: https://roboflow.com
- EasyOCR: https://github.com/JaidedAI/EasyOCR
