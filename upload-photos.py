#!/usr/bin/env python3
"""
Photo Blog Upload Script
Processes photos from local albums directory, generates multiple sizes,
extracts EXIF data, and creates Hugo data manifest.

Usage:
    python upload-photos.py [--album ALBUM_NAME] [--dry-run]
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import yaml

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None  # Remove decompression bomb protection
except ImportError:
    print("Error: Pillow is not installed. Install it with: pip install Pillow")
    sys.exit(1)

# Optional boto3 for S3-compatible storage (R2/B2)
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class PhotoUploader:
    """Handles photo processing and manifest generation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.photos_dir = Path(config['photos_dir']).expanduser()
        self.hugo_repo = Path(config['hugo_repo']).expanduser()
        self.use_cloud_storage = config.get('use_cloud_storage', False)

        # Initialize S3 client if cloud storage is enabled
        self.s3_client = None
        if self.use_cloud_storage:
            if not HAS_BOTO3:
                print("Warning: boto3 not installed. Cloud storage disabled.")
                print("Install with: pip install boto3")
                self.use_cloud_storage = False
            else:
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=config.get('s3_endpoint'),
                    aws_access_key_id=config.get('s3_access_key'),
                    aws_secret_access_key=config.get('s3_secret_key')
                )
                self.s3_bucket = config.get('s3_bucket')
                self.cdn_base_url = config.get('cdn_base_url')

        # Image size configurations
        self.original_max_width = config.get('original_max_width', 4000)
        self.medium_width = config.get('medium_width', 1600)
        self.thumbnail_width = config.get('thumbnail_width', 400)
        self.jpeg_quality = config.get('jpeg_quality', 85)

    def extract_exif(self, photo_path: Path) -> Dict[str, Any]:
        """Extract EXIF data from photo using exiftool"""
        try:
            result = subprocess.run(
                [
                    'exiftool', '-json',
                    '-Make', '-Model', '-LensModel',
                    '-ISO', '-ShutterSpeed', '-Aperture', '-FNumber',
                    '-FocalLength', '-DateTimeOriginal',
                    '-ImageWidth', '-ImageHeight',
                    str(photo_path)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)[0]

            # Format EXIF data
            exif = {}
            if 'Make' in data and 'Model' in data:
                exif['camera'] = f"{data['Make']} {data['Model']}"
            elif 'Model' in data:
                exif['camera'] = data['Model']

            if 'LensModel' in data:
                exif['lens'] = data['LensModel']

            if 'FocalLength' in data:
                exif['focal_length'] = data['FocalLength']

            if 'FNumber' in data:
                exif['aperture'] = str(data['FNumber'])
            elif 'Aperture' in data:
                exif['aperture'] = str(data['Aperture'])

            if 'ShutterSpeed' in data:
                exif['shutter_speed'] = data['ShutterSpeed']

            if 'ISO' in data:
                exif['iso'] = data['ISO']

            if 'DateTimeOriginal' in data:
                try:
                    dt = datetime.strptime(data['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S')
                    exif['date_taken'] = dt.isoformat() + 'Z'
                except:
                    pass

            if 'ImageWidth' in data and 'ImageHeight' in data:
                exif['width'] = data['ImageWidth']
                exif['height'] = data['ImageHeight']

            return exif
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
            # exiftool not available or failed, return empty dict
            return {}

    def resize_image(self, img: Image.Image, target_width: int) -> Image.Image:
        """Resize image maintaining aspect ratio"""
        if img.width <= target_width:
            return img

        ratio = target_width / img.width
        target_height = int(img.height * ratio)
        return img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    def process_image(self, photo_path: Path, output_dir: Path, size_name: str, target_width: int) -> Path:
        """Process and save a single image size"""
        output_path = output_dir / photo_path.name

        # Open and process image
        with Image.open(photo_path) as img:
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize if needed
            if target_width:
                img = self.resize_image(img, target_width)

            # Save
            img.save(output_path, 'JPEG', quality=self.jpeg_quality, optimize=True)

        return output_path

    def upload_to_cloud(self, local_path: Path, s3_key: str) -> str:
        """Upload file to S3-compatible storage (R2/B2)"""
        if not self.use_cloud_storage or not self.s3_client:
            return str(local_path)

        try:
            self.s3_client.upload_file(
                str(local_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )
            return f"{self.cdn_base_url}/{s3_key}"
        except Exception as e:
            print(f"Warning: Failed to upload {s3_key}: {e}")
            return str(local_path)

    def process_photo(self, photo_path: Path, album_id: str, album_dir: Path) -> Dict[str, Any]:
        """Process a single photo: resize, upload (if cloud), extract EXIF"""
        print(f"  Processing {photo_path.name}...")

        # Create size directories in the album directory
        sizes = {
            'original': self.original_max_width,
            'medium': self.medium_width,
            'thumbnail': self.thumbnail_width
        }

        photo_data = {
            'id': photo_path.stem,
            'filename': photo_path.name,
            'urls': {}
        }

        # Process each size
        for size_name, target_width in sizes.items():
            # Save processed photos in album_dir/size_name/
            size_dir = album_dir / size_name
            size_dir.mkdir(exist_ok=True)

            # Process image
            output_path = self.process_image(photo_path, size_dir, size_name, target_width)

            # Upload to cloud or use local path
            if self.use_cloud_storage:
                s3_key = f"albums/{album_id}/{size_name}/{photo_path.name}"
                url = self.upload_to_cloud(output_path, s3_key)
            else:
                # Use local path - photos stay in ~/Pictures/albums/
                # symlink from static/photos will point to ~/Pictures/albums
                rel_path = f"/photos/{album_dir.name}/{size_name}/{photo_path.name}"
                url = rel_path

            photo_data['urls'][size_name] = url

        # Extract EXIF data
        exif = self.extract_exif(photo_path)
        if exif:
            photo_data['exif'] = exif
            if 'width' in exif:
                photo_data['width'] = exif['width']
            if 'height' in exif:
                photo_data['height'] = exif['height']

        return photo_data

    def read_album_metadata(self, album_dir: Path) -> Dict[str, Any]:
        """Read album metadata from album.txt or album.yaml if it exists"""
        metadata = {}

        # Try YAML first
        yaml_file = album_dir / 'album.yaml'
        if yaml_file.exists():
            with open(yaml_file, 'r') as f:
                metadata = yaml.safe_load(f) or {}
        else:
            # Try text file
            txt_file = album_dir / 'album.txt'
            if txt_file.exists():
                with open(txt_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 0:
                        metadata['title'] = lines[0].strip()
                    if len(lines) > 1:
                        metadata['description'] = lines[1].strip()

        return metadata

    def sanitize_album_id(self, name: str) -> str:
        """Convert album name to URL-safe ID"""
        import re
        # Convert to lowercase, replace spaces/special chars with hyphens
        slug = name.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars except spaces and hyphens
        slug = re.sub(r'[-\s]+', '-', slug)   # Replace spaces/multiple hyphens with single hyphen
        slug = slug.strip('-')                # Remove leading/trailing hyphens
        return slug

    def process_album(self, album_dir: Path) -> Dict[str, Any]:
        """Process all photos in an album"""
        album_dir_name = album_dir.name
        album_id = self.sanitize_album_id(album_dir_name)
        print(f"\nProcessing album: {album_dir_name} (ID: {album_id})")

        # Find all image files (only in root of album dir, not in subdirectories)
        image_extensions = {'.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG'}
        photo_paths = [p for p in album_dir.iterdir()
                      if p.is_file() and p.suffix in image_extensions]

        if not photo_paths:
            print(f"  No photos found in {album_id}")
            return None

        # Read metadata
        metadata = self.read_album_metadata(album_dir)

        # Processed photos will be saved directly in album_dir subdirectories
        # No temp directory needed - everything stays in ~/Pictures/albums/

        # Process each photo
        photos = []
        for photo_path in sorted(photo_paths):
            try:
                photo_data = self.process_photo(photo_path, album_id, album_dir)
                photos.append(photo_data)
            except Exception as e:
                print(f"  Error processing {photo_path.name}: {e}")

        if not photos:
            return None

        # Build album data
        album = {
            'id': album_id,
            'title': metadata.get('title', album_dir_name),  # Use original directory name as default title
            'photos': photos
        }

        # Add optional fields
        if 'description' in metadata:
            album['description'] = metadata['description']
        if 'date' in metadata:
            album['date'] = metadata['date']
        else:
            # Use current date as fallback
            album['date'] = datetime.now().date().isoformat()
        if 'location' in metadata:
            album['location'] = metadata['location']
        if 'tags' in metadata:
            album['tags'] = metadata['tags']
        if 'cover_photo' in metadata:
            album['cover_photo'] = metadata['cover_photo']

        print(f"  Processed {len(photos)} photos")
        return album

    def generate_manifest(self, album_filter: Optional[str] = None):
        """Generate albums.yaml manifest"""
        print(f"Scanning photos directory: {self.photos_dir}")

        if not self.photos_dir.exists():
            print(f"Error: Photos directory does not exist: {self.photos_dir}")
            return

        albums = []

        # Process each album directory
        for album_dir in sorted(self.photos_dir.iterdir()):
            if not album_dir.is_dir():
                continue

            # Skip if filtering by album
            if album_filter and album_dir.name != album_filter:
                continue

            album = self.process_album(album_dir)
            if album:
                albums.append(album)

        if not albums:
            print("\nNo albums found to process.")
            return

        # Generate manifest
        manifest = {'albums': albums}

        # Write YAML file
        manifest_path = self.hugo_repo / 'data' / 'albums.yaml'
        manifest_path.parent.mkdir(exist_ok=True)

        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, sort_keys=False, allow_unicode=True, default_flow_style=False)

        print(f"\n✓ Manifest written to: {manifest_path}")
        print(f"✓ Processed {len(albums)} albums")

        # Create content files for each album
        print(f"\nCreating content files...")
        content_dir = self.hugo_repo / 'content' / 'album'
        content_dir.mkdir(parents=True, exist_ok=True)

        for album in albums:
            content_file = content_dir / f"{album['id']}.md"
            content = f"""---
title: "{album['title']}"
type: album
---
"""
            with open(content_file, 'w') as f:
                f.write(content)
            print(f"  Created: content/album/{album['id']}.md")

        print(f"✓ Created {len(albums)} content files")

        # For local storage, create symlink from static/photos to photos directory
        if not self.use_cloud_storage:
            self.setup_local_symlink()

    def setup_local_symlink(self):
        """Create symlink from static/photos to ~/Pictures/albums for local dev"""
        static_photos = self.hugo_repo / 'static' / 'photos'

        # Remove existing directory/symlink
        if static_photos.is_symlink():
            static_photos.unlink()
            print(f"\n✓ Removed old symlink: {static_photos}")
        elif static_photos.exists():
            import shutil
            shutil.rmtree(static_photos)
            print(f"\n✓ Removed old directory: {static_photos}")

        # Create symlink
        static_photos.symlink_to(self.photos_dir.resolve())
        print(f"✓ Created symlink: static/photos → {self.photos_dir}")
        print(f"  (Processed photos in ~/Pictures/albums/ are now accessible to Hugo)")


def load_config() -> Dict[str, Any]:
    """Load configuration from .env file or environment variables"""
    config = {
        'photos_dir': os.getenv('PHOTOS_DIR', '~/Pictures/albums'),
        'hugo_repo': os.getenv('HUGO_REPO', '.'),
        'use_cloud_storage': os.getenv('USE_CLOUD_STORAGE', 'false').lower() == 'true',
        'original_max_width': int(os.getenv('ORIGINAL_MAX_WIDTH', '4000')),
        'medium_width': int(os.getenv('MEDIUM_WIDTH', '1600')),
        'thumbnail_width': int(os.getenv('THUMBNAIL_WIDTH', '400')),
        'jpeg_quality': int(os.getenv('JPEG_QUALITY', '85')),
    }

    # Try to load .env file if it exists
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:  # Don't override existing env vars
                            os.environ[key] = value
                            # Update config
                            if key == 'PHOTOS_DIR':
                                config['photos_dir'] = value
                            elif key == 'HUGO_REPO':
                                config['hugo_repo'] = value
                            elif key == 'USE_CLOUD_STORAGE':
                                config['use_cloud_storage'] = value.lower() == 'true'

    # Cloud storage settings (optional) - load AFTER .env file
    if config['use_cloud_storage']:
        config.update({
            's3_endpoint': os.getenv('S3_ENDPOINT'),
            's3_access_key': os.getenv('S3_ACCESS_KEY'),
            's3_secret_key': os.getenv('S3_SECRET_KEY'),
            's3_bucket': os.getenv('S3_BUCKET', 'photos'),
            'cdn_base_url': os.getenv('CDN_BASE_URL'),
        })

    return config


def main():
    parser = argparse.ArgumentParser(description='Process photos and generate Hugo manifest')
    parser.add_argument('--album', help='Process only specific album')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()

    # Load configuration
    config = load_config()

    print("Photo Blog Upload Script")
    print("=" * 50)
    print(f"Photos directory: {config['photos_dir']}")
    print(f"Hugo repository: {config['hugo_repo']}")
    print(f"Cloud storage: {'Enabled' if config['use_cloud_storage'] else 'Disabled (using local storage)'}")
    print("=" * 50)

    if args.dry_run:
        print("\nDRY RUN MODE - No changes will be made")
        return

    # Create uploader and generate manifest
    uploader = PhotoUploader(config)
    uploader.generate_manifest(album_filter=args.album)

    print("\n✓ Done! You can now preview with: hugo server")


if __name__ == '__main__':
    main()
