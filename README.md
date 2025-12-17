# Photo Blog

A Hugo-based photo blog with automated photo processing, EXIF extraction, and optional cloud storage.

## Features

- 📸 **Automatic photo processing** - Generates multiple sizes (original, medium, thumbnail)
- 📊 **EXIF data extraction** - Camera, lens, settings automatically extracted
- 🎨 **Responsive design** - Modern grid layout with PhotoSwipe lightbox
- 🔗 **Smart storage** - Symlink-based local dev, optional R2/B2 cloud storage
- ⚡ **Fast builds** - No image processing during Hugo build
- 📦 **Git-friendly** - Photos stay outside git, only YAML manifest committed
- 🔧 **Makefile automation** - Common tasks simplified

## Quick Start

### 1. Prerequisites

```bash
# Hugo (already installed)
hugo version  # Should be 0.123.0+

# Python 3
python3 --version  # Should be 3.8+
```

### 2. Install Dependencies

```bash
# Recommended: Use virtual environment
make setup

# This creates a venv and installs dependencies
# Or manually:
# make venv      # Create virtual environment
# make install   # Install dependencies
```

**Optional:** Install exiftool for EXIF extraction
```bash
# macOS
brew install exiftool

# Linux
sudo apt install libimage-exiftool-perl
```

### 3. Check Setup

```bash
make check
```

### 4. Add Your First Album

```bash
# Create album directory
mkdir ~/Pictures/albums/my-first-album

# Add photos
cp /path/to/your/photos/*.jpg ~/Pictures/albums/my-first-album/

# Optional: Add metadata
cat > ~/Pictures/albums/my-first-album/album.yaml << EOF
title: "My First Album"
description: "A collection of my favorite photos"
date: 2025-12-15
location: "San Francisco, CA"
tags:
  - photography
  - travel
EOF
```

### 5. Process Photos

```bash
make process
```

This automatically:
- Creates 3 sizes: original (4000px), medium (1600px), thumbnail (400px)
- Extracts EXIF data (camera, lens, settings)
- Generates `data/albums.yaml` manifest
- Creates `content/album/` page files
- Creates symlink `static/photos` → `~/Pictures/albums/`

### 6. Preview

```bash
make serve
# Open http://localhost:1313
```

## Photo Organization

### Directory Structure

```
~/Pictures/albums/
├── my-first-album/
│   ├── photo1.jpg              # Your original photos
│   ├── photo2.jpg
│   ├── album.yaml              # Optional metadata
│   ├── original/               # Processed (max 4000px)
│   ├── medium/                 # Processed (1600px)
│   └── thumbnail/              # Processed (400px)
└── another-album/
    └── ...
```

### How It Works

1. **Originals stay safe** - Your photos in `~/Pictures/albums/album-name/*.jpg`
2. **Processed versions** - Created in subdirectories (original/, medium/, thumbnail/)
3. **Symlink for Hugo** - `static/photos` → `~/Pictures/albums/`
4. **No duplication** - Photos never copied to git repo
5. **Manifest only** - Git tracks `data/albums.yaml` (tiny YAML file)

## Album Naming

### Directory Names

Use any name - spaces and special characters are OK:

```bash
~/Pictures/albums/
├── Trip to Japan 2025/         # ✅ Spaces OK
├── NYC Street Photography!/    # ✅ Special chars removed
├── Family Reunion (Dec 2025)/  # ✅ Parentheses OK
└── hiking-spring-2025/         # ✅ Hyphens preferred
```

### URL Conversion

Directory names are automatically converted to URL-safe IDs:

```
Directory Name              →  URL
─────────────────────────────────────────
Trip to Japan 2025          →  /album/trip-to-japan-2025/
NYC Street Photography!     →  /album/nyc-street-photography/
Family Reunion (Dec 2025)   →  /album/family-reunion-dec-2025/
```

### Custom Titles

Use `album.yaml` to customize the display title:

```yaml
title: "A Journey Through Japan"
description: "Two weeks exploring Tokyo, Kyoto, and Osaka"
date: 2025-03-15
location: "Tokyo, Japan"
tags:
  - travel
  - japan
  - photography
```

## Common Tasks

### Add New Album

```bash
# 1. Create directory and add photos
mkdir ~/Pictures/albums/new-album
cp photos/*.jpg ~/Pictures/albums/new-album/

# 2. Process
make process

# 3. Preview
make serve
```

### Update Existing Album

```bash
# Add more photos
cp more-photos/*.jpg ~/Pictures/albums/existing-album/

# Reprocess
make process
```

### Process Single Album

```bash
make process-album ALBUM=album-name
```

### Quick Development Workflow

```bash
make dev  # Process photos + start server
```

### Build for Production

```bash
make build
```

### Clean Build Files

```bash
make clean
```

### Show Site Info

```bash
make info
```

### Run Tests

```bash
make test
```

### All Available Commands

```bash
make help
```

## Configuration

### Environment Variables

Edit `.env`:

```bash
# Photo directories
PHOTOS_DIR=~/Pictures/albums
HUGO_REPO=.

# Cloud storage (optional - see ADVANCED.md)
USE_CLOUD_STORAGE=false

# Image sizes
ORIGINAL_MAX_WIDTH=4000
MEDIUM_WIDTH=1600
THUMBNAIL_WIDTH=400
JPEG_QUALITY=85
```

### Hugo Settings

Edit `hugo.toml`:

```toml
baseURL = 'https://photos.amirsadoughi.com/'
title = 'Your Name - Photography'

[params]
  description = "Personal photography portfolio"
  author = "Your Name"
```

## Deployment to Netlify

### First Time Setup

```bash
# 1. Initialize git
make git-init

# 2. Commit files
git add .
git commit -m "Initial commit"

# 3. Create GitHub repository and push
git remote add origin https://github.com/yourusername/photo-blog.git
git push -u origin main
```

### Connect to Netlify

1. Go to https://app.netlify.com/
2. Click "Add new site" → "Import an existing project"
3. Choose GitHub and select your repository
4. Settings auto-detected from `netlify.toml`
5. Click "Deploy"

### Password Protection (Optional)

For private viewing:

1. Netlify → Site Settings → Access Control
2. Enable "Password Protection"
3. Set a password
4. Share with friends/family

### Adding More Photos

```bash
# 1. Add photos locally
cp new-photos/*.jpg ~/Pictures/albums/album-name/

# 2. Process
make process

# 3. Deploy
git add data/albums.yaml content/album/
git commit -m "Add new photos"
git push
```

**Note:** For local storage, Netlify needs to process photos during build. For production, use cloud storage (see ADVANCED.md).

## Project Structure

```
.
├── content/
│   ├── _index.md              # Home page
│   └── album/                 # Album pages (auto-generated)
├── data/
│   └── albums.yaml            # Photo manifest (auto-generated)
├── layouts/
│   ├── _default/baseof.html   # Base template
│   ├── partials/              # Reusable components
│   ├── index.html             # Albums grid
│   └── album/single.html      # Album detail page
├── static/
│   ├── css/style.css          # Custom styles
│   └── photos/                # Symlink → ~/Pictures/albums
├── hugo.toml                  # Hugo config
├── netlify.toml               # Netlify build settings
├── Makefile                   # Task automation
├── upload-photos.py           # Photo processor
├── requirements.txt           # Python dependencies
└── .env                       # Configuration
```

## What Gets Committed to Git

```
✅ Code (layouts, CSS, templates)
✅ data/albums.yaml (manifest with metadata)
✅ content/album/*.md (album pages)
✅ Configuration files
❌ Photos (in ~/Pictures/albums/)
❌ static/photos/ (symlink)
❌ public/ (build output)
```

## Troubleshooting

### Photos not showing

```bash
# Check symlink
ls -la static/photos
# Should show: static/photos -> /home/user/Pictures/albums

# Recreate symlink
make process

# Verify processed photos exist
ls ~/Pictures/albums/album-name/medium/
```

### Album not appearing

```bash
# Check for photos in album
ls ~/Pictures/albums/album-name/*.jpg

# Reprocess
make process

# Check manifest
cat data/albums.yaml
```

### EXIF data missing

```bash
# Check if exiftool is installed
exiftool -ver

# Install exiftool
# macOS: brew install exiftool
# Linux: sudo apt install libimage-exiftool-perl
```

### Build errors

```bash
# Check Hugo version
hugo version  # Should be 0.123.0+

# Clean and rebuild
make clean
make build
```

### Process script errors

```bash
# Check dependencies
make check

# Reinstall Python packages
pip install -r requirements.txt
```

### Album URLs not working

Album IDs are sanitized for URLs. Check the generated ID:

```bash
# View album IDs
grep "^- id:" data/albums.yaml

# URLs should be: /album/<album-id>/
# Not the directory name
```

## Tips

1. **Organize by event/date** - Use descriptive directory names like `trip-japan-2025`
2. **Add metadata** - Create `album.yaml` for custom titles and descriptions
3. **Backup originals** - Keep originals backed up separately from the blog
4. **Use exiftool** - Install for automatic camera/lens/settings extraction
5. **Reprocess after changes** - Run `make process` after adding/removing photos
6. **For production** - Consider cloud storage (see ADVANCED.md)

## Size Estimates

### Example Album (7 photos)

```
Originals:      174 MB (untouched)
Processed:       25 MB (3 sizes)
Total disk:     199 MB

Git repo:        ~5 KB (manifest only!)
```

### Hugo Build

```
Local storage:   ~200MB (with photos)
Cloud storage:   ~2MB (HTML only)
Build time:      10-30 seconds
```

## Advanced Features

See `ADVANCED.md` for:

- Cloud storage setup (Cloudflare R2 / Backblaze B2)
- Custom domains
- Performance optimization
- CDN configuration
- Migration guides

## License

Personal project - all rights reserved for photos.
Code can be used as reference.

## Credits

- Built with [Hugo](https://gohugo.io/)
- Lightbox by [PhotoSwipe](https://photoswipe.com/)
- Image processing by [Pillow](https://python-pillow.org/)
- EXIF extraction by [ExifTool](https://exiftool.org/)
