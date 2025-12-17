# Advanced Configuration

Optional features and cloud storage setup for production deployments.

## Table of Contents

- [Cloud Storage Setup](#cloud-storage-setup)
- [Custom Domains](#custom-domains)
- [Performance Optimization](#performance-optimization)
- [Migration Guides](#migration-guides)
- [Advanced Album Management](#advanced-album-management)

---

## Cloud Storage Setup

For production deployments, use Cloudflare R2 or Backblaze B2 instead of local storage.

### Why Cloud Storage?

**Local Storage:**
- Photos in `static/photos/` via symlink
- Git repo references local paths
- Netlify must process photos during build (slow, expensive)

**Cloud Storage (R2/B2):**
- Photos stored in cloud CDN
- Git repo only has manifest (~5KB)
- Fast Netlify builds (<30 seconds)
- Cheap storage (~$1-2/month for 100GB)
- Zero egress fees (R2)

---

## Cloudflare R2 Setup (Recommended)

### Pros
- **Zero egress fees** (unlimited free downloads!)
- Built-in global CDN
- Easy custom domain setup
- $0.015/GB/month storage

### Setup Steps

#### 1. Create R2 Bucket

1. Go to https://dash.cloudflare.com/
2. Navigate to **R2 Object Storage**
3. Click **Create bucket**
4. Name: `photos` (or your preferred name)
5. Location: Auto (or choose closest region)
6. Click **Create bucket**

#### 2. Enable Public Access

1. In bucket settings, click **Settings**
2. Scroll to **Public access**
3. Click **Allow Access** or **Connect domain**
4. Note the public R2.dev URL: `https://your-bucket.r2.dev`

#### 3. Create API Token

1. Go to **R2** → **Manage R2 API Tokens**
2. Click **Create API token**
3. Name: `photo-blog-upload`
4. Permissions: **Object Read & Write**
5. Bucket: Select your `photos` bucket
6. Click **Create API token**
7. **Save these credentials:**
   - Access Key ID
   - Secret Access Key
   - Endpoint URL (e.g., `https://abc123.r2.cloudflarestorage.com`)

#### 4. Configure Photo Blog

Edit `.env`:

```bash
USE_CLOUD_STORAGE=true

# Cloudflare R2 Settings
S3_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
S3_ACCESS_KEY=your_access_key_id_here
S3_SECRET_KEY=your_secret_access_key_here
S3_BUCKET=photos
CDN_BASE_URL=https://your-bucket.r2.dev
```

#### 5. Install boto3

```bash
pip install boto3
```

#### 6. Upload Photos

```bash
# Process and upload to R2
make process

# Check manifest - URLs should point to R2
cat data/albums.yaml
```

### Cost Estimate (R2)

- Storage: $0.015/GB/month
- Egress: **$0** (free!)
- Operations: ~$0.001/month (negligible)

**100GB photos: ~$1.50/month**

---

## Backblaze B2 Setup

### Pros
- Very cheap storage ($0.005/GB/month)
- S3-compatible API
- Good for private/low-traffic sites

### Cons
- Egress fees after free tier
- Slower than R2 without CDN

### Setup Steps

#### 1. Create B2 Bucket

1. Go to https://www.backblaze.com/b2/
2. Sign up or log in
3. Navigate to **Buckets** → **Create a Bucket**
4. Bucket Name: `photos` (must be globally unique)
5. Files in Bucket: **Public**
6. Click **Create a Bucket**

#### 2. Create Application Key

1. Go to **App Keys** (in left sidebar)
2. Click **Add a New Application Key**
3. Name: `photo-blog-upload`
4. Bucket Access: Your `photos` bucket
5. Type of Access: **Read and Write**
6. Click **Create New Key**
7. **Save these:**
   - keyID (Access Key)
   - applicationKey (Secret Key)

#### 3. Configure Photo Blog

Edit `.env`:

```bash
USE_CLOUD_STORAGE=true

# Backblaze B2 Settings
S3_ENDPOINT=https://s3.us-west-004.backblazeb2.com
S3_ACCESS_KEY=your_key_id_here
S3_SECRET_KEY=your_application_key_here
S3_BUCKET=photos
CDN_BASE_URL=https://f004.backblazeb2.com/file/photos
```

**Note:** Endpoint varies by region. Check your bucket settings for the correct endpoint.

#### 4. Upload Photos

```bash
pip install boto3
make process
```

### Cost Estimate (B2)

- Storage: $0.005/GB/month
- Egress: First 3x storage free per month, then $0.01/GB
- Operations: ~$0.001/month

**100GB photos:**
- Storage: $0.50/month
- Free egress: 300GB/month
- Total: ~$0.50-2/month

---

## Testing Cloud Storage

After configuring:

```bash
# Test with single album
make process-album ALBUM=test-album

# Check manifest URLs
cat data/albums.yaml
# Should show: https://your-bucket.r2.dev/albums/...

# Test in browser
make serve
# Images should load from cloud
```

---

## Custom Domains

### Using Custom Subdomain with R2

For URLs like `cdn.yourdomain.com`:

#### 1. Connect Domain in R2

1. In R2 bucket settings, click **Connect domain**
2. Enter: `cdn.yourdomain.com`

#### 2. Add DNS Record

In your DNS provider (Cloudflare, etc.):

```
Type: CNAME
Name: cdn
Target: your-bucket.r2.dev
```

#### 3. Update Configuration

Edit `.env`:

```bash
CDN_BASE_URL=https://cdn.yourdomain.com
```

#### 4. Reprocess Photos

```bash
make process
```

### Custom Domain for Hugo Site

Edit `hugo.toml`:

```toml
baseURL = 'https://photos.yourdomain.com/'
```

In Netlify:
1. Site Settings → Domain Management
2. Add custom domain: `photos.yourdomain.com`
3. Add DNS record (Netlify provides instructions)

---

## Performance Optimization

### Image Quality Settings

Edit `.env` for different size/quality tradeoffs:

```bash
# Higher quality, larger files
JPEG_QUALITY=90
MEDIUM_WIDTH=2000

# Lower quality, smaller files (faster)
JPEG_QUALITY=80
MEDIUM_WIDTH=1400
```

### Lazy Loading

Already implemented in layouts. Images load as you scroll.

### Preloading

Add to `layouts/partials/head.html`:

```html
<!-- Preload first album cover -->
{{ if .IsHome }}
  {{ range first 1 .Site.Data.albums.albums }}
    {{ $cover := index .photos 0 }}
    <link rel="preload" as="image" href="{{ $cover.urls.thumbnail }}">
  {{ end }}
{{ end }}
```

### Cache Headers

Already configured in `netlify.toml`:

```toml
[[headers]]
  for = "/photos/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

---

## Migration Guides

### From Local to Cloud Storage

```bash
# 1. Set up R2/B2 credentials in .env
USE_CLOUD_STORAGE=true
# ... add credentials ...

# 2. Upload existing photos
make process

# 3. Test
make serve

# 4. Deploy
git add data/albums.yaml
git commit -m "Migrate to cloud storage"
git push
```

### From Cloud Back to Local

```bash
# 1. Update .env
USE_CLOUD_STORAGE=false

# 2. Reprocess (creates symlink)
make process

# 3. Processed photos are already in ~/Pictures/albums/
make serve
```

### Moving Photos Directory

```bash
# 1. Move photos
mv ~/Pictures/albums ~/Photos/blog-albums

# 2. Update .env
PHOTOS_DIR=~/Photos/blog-albums

# 3. Reprocess
make process
```

---

## Advanced Album Management

### Batch Renaming Albums

```bash
# Rename directory
mv ~/Pictures/albums/old-name ~/Pictures/albums/new-name

# Reprocess
make process

# Old processed photos remain but won't be linked
# Clean up manually if needed:
rm -rf static/photos/old-name/  # If local storage
```

### Selective Processing

Process only changed albums:

```bash
# Process single album
make process-album ALBUM=album-name

# Process multiple albums
for album in album1 album2 album3; do
    make process-album ALBUM=$album
done
```

### Album Metadata Best Practices

Create detailed `album.yaml`:

```yaml
title: "Yosemite National Park - Summer 2025"
description: |
  A week exploring waterfalls, granite cliffs, and alpine meadows.
  Highlights include Half Dome, El Capitan, and Glacier Point.
date: 2025-07-15
location: "Yosemite National Park, CA, USA"
tags:
  - nature
  - hiking
  - landscape
  - national-parks
  - california
camera: "Sony A7 IV"
```

### Managing Large Collections

For 100+ albums:

1. **Organize by year:**
   ```
   ~/Pictures/albums/
   ├── 2023/
   │   ├── trip-paris/
   │   └── summer-hiking/
   ├── 2024/
   │   └── ...
   └── 2025/
       └── ...
   ```

   **Note:** Upload script expects flat structure. Use symlinks:
   ```bash
   ln -s ~/Pictures/albums/2023/* ~/Pictures/albums/
   ```

2. **Partial uploads:** Process only new albums
   ```bash
   make process-album ALBUM=new-album-name
   ```

3. **Cloud storage recommended** for large collections

---

## Security Considerations

### Protecting Credentials

- `.env` is in `.gitignore` - never commit credentials
- Use environment variables on Netlify for secrets
- Rotate API keys periodically

### Password Protection

Netlify password protection options:

1. **Site-wide password:**
   - Site Settings → Access Control
   - Simple, covers entire site

2. **Per-album protection:**
   - Not natively supported
   - Consider using Netlify Functions for custom auth

### Private Buckets

For private albums:

1. Keep R2/B2 bucket private
2. Use signed URLs (requires custom script)
3. Or use Netlify password protection + public bucket

---

## Monitoring & Analytics

### Netlify Analytics

Enable in Netlify dashboard:
- Site Settings → Analytics
- $9/month per site

### Cloudflare Analytics (R2)

If using R2 with Cloudflare domain:
- Free analytics in Cloudflare dashboard
- Shows bandwidth, requests, cache hits

### Custom Analytics

Add to `layouts/partials/footer.html`:

```html
<!-- Google Analytics, Plausible, etc. -->
```

---

## Backup Strategies

### Original Photos

**Critical:** Always backup originals separately

Options:
1. External hard drive (cheap, offline)
2. Cloud backup (Backblaze Personal, Google Photos)
3. NAS (network storage)

### Processed Photos

Can be regenerated anytime:

```bash
# Delete processed to save space
rm -rf ~/Pictures/albums/*/original/
rm -rf ~/Pictures/albums/*/medium/
rm -rf ~/Pictures/albums/*/thumbnail/

# Regenerate when needed
make process
```

### Code & Configuration

```bash
# Regular git commits
git add .
git commit -m "Update albums"
git push
```

---

## Troubleshooting Cloud Storage

### Authentication Errors

```bash
# Test connection
python3 << EOF
import boto3
import os
from pathlib import Path

# Load .env
env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value.strip('"').strip("'")

s3 = boto3.client('s3',
    endpoint_url=os.getenv('S3_ENDPOINT'),
    aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('S3_SECRET_KEY')
)

print("Testing connection...")
print(s3.list_buckets())
print("✓ Connection successful!")
EOF
```

### Upload Failures

- Check credentials in `.env`
- Verify endpoint URL is correct
- Ensure API token has write permissions
- Check bucket name matches

### Images Not Loading

- Verify bucket is public
- Test CDN URL directly in browser
- Check CORS settings if needed
- Verify manifest URLs are correct

---

## Cost Optimization

### Cloudflare R2

- No egress fees = predictable costs
- Monitor storage usage in dashboard
- Delete old albums if needed

### Backblaze B2

- Monitor egress (downloads)
- Use Cloudflare CDN for free bandwidth:
  1. Enable Bandwidth Alliance
  2. Point custom domain through Cloudflare
  3. Free egress from B2 to Cloudflare

### General Tips

1. **Optimize image quality:** Lower JPEG_QUALITY = smaller files
2. **Right-size images:** Reduce MEDIUM_WIDTH if photos are too large
3. **Delete unused albums:** Save storage costs
4. **Monitor bandwidth:** Check analytics dashboards

---

## Support & Resources

### Hugo
- Documentation: https://gohugo.io/
- Discourse: https://discourse.gohugo.io/

### Cloudflare R2
- Docs: https://developers.cloudflare.com/r2/
- Community: https://community.cloudflare.com/

### Backblaze B2
- Docs: https://www.backblaze.com/b2/docs/
- Support: https://help.backblaze.com/

### Netlify
- Docs: https://docs.netlify.com/
- Support: https://answers.netlify.com/

---

## Future Enhancements

Potential features to add:

- [ ] Map view with geotagged photos
- [ ] Search/filter by tags, location, camera
- [ ] RSS feed for new albums
- [ ] Comments (via Disqus, utterances, etc.)
- [ ] Social sharing buttons
- [ ] Download album as ZIP
- [ ] Slideshow mode
- [ ] Print-ready layouts
- [ ] Multi-language support

See the code in `layouts/` to implement these features.
