# Git Setup Guide
═══════════════════════════════════════════════════════════════

## First Time Setup (Your Machine)

```bash
# 1. Initialize Git LFS (for large data files)
git lfs install

# 2. Clone the repo
git clone <repo-url>
cd hermes_v2

# 3. Run setup (builds Docker, ingests data, runs tests)
./setup.ps1
```

## For Users Who Clone

After cloning, they need to:

```bash
# 1. Configure API keys
cp .env.example .env
# Edit .env and add OPENROUTER_API_KEY

# 2. Start services
./start.ps1

# 3. Or use production mode
./start.ps1 prod
```

## What's Included in Git

| File | Size | Description |
|------|------|-------------|
| `dataset/training_data/` | 2.5MB | Training trajectories, SFT, reward data |
| `dataset/mains_gs_all.jsonl` | 4.4MB | Mains GS questions (2017-2024) |
| `dataset/prelims_gs_all.jsonl` | 1.9MB | Prelims GS questions |
| `dataset/csat_dataset_all.jsonl` | 1.8MB | CSAT dataset |
| `dataset/2011-2025/` | ~10MB | Year-wise PYQ data |
| `dataset/README.md` | <1KB | Data documentation |
| `backend/` | ~5MB | All Python source code |
| `frontend/` | ~2MB | React frontend |
| `docker-compose*.yml` | <1KB each | Docker configs |
| `start.ps1` | <1KB | One-click startup |
| `setup.ps1` | <1KB | First-time setup |
| `.env.example` | <1KB | Config template |

**Total repo size: ~25MB**

## Git LFS

Large files (*.jsonl, databases/) are tracked with Git LFS.
Users need Git LFS installed to clone:

```bash
# Install Git LFS
git lfs install

# Clone (LFS files downloaded automatically)
git clone <repo-url>
```

## Quick Commands

```bash
# Start
./start.ps1

# Stop
./start.ps1 stop

# Test
./start.ps1 test

# View logs
./start.ps1 logs

# Check status
./start.ps1 status

# Update & rebuild
./start.ps1 update
```
