#!/bin/bash
# =============================================================================
# Master Retraining Script for DGX A100
# =============================================================================
# Runs the full upgraded pipeline:
#   1. (Optional) CCPD dataset preparation
#   2. Plate extraction (UFPR + CCPD)
#   3. Autoencoder training (VGG perceptual loss, warm restarts, 250 epochs)
#   4. DQN training (dueling architecture, OCR reward, 1500 episodes)
#   5. Full resolution degradation experiment
#
# Usage:
#   chmod +x retrain_all.sh
#   ./retrain_all.sh              # Skip CCPD prep (already done)
#   ./retrain_all.sh --with-ccpd  # Include CCPD preparation
#
# Run inside screen/tmux for long training:
#   screen -S training
#   ./retrain_all.sh
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "  LPR Autoencoder - Full Retraining Pipeline"
echo "=============================================="
echo "Start time: $(date)"
echo ""

# Check GPU
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
echo ""

WITH_CCPD=false
if [[ "$1" == "--with-ccpd" ]]; then
    WITH_CCPD=true
fi

# ─── Step 0: CCPD Dataset Preparation (optional) ─────────────────────
if $WITH_CCPD; then
    echo "=========================================="
    echo "Step 0: Preparing CCPD dataset"
    echo "=========================================="
    python3 prepare_ccpd.py \
        --ccpd-dir data/ccpd/CCPD2019 \
        --output-dir data/ccpd_yolo \
        --plate-output-dir data/plates/ccpd \
        --max-images 50000
    echo "CCPD preparation complete!"
    echo ""
fi

# ─── Step 1: Extract plate crops ──────────────────────────────────────
echo "=========================================="
echo "Step 1: Extracting plate crops from UFPR"
echo "=========================================="
python3 extract_plates.py \
    --data-dir data/ufpr_yolo \
    --output-dir data/plates \
    --padding 0.15
echo "Plate extraction complete!"
echo ""

# ─── Step 2: Autoencoder Training (upgraded) ──────────────────────────
echo "=========================================="
echo "Step 2: Training U-Net Autoencoder"
echo "  - VGG perceptual loss (weight=0.1)"
echo "  - Aggressive degradation (factors up to 16)"
echo "  - CosineAnnealingWarmRestarts"
echo "  - 250 epochs"
echo "=========================================="

# Combine UFPR + CCPD plates if CCPD was prepared
PLATE_DIR="data/plates/train"
if $WITH_CCPD && [ -d "data/plates/ccpd" ]; then
    echo "Combining UFPR + CCPD plate crops..."
    PLATE_DIR="data/plates/combined"
    mkdir -p "$PLATE_DIR"
    # Symlink all plate crops into combined dir
    ln -sf "$(pwd)/data/plates/train/"* "$PLATE_DIR/" 2>/dev/null || true
    ln -sf "$(pwd)/data/plates/ccpd/"* "$PLATE_DIR/" 2>/dev/null || true
    echo "Combined plates: $(ls "$PLATE_DIR" | wc -l) images"
fi

python3 train_autoencoder.py \
    --model unet \
    --plate-dir "$PLATE_DIR" \
    --epochs 250 \
    --batch-size 32 \
    --device cuda
echo ""
echo "Autoencoder training complete!"
echo ""

# ─── Step 3: DQN Training (upgraded) ─────────────────────────────────
echo "=========================================="
echo "Step 3: Training Dueling DQN Agent"
echo "  - Dueling architecture"
echo "  - OCR-based reward (EasyOCR + GT text)"
echo "  - 1500 episodes × 80 steps"
echo "  - 5-feature state representation"
echo "=========================================="
python3 train_dqn.py \
    --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
    --plate-dir "$PLATE_DIR" \
    --episodes 1500 \
    --steps-per-episode 80 \
    --output-dir results/dqn \
    --device cuda
echo ""
echo "DQN training complete!"
echo ""

# ─── Step 4: Full Experiment ──────────────────────────────────────────
echo "=========================================="
echo "Step 4: Running Full Resolution Experiment"
echo "  - Autoencoder applied to full image"
echo "  - Enhanced OCR pipeline (en+pt)"
echo "  - All degradation types"
echo "=========================================="
python3 run_experiment.py \
    --detector-weights results/detection/plate_detection/weights/best.pt \
    --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
    --autoencoder-type unet \
    --test-dir data/ufpr_yolo/test \
    --max-images 100 \
    --output-dir results/experiment_v2 \
    --device cuda
echo ""

# ─── Done ─────────────────────────────────────────────────────────────
echo "=============================================="
echo "  ALL TRAINING COMPLETE!"
echo "=============================================="
echo "End time: $(date)"
echo ""
echo "Results:"
echo "  Autoencoder : results/autoencoder/unet/"
echo "  DQN Agent   : results/dqn/"
echo "  Experiment  : results/experiment_v2/"
echo ""
echo "Next steps:"
echo "  1. Review results/experiment_v2/experiment_results.json"
echo "  2. Check results/experiment_v2/plots/ for comparison charts"
echo "  3. Compare v2 results against previous baseline"
