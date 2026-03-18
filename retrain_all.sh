#!/bin/bash
# =============================================================================
# Master Retraining Script for DGX A100 — v3 (GAN Pipeline)
# =============================================================================
# Runs the full upgraded pipeline:
#   1. (Optional) CCPD dataset preparation
#   2. Plate extraction (UFPR + CCPD)
#   3. Autoencoder pre-training (VGG perceptual loss, 250 epochs)
#   4. GAN fine-tuning (PatchGAN adversarial, 100 epochs)
#   5. DQN training (dueling architecture, OCR reward, 1500 episodes)
#   6. Full resolution degradation experiment (v3)
#   7. Generate publication figures
#
# Usage:
#   chmod +x retrain_all.sh
#   ./retrain_all.sh              # Full pipeline
#   ./retrain_all.sh --skip-ae    # Skip AE pre-training (use existing weights)
#   ./retrain_all.sh --with-ccpd  # Include CCPD preparation
#   ./retrain_all.sh --skip-ae --figures-only  # Only regenerate figures
#
# Run inside screen/tmux for long training:
#   screen -S training
#   ./retrain_all.sh
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "  LPR Autoencoder v3 — Full GAN Pipeline"
echo "=============================================="
echo "Start time: $(date)"
echo ""

# Check GPU
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
echo ""

# ─── Parse flags ─────────────────────────────────────────────────────
WITH_CCPD=false
SKIP_AE=false
FIGURES_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --with-ccpd)    WITH_CCPD=true ;;
        --skip-ae)      SKIP_AE=true ;;
        --figures-only) FIGURES_ONLY=true ;;
    esac
done

# Plate directory (may be overridden with CCPD)
PLATE_DIR="data/plates/train"

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

if ! $FIGURES_ONLY; then

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

# Combine UFPR + CCPD plates if CCPD was prepared
if $WITH_CCPD && [ -d "data/plates/ccpd" ]; then
    echo "Combining UFPR + CCPD plate crops..."
    PLATE_DIR="data/plates/combined"
    mkdir -p "$PLATE_DIR"
    ln -sf "$(pwd)/data/plates/train/"* "$PLATE_DIR/" 2>/dev/null || true
    ln -sf "$(pwd)/data/plates/ccpd/"* "$PLATE_DIR/" 2>/dev/null || true
    echo "Combined plates: $(ls "$PLATE_DIR" | wc -l) images"
fi

# ─── Step 2: Autoencoder Pre-Training ────────────────────────────────
if ! $SKIP_AE; then
    echo "=========================================="
    echo "Step 2: Pre-training U-Net Autoencoder"
    echo "  - VGG perceptual loss (weight=0.1)"
    echo "  - Aggressive degradation (factors up to 16)"
    echo "  - CosineAnnealingWarmRestarts"
    echo "  - 250 epochs"
    echo "=========================================="
    python3 train_autoencoder.py \
        --model unet \
        --plate-dir "$PLATE_DIR" \
        --epochs 250 \
        --batch-size 32 \
        --device cuda
    echo ""
    echo "Autoencoder pre-training complete!"
    echo ""
else
    echo "=========================================="
    echo "Step 2: SKIPPED (--skip-ae flag, using existing weights)"
    echo "=========================================="
    echo ""
fi

# ─── Step 3: GAN Fine-Tuning ────────────────────────────────────────
echo "=========================================="
echo "Step 3: GAN Fine-Tuning"
echo "  - MultiScale PatchGAN discriminator"
echo "  - LSGAN objective"
echo "  - L1 + SSIM + VGG + adversarial loss"
echo "  - Warm-start from autoencoder weights"
echo "  - 100 epochs"
echo "=========================================="

# Use AE weights for warm start
AE_WEIGHTS="results/autoencoder/unet/best_autoencoder.pth"
if [ ! -f "$AE_WEIGHTS" ]; then
    echo "WARNING: No AE weights found at $AE_WEIGHTS"
    echo "  GAN will train from scratch (slower convergence)"
    GAN_PRETRAINED=""
else
    GAN_PRETRAINED="--pretrained-weights $AE_WEIGHTS"
fi

python3 train_gan.py \
    --plate-dir "$PLATE_DIR" \
    $GAN_PRETRAINED \
    --epochs 100 \
    --batch-size 16 \
    --output-dir results/autoencoder/gan \
    --device cuda
echo ""
echo "GAN fine-tuning complete!"
echo ""

# ─── Step 4: DQN Training ───────────────────────────────────────────
echo "=========================================="
echo "Step 4: Training Dueling DQN Agent"
echo "  - Dueling architecture"
echo "  - OCR-based reward (EasyOCR + GT text)"
echo "  - 1500 episodes × 80 steps"
echo "  - 5-feature state representation"
echo "=========================================="

# Use GAN generator weights if available, else fallback to AE
DQN_WEIGHTS="results/autoencoder/gan/best_generator.pth"
if [ ! -f "$DQN_WEIGHTS" ]; then
    DQN_WEIGHTS="$AE_WEIGHTS"
    echo "  Using AE weights for DQN (GAN weights not found)"
fi

python3 train_dqn.py \
    --autoencoder-weights "$DQN_WEIGHTS" \
    --plate-dir "$PLATE_DIR" \
    --episodes 1500 \
    --steps-per-episode 80 \
    --output-dir results/dqn \
    --device cuda
echo ""
echo "DQN training complete!"
echo ""

# ─── Step 5: Full Experiment ────────────────────────────────────────
echo "=========================================="
echo "Step 5: Running Full Resolution Experiment (v3)"
echo "  - GAN generator for restoration"
echo "  - Enhanced OCR pipeline (en+pt)"
echo "  - All degradation types"
echo "=========================================="

# Use GAN generator weights if available
EXP_WEIGHTS="results/autoencoder/gan/best_generator.pth"
if [ ! -f "$EXP_WEIGHTS" ]; then
    EXP_WEIGHTS="$AE_WEIGHTS"
    echo "  Using AE weights for experiment (GAN weights not found)"
fi

python3 run_experiment.py \
    --detector-weights results/detection/plate_detection/weights/best.pt \
    --autoencoder-weights "$EXP_WEIGHTS" \
    --autoencoder-type unet \
    --test-dir data/ufpr_yolo/test \
    --max-images 100 \
    --output-dir results/experiment_v3 \
    --device cuda
echo ""

fi  # end of !FIGURES_ONLY

# ─── Step 6: Generate Publication Figures ────────────────────────────
echo "=========================================="
echo "Step 6: Generating Publication Figures"
echo "=========================================="

# Auto-detect best weights for figures
FIG_AE_WEIGHTS="results/autoencoder/unet/best_autoencoder.pth"
FIG_GAN_WEIGHTS="results/autoencoder/gan/best_generator.pth"
FIG_GAN_HISTORY="results/autoencoder/gan/gan_training_results.json"
FIG_RESULTS="results/experiment_v3/experiment_results.json"
FIG_RESULTS_V2="results/experiment_v2/experiment_results.json"

# Build figure generation command
FIG_CMD="python3 generate_figures.py"
FIG_CMD+=" --output-dir results/figures"
FIG_CMD+=" --device cuda"

[ -f "$FIG_RESULTS" ]    && FIG_CMD+=" --results $FIG_RESULTS"
[ -f "$FIG_RESULTS_V2" ] && FIG_CMD+=" --results-v2 $FIG_RESULTS_V2"
[ -f "$FIG_AE_WEIGHTS" ] && FIG_CMD+=" --autoencoder-weights $FIG_AE_WEIGHTS"
[ -f "$FIG_GAN_WEIGHTS" ] && FIG_CMD+=" --gan-weights $FIG_GAN_WEIGHTS"
[ -f "$FIG_GAN_HISTORY" ] && FIG_CMD+=" --gan-history $FIG_GAN_HISTORY"
[ -f "results/dqn/dqn_training_history.json" ] && FIG_CMD+=" --dqn-history results/dqn/dqn_training_history.json"
[ -f "results/detection/plate_detection/weights/best.pt" ] && FIG_CMD+=" --detector-weights results/detection/plate_detection/weights/best.pt"

echo "Running: $FIG_CMD"
eval $FIG_CMD
echo ""

# ─── Done ─────────────────────────────────────────────────────────────
echo "=============================================="
echo "  ALL TRAINING COMPLETE!"
echo "=============================================="
echo "End time: $(date)"
echo ""
echo "Results:"
echo "  Autoencoder  : results/autoencoder/unet/"
echo "  GAN          : results/autoencoder/gan/"
echo "  DQN Agent    : results/dqn/"
echo "  Experiment   : results/experiment_v3/"
echo "  Figures      : results/figures/"
echo ""
echo "Next steps:"
echo "  1. Review results/experiment_v3/experiment_results.json"
echo "  2. Check results/figures/ for publication-quality plots"
echo "  3. Compare v2 vs v3 in fig13_version_comparison.png"
echo "  4. Check fig11_gan_vs_ae_gallery.png for reconstruction quality"
