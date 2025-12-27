.PHONY: help venv install setup process process-all serve build clean deploy git-init check test

# Default target
help:
	@echo "Photo Blog - Available Commands"
	@echo "================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make venv           - Create Python virtual environment"
	@echo "  make install        - Install Python dependencies"
	@echo "  make setup          - Complete initial setup (venv + install + dirs)"
	@echo "  make check          - Check all dependencies are installed"
	@echo ""
	@echo "Development:"
	@echo "  make process        - Smart process (only new/changed albums)"
	@echo "  make process-all    - Force reprocess all albums"
	@echo "  make process-album  - Process single album (usage: make process-album ALBUM=album-name)"
	@echo "  make serve          - Start Hugo dev server (with drafts)"
	@echo "  make serve-prod     - Start Hugo server in production mode"
	@echo ""
	@echo "Building:"
	@echo "  make build          - Build Hugo site for production"
	@echo "  make clean          - Clean generated files"
	@echo ""
	@echo "Workflow:"
	@echo "  make dev            - Process photos + serve (quick dev workflow)"
	@echo "  make deploy-ready   - Process photos + build (prepare for deploy)"
	@echo ""
	@echo "Git:"
	@echo "  make git-init       - Initialize git repository"
	@echo "  make git-status     - Show git status and photo directories"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run basic tests and validation"
	@echo ""
	@echo "Environment:"
	@echo "  ALBUM=name         - Specify album name for process-album"
	@echo "  PORT=1313          - Hugo server port (default: 1313)"

# Variables
VENV_DIR := venv
VENV_PYTHON := $(VENV_DIR)/bin/python3
VENV_PIP := $(VENV_DIR)/bin/pip

# Use venv if it exists, otherwise use system python
PYTHON := $(shell if [ -f $(VENV_PYTHON) ]; then echo $(VENV_PYTHON); else echo python3; fi)
PIP := $(shell if [ -f $(VENV_PIP) ]; then echo $(VENV_PIP); else echo "python3 -m pip"; fi)

HUGO := hugo
PHOTOS_DIR := $(shell grep PHOTOS_DIR .env 2>/dev/null | cut -d '=' -f2 | sed 's|~|$(HOME)|g' || echo "$(HOME)/Pictures/albums")
PORT ?= 1313

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Virtual Environment
venv:
	@if [ -d $(VENV_DIR) ]; then \
		echo "$(YELLOW)Virtual environment already exists at $(VENV_DIR)$(NC)"; \
	else \
		echo "$(BLUE)Creating Python virtual environment...$(NC)"; \
		python3 -m venv $(VENV_DIR); \
		echo "$(GREEN)✓ Virtual environment created$(NC)"; \
		echo ""; \
		echo "To activate manually:"; \
		echo "  source $(VENV_DIR)/bin/activate"; \
		echo ""; \
		echo "Note: Makefile automatically uses venv when available"; \
	fi

# Installation
install:
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(YELLOW)No virtual environment found. Creating one...$(NC)"; \
		$(MAKE) venv; \
		echo ""; \
	fi
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"
	@if [ -f $(VENV_PYTHON) ]; then \
		echo "$(GREEN)✓ Using virtual environment: $(VENV_DIR)$(NC)"; \
	else \
		echo "$(YELLOW)⚠ Using system Python$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Optional: Install exiftool for EXIF data extraction:$(NC)"
	@echo "  macOS:   brew install exiftool"
	@echo "  Linux:   sudo apt install libimage-exiftool-perl"
	@echo "  Check:   exiftool -ver"

setup: venv install
	@echo ""
	@echo "$(BLUE)Setting up directories...$(NC)"
	@mkdir -p $(PHOTOS_DIR)
	@mkdir -p content/album
	@mkdir -p static/photos
	@mkdir -p data
	@echo "$(GREEN)✓ Directories created$(NC)"
	@echo ""
	@echo "$(BLUE)Checking configuration...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)⚠ No .env file found, copying from .env.example$(NC)"; \
		cp .env.example .env; \
	else \
		echo "$(GREEN)✓ .env file exists$(NC)"; \
	fi
	@echo ""
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo "Next steps:"
	@echo "  1. Add photos to: $(PHOTOS_DIR)/your-album-name/"
	@echo "  2. Run: make process"
	@echo "  3. Run: make serve"

# Dependency checking
check:
	@echo "$(BLUE)Checking dependencies...$(NC)"
	@echo -n "Virtual env: "
	@if [ -d $(VENV_DIR) ]; then \
		echo "$(GREEN)✓ Active at $(VENV_DIR)$(NC)"; \
	else \
		echo "$(YELLOW)⚠ Not using venv (run: make venv)$(NC)"; \
	fi
	@echo -n "Hugo: "
	@if command -v hugo >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $(shell hugo version | cut -d' ' -f1-2)$(NC)"; \
	else \
		echo "$(RED)✗ Not installed$(NC)"; \
		echo "  Install: https://gohugo.io/installation/"; \
	fi
	@echo -n "Python 3: "
	@if command -v python3 >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $(shell python3 --version)$(NC)"; \
	else \
		echo "$(RED)✗ Not installed$(NC)"; \
	fi
	@echo -n "Pillow: "
	@if $(PYTHON) -c "import PIL" 2>/dev/null; then \
		echo "$(GREEN)✓ Installed$(NC)"; \
	else \
		echo "$(RED)✗ Not installed (run: make install)$(NC)"; \
	fi
	@echo -n "PyYAML: "
	@if $(PYTHON) -c "import yaml" 2>/dev/null; then \
		echo "$(GREEN)✓ Installed$(NC)"; \
	else \
		echo "$(RED)✗ Not installed (run: make install)$(NC)"; \
	fi
	@echo -n "boto3 (optional): "
	@if $(PYTHON) -c "import boto3" 2>/dev/null; then \
		echo "$(GREEN)✓ Installed$(NC)"; \
	else \
		echo "$(YELLOW)⚠ Not installed (only needed for cloud storage)$(NC)"; \
	fi
	@echo -n "exiftool (optional): "
	@if command -v exiftool >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $(shell exiftool -ver)$(NC)"; \
	else \
		echo "$(YELLOW)⚠ Not installed (EXIF data will be skipped)$(NC)"; \
	fi
	@echo ""
	@echo "$(BLUE)Configuration:$(NC)"
	@echo "Photos directory: $(PHOTOS_DIR)"
	@if [ -d "$(PHOTOS_DIR)" ]; then \
		echo "$(GREEN)✓ Directory exists$(NC)"; \
		echo "Albums found: $(shell find $(PHOTOS_DIR) -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"; \
	else \
		echo "$(RED)✗ Directory not found$(NC)"; \
	fi

# Photo processing
process:
	@echo "$(BLUE)Smart processing photos (skip already processed)...$(NC)"
	@$(PYTHON) upload-photos.py
	@echo "$(GREEN)✓ Processing complete$(NC)"

process-all:
	@echo "$(BLUE)Force processing all photos...$(NC)"
	@$(PYTHON) upload-photos.py --force
	@echo "$(GREEN)✓ Processing complete$(NC)"

process-album:
	@if [ -z "$(ALBUM)" ]; then \
		echo "$(RED)Error: ALBUM not specified$(NC)"; \
		echo "Usage: make process-album ALBUM=album-name"; \
		exit 1; \
	fi
	@echo "$(BLUE)Processing album: $(ALBUM)$(NC)"
	@$(PYTHON) upload-photos.py --album $(ALBUM)
	@echo "$(GREEN)✓ Album processed: $(ALBUM)$(NC)"

# Development server
serve:
	@echo "$(BLUE)Starting Hugo development server...$(NC)"
	@echo "$(GREEN)➜ Open: http://localhost:$(PORT)$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	@$(HUGO) server --buildDrafts --port $(PORT)

serve-prod:
	@echo "$(BLUE)Starting Hugo server (production mode)...$(NC)"
	@echo "$(GREEN)➜ Open: http://localhost:$(PORT)$(NC)"
	@$(HUGO) server --port $(PORT)

# Building
build:
	@echo "$(BLUE)Building Hugo site...$(NC)"
	@$(HUGO) --gc --minify
	@echo "$(GREEN)✓ Build complete: public/$(NC)"

clean:
	@echo "$(BLUE)Cleaning generated files...$(NC)"
	@rm -rf public/
	@rm -rf resources/_gen/
	@rm -f .hugo_build.lock
	@echo "$(GREEN)✓ Clean complete$(NC)"

# Combined workflows
dev: process serve

deploy-ready: clean process build
	@echo ""
	@echo "$(GREEN)✓ Ready for deployment!$(NC)"
	@echo "Next steps:"
	@echo "  1. git add data/albums.yaml"
	@echo "  2. git commit -m 'Update photos'"
	@echo "  3. git push"

# Git operations
git-init:
	@if [ -d .git ]; then \
		echo "$(YELLOW)Git repository already initialized$(NC)"; \
	else \
		echo "$(BLUE)Initializing git repository...$(NC)"; \
		git init; \
		echo "$(GREEN)✓ Git initialized$(NC)"; \
		echo ""; \
		echo "Next steps:"; \
		echo "  1. Create repository on GitHub"; \
		echo "  2. git add ."; \
		echo "  3. git commit -m 'Initial commit'"; \
		echo "  4. git remote add origin <your-repo-url>"; \
		echo "  5. git push -u origin main"; \
	fi

git-status:
	@echo "$(BLUE)Git Status:$(NC)"
	@git status --short 2>/dev/null || echo "$(YELLOW)Not a git repository$(NC)"
	@echo ""
	@echo "$(BLUE)Photo Albums:$(NC)"
	@if [ -d "$(PHOTOS_DIR)" ]; then \
		find $(PHOTOS_DIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | while read album; do \
			count=$$(find $(PHOTOS_DIR)/$$album -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) 2>/dev/null | wc -l); \
			echo "  $$album: $$count photos"; \
		done; \
	else \
		echo "$(YELLOW)Photos directory not found: $(PHOTOS_DIR)$(NC)"; \
	fi

# Testing
test:
	@echo "$(BLUE)Running tests...$(NC)"
	@echo ""
	@echo "1. Checking configuration..."
	@if [ ! -f .env ]; then \
		echo "$(RED)✗ .env file missing$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ .env file exists$(NC)"; \
	fi
	@echo ""
	@echo "2. Checking manifest..."
	@if [ ! -f data/albums.yaml ]; then \
		echo "$(RED)✗ data/albums.yaml missing (run: make process)$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ data/albums.yaml exists$(NC)"; \
		albums=$$(grep -c "^  - id:" data/albums.yaml 2>/dev/null || echo 0); \
		echo "  Found $$albums album(s)"; \
	fi
	@echo ""
	@echo "3. Checking layouts..."
	@if [ ! -f layouts/index.html ]; then \
		echo "$(RED)✗ layouts/index.html missing$(NC)"; \
	else \
		echo "$(GREEN)✓ layouts/index.html exists$(NC)"; \
	fi
	@if [ ! -f layouts/album/single.html ]; then \
		echo "$(RED)✗ layouts/album/single.html missing$(NC)"; \
	else \
		echo "$(GREEN)✓ layouts/album/single.html exists$(NC)"; \
	fi
	@echo ""
	@echo "4. Testing Hugo build..."
	@if $(HUGO) --quiet 2>/dev/null; then \
		echo "$(GREEN)✓ Hugo build successful$(NC)"; \
	else \
		echo "$(RED)✗ Hugo build failed$(NC)"; \
		exit 1; \
	fi
	@echo ""
	@echo "$(GREEN)All tests passed!$(NC)"

# Info targets
info:
	@echo "$(BLUE)Photo Blog Information$(NC)"
	@echo "======================"
	@echo ""
	@echo "Configuration:"
	@echo "  Photos directory: $(PHOTOS_DIR)"
	@echo "  Hugo site: $(shell pwd)"
	@echo ""
	@if [ -f data/albums.yaml ]; then \
		albums=$$(grep -c "^  - id:" data/albums.yaml 2>/dev/null || echo 0); \
		photos=$$(grep -c "^      - id:" data/albums.yaml 2>/dev/null || echo 0); \
		echo "Content:"; \
		echo "  Albums: $$albums"; \
		echo "  Photos: $$photos"; \
		echo ""; \
	fi
	@if [ -d public ]; then \
		size=$$(du -sh public 2>/dev/null | cut -f1); \
		files=$$(find public -type f 2>/dev/null | wc -l); \
		echo "Build:"; \
		echo "  Output size: $$size"; \
		echo "  Files: $$files"; \
	else \
		echo "Build: Not built yet (run: make build)"; \
	fi
