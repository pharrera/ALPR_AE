# License Plate Recognition via Adaptive Deep Learning Restoration

**CPSC 543 — Assignment 1**

Can a learned restorer (U-Net + GAN) plus an adaptive RL policy (DQN) recover license-plate detection and OCR accuracy lost to image degradation? This repo measures the answer on the UFPR-ALPR benchmark.

## Student Information

- **Name**: Peter Herrera
- **Email**: peherrera@chapman.edu
- **Group Collaborators**: None
- **Course**: CPSC 543, Spring 2026

## Pipeline

```
Input → [DQN selects strategy] → [optional GAN restoration]
      → YOLOv8n detection → plate crop
      → [GAN restoration on crop]
      → EasyOCR (en+pt, ensemble preprocessing) → text
```

Components:

1. **Detector** — YOLOv8n fine-tuned on UFPR-ALPR (frozen; `mAP50 = 0.977`).
2. **Restorer** — U-Net autoencoder, pre-trained with MSE + SSIM + VGG perceptual loss, then fine-tuned with a multi-scale PatchGAN (LSGAN).
3. **OCR** — EasyOCR with a 4-variant preprocessing ensemble (CLAHE, denoise, sharpen, binarize, invert).
4. **Adaptive policy** — Dueling DQN over a 5-D image-quality feature vector (sharpness, brightness, edge density, contrast, resolution scale), selecting one of {pass-through, bicubic upscale, autoencoder restore}.

## Dataset

**UFPR-ALPR** (Universidade Federal do Paraná).
- 4,500 fully annotated frames from on-vehicle cameras in Curitiba, Brazil.
- 7-character Brazilian plates (legacy `ABC-1234` and Mercosul `ABC1D23`).
- Splits used (YOLO-converted): **train 1,800 / val 900 / test 1,800.**
- Per-image plate text ground truth lives in `data/ufpr_yolo/plate_gt.json` (4,500 entries).

### Access

UFPR-ALPR is released under a research license. Request access from the authors:
https://web.inf.ufpr.br/vri/databases/ufpr-alpr/

Once you have the raw release, convert it to YOLO format:
```bash
python prepare_ufpr_yolo.py
```
This writes `data/ufpr_yolo/{train,valid,test}/{images,labels}` and `data/ufpr_yolo/plate_gt.json`.

A secondary CCPD converter (`prepare_ccpd.py`) is included for the Chinese plate dataset but **CCPD is not used in any reported result**.

## Setup

```bash
# Python 3.9+
pip install -r requirements.txt
```

Device is auto-selected: `cuda > mps > cpu`. Override with `--device {cuda,mps,cpu}` on any training/experiment script.

## Reproducing the Results

The whole pipeline is wrapped in `retrain_all.sh`:
```bash
./retrain_all.sh                  # full pipeline (AE → GAN → DQN → experiment → figures)
./retrain_all.sh --skip-ae        # skip autoencoder pre-training
./retrain_all.sh --figures-only   # regenerate plots only
```

Individual steps:

```bash
# 1. (one-time) convert UFPR-ALPR to YOLO format
python prepare_ufpr_yolo.py

# 2. train detector (already trained; weights at results/detection/plate_detection/weights/best.pt)
python train_detector.py --config configs/config.yaml

# 3. extract plate crops for the restorer
python extract_plates.py

# 4. autoencoder pre-training (MSE + SSIM + VGG perceptual)
python train_autoencoder.py --config configs/config.yaml --model unet

# 5. GAN fine-tuning (PatchGAN discriminator)
python train_gan.py --config configs/config.yaml

# 6. DQN policy training
python train_dqn.py --config configs/config.yaml

# 7. resolution-degradation experiment
python run_experiment.py \
    --detector-weights results/detection/plate_detection/weights/best.pt \
    --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
    --output-dir results/experiment

# 8. publication figures
python generate_figures.py
```

## Headline Result

Detection mAP under bicubic-downsample degradation (test set, $n=1{,}800$):

| Condition           | 640 px | 320 px | 240 px |
|---------------------|-------:|-------:|-------:|
| Baseline (degraded) |   1.00 |   0.59 |   0.11 |
| Bicubic upscale     |   1.00 |   0.77 |   0.25 |
| **Autoencoder**     |   1.00 |   0.80 | **0.47** |

OCR exact-match ceilings around 27% even at native 640 px, because EasyOCR is not trained on Brazilian plate fonts. Restoration helps detection substantially; the OCR bottleneck is a representation problem, not a restoration one.

Full results: `results/experiment_v2/experiment_results.json`.
Figures: `results/figures/` and `results/experiment_v2/plots/`.

## Project Structure

```
code/
├── configs/config.yaml          # all hyperparameters
├── models/
│   ├── autoencoder.py           # U-Net + VGG perceptual + SSIM losses
│   ├── discriminator.py         # multi-scale PatchGAN
│   ├── detector.py              # YOLOv8n wrapper
│   ├── classifier.py            # character CNN (optional)
│   └── dqn_agent.py             # dueling DQN
├── utils/
│   ├── ocr_utils.py             # ensemble OCR pipeline (en+pt)
│   ├── degradation.py           # ImageDegrader
│   ├── data_loader.py           # PlateImageDataset
│   ├── ufpr_data_loader.py
│   ├── metrics.py
│   ├── visualization.py
│   └── device.py
├── experiments/
│   └── resolution_experiment.py
├── prepare_ufpr_yolo.py         # UFPR-ALPR → YOLO converter
├── prepare_ccpd.py              # CCPD converter (unused)
├── extract_plates.py
├── train_detector.py
├── train_autoencoder.py
├── train_gan.py
├── train_dqn.py
├── train_classifier.py
├── run_experiment.py
├── generate_figures.py
├── retrain_all.sh               # master pipeline
├── writeup/
│   └── assignment1.tex          # Assignment 1 LaTeX writeup
└── results/                     # outputs (not committed)
```

## References

- Laroca, R. et al., *A Robust Real-Time Automatic License Plate Recognition Based on the YOLO Detector*, IJCNN, 2018. (UFPR-ALPR)
- Xu, Z. et al., *Towards End-to-End License Plate Detection and Recognition: A Large Dataset and Baseline*, ECCV, 2018. (CCPD)
- Laroca, R. et al., *Leveraging Super-Resolution for License Plate Recognition: The UFPR-SR-Plates Benchmark*, 2025.
- Chen, H. et al., *RestoreAgent: Autonomous Image Restoration Agent via Multimodal LLMs*, NeurIPS, 2024.
- Ultralytics YOLOv8: https://github.com/ultralytics/ultralytics
- EasyOCR: https://github.com/JaidedAI/EasyOCR
