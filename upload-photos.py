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

    def needs_processing(self, album_dir: Path) -> bool:
        """Check if album needs processing (new photos or missing processed versions)"""
        # Find source photos
        image_extensions = {'.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG'}
        source_photos = [p for p in album_dir.iterdir()
                        if p.is_file() and p.suffix in image_extensions]

        if not source_photos:
            return False

        # Check if processed directories exist
        original_dir = album_dir / 'original'
        medium_dir = album_dir / 'medium'
        thumbnail_dir = album_dir / 'thumbnail'

        if not (original_dir.exists() and medium_dir.exists() and thumbnail_dir.exists()):
            return True  # Missing processed directories

        # Check if photo counts match
        processed_photos = list(original_dir.glob('*.[jJ][pP][gG]')) + \
                          list(original_dir.glob('*.[jJ][pP][eE][gG]')) + \
                          list(original_dir.glob('*.[pP][nN][gG]'))

        if len(source_photos) != len(processed_photos):
            return True  # Photo count mismatch

        # Check if all source photos have processed versions
        source_names = {p.name for p in source_photos}
        processed_names = {p.name for p in processed_photos}

        if source_names != processed_names:
            return True  # Different photo sets

        return False  # All good, no processing needed

    def read_processed_photos(self, album_dir: Path, album_id: str) -> List[Dict[str, Any]]:
        """Read already-processed photos without re-processing"""
        # Find all image files in root
        image_extensions = {'.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG'}
        photo_paths = sorted([p for p in album_dir.iterdir()
                             if p.is_file() and p.suffix in image_extensions])

        if not photo_paths:
            return []

        photos = []
        for photo_path in photo_paths:
            photo_data = {
                'id': photo_path.stem,
                'filename': photo_path.name,
                'urls': {}
            }

            # Generate URLs based on storage mode
            sizes = ['original', 'medium', 'thumbnail']
            for size_name in sizes:
                if self.use_cloud_storage:
                    s3_key = f"albums/{album_id}/{size_name}/{photo_path.name}"
                    url = f"{self.cdn_base_url}/{s3_key}"
                else:
                    url = f"/photos/{album_dir.name}/{size_name}/{photo_path.name}"
                photo_data['urls'][size_name] = url

            # Read EXIF from SOURCE photo (not processed), to preserve all metadata
            exif = self.extract_exif(photo_path)
            if exif:
                photo_data['exif'] = exif
                if 'width' in exif:
                    photo_data['width'] = exif['width']
                if 'height' in exif:
                    photo_data['height'] = exif['height']

            photos.append(photo_data)

        return photos

    def process_album(self, album_dir: Path, metadata_only: bool = False) -> Dict[str, Any]:
        """Process all photos in an album"""
        album_dir_name = album_dir.name
        album_id = self.sanitize_album_id(album_dir_name)

        if metadata_only:
            print(f"\n✓ Updating metadata for: {album_dir_name} (ID: {album_id})")
        else:
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

        # If metadata-only mode, read existing processed photos
        if metadata_only:
            photos = self.read_processed_photos(album_dir, album_id)
            if not photos:
                print(f"  Warning: No processed photos found, switching to full processing")
                metadata_only = False

        # Full processing mode
        if not metadata_only:
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

        if metadata_only:
            print(f"  Updated metadata ({len(photos)} photos)")
        else:
            print(f"  Processed {len(photos)} photos")
        return album

    def generate_manifest(self, album_filter: Optional[str] = None, force: bool = False):
        """Generate albums.yaml manifest"""
        print(f"Scanning photos directory: {self.photos_dir}")

        if not self.photos_dir.exists():
            print(f"Error: Photos directory does not exist: {self.photos_dir}")
            return

        # Load existing manifest if it exists
        manifest_path = self.hugo_repo / 'data' / 'albums.yaml'
        existing_albums = {}
        if manifest_path.exists() and not album_filter:
            try:
                with open(manifest_path, 'r') as f:
                    existing_data = yaml.safe_load(f)
                    if existing_data and 'albums' in existing_data:
                        # Index by album ID for easy lookup
                        existing_albums = {a['id']: a for a in existing_data['albums']}
                        print(f"Loaded {len(existing_albums)} existing albums from manifest")
            except Exception as e:
                print(f"Warning: Could not load existing manifest: {e}")

        processed_albums = {}
        processed_count = 0
        skipped_count = 0

        # Process each album directory
        for album_dir in sorted(self.photos_dir.iterdir()):
            if not album_dir.is_dir():
                continue

            album_dir_name = album_dir.name
            album_id = self.sanitize_album_id(album_dir_name)

            # Skip if filtering by album
            if album_filter and album_dir.name != album_filter:
                # Keep existing album data if not filtering on it
                if album_id in existing_albums:
                    processed_albums[album_id] = existing_albums[album_id]
                continue

            # Check if processing is needed (unless forced or filtering specific album)
            needs_proc = self.needs_processing(album_dir)

            if not force and not album_filter and not needs_proc:
                # Photos unchanged - just update metadata
                album = self.process_album(album_dir, metadata_only=True)
                if album:
                    processed_albums[album['id']] = album
                    skipped_count += 1
            else:
                # Photos changed or forced - full processing
                album = self.process_album(album_dir, metadata_only=False)
                if album:
                    processed_albums[album['id']] = album
                    processed_count += 1

        if not processed_albums:
            print("\nNo albums found.")
            return

        # Convert back to list
        albums = list(processed_albums.values())

        # Generate manifest
        manifest = {'albums': albums}

        # Write YAML file
        manifest_path.parent.mkdir(exist_ok=True)

        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, sort_keys=False, allow_unicode=True, default_flow_style=False)

        print(f"\n✓ Manifest written to: {manifest_path}")
        print(f"✓ Fully processed: {processed_count} album(s)")
        print(f"✓ Metadata updated: {skipped_count} album(s) (photos unchanged)")
        print(f"✓ Total albums in manifest: {len(albums)}")

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
    parser.add_argument('--force', action='store_true', help='Force reprocess all albums (skip smart detection)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()

    # Load configuration
    config = load_config()

    print("Photo Blog Upload Script")
    print("=" * 50)
    print(f"Photos directory: {config['photos_dir']}")
    print(f"Hugo repository: {config['hugo_repo']}")
    print(f"Cloud storage: {'Enabled' if config['use_cloud_storage'] else 'Disabled (using local storage)'}")
    if args.force:
        print(f"Mode: FORCE (reprocess all albums)")
    elif args.album:
        print(f"Mode: Single album ({args.album})")
    else:
        print(f"Mode: Smart (skip already processed albums)")
    print("=" * 50)

    if args.dry_run:
        print("\nDRY RUN MODE - No changes will be made")
        return

    # Create uploader and generate manifest
    uploader = PhotoUploader(config)
    uploader.generate_manifest(album_filter=args.album, force=args.force)

    print("\n✓ Done! You can now preview with: hugo server")


if __name__ == '__main__':
    main()
