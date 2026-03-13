#!/usr/bin/env python3
"""
upload_r2.py — Upload images to Cloudflare R2 for Rednote posts.

Usage:
    python upload_r2.py <image_dir> [--slug <post_slug>]

Examples:
    python upload_r2.py ./output --slug ai-weekly-digest
    python upload_r2.py ./output   # auto-generates slug from directory name

Environment variables (required):
    CLOUDFLARE_ACCOUNT_ID          — Cloudflare account ID
    CLOUDFLARE_R2_ACCESS_KEY_ID    — R2 API token access key
    CLOUDFLARE_R2_SECRET_ACCESS_KEY — R2 API token secret key

The script uploads all PNG files in <image_dir> to:
    notion-data/rednote/{slug}/{timestamp}/{filename}

and prints the public URLs for each uploaded image.
"""

import argparse
import datetime
import os
import sys
import glob
import re

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
R2_BUCKET = "notion-data"
R2_PUBLIC_BASE = "https://pub-058d0716e3ab466485a24ef35b0c14f1.r2.dev"


def get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: environment variable {name} is not set.", file=sys.stderr)
        sys.exit(1)
    return val


def build_s3_client():
    """Create a boto3 S3 client pointing at Cloudflare R2."""
    try:
        import boto3
    except ImportError:
        print("boto3 not found — installing…", file=sys.stderr)
        os.system(f"{sys.executable} -m pip install boto3 -q --break-system-packages")
        import boto3

    account_id = get_env("CLOUDFLARE_ACCOUNT_ID")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=get_env("CLOUDFLARE_R2_ACCESS_KEY_ID"),
        aws_secret_access_key=get_env("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def slugify(text: str) -> str:
    """Turn arbitrary text into a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    return text.strip("-") or "post"


def collect_images(directory: str) -> list[str]:
    """Return sorted list of PNG files in *directory*."""
    patterns = [os.path.join(directory, "*.png"), os.path.join(directory, "*.PNG")]
    files: list[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    if not files:
        print(f"ERROR: no PNG files found in {directory}", file=sys.stderr)
        sys.exit(1)
    # Sort so cover comes first, then page_01, page_02…
    return sorted(set(files))


def upload(image_dir: str, slug: str | None = None) -> list[dict]:
    """
    Upload all PNGs in *image_dir* to R2.

    Returns a list of dicts: [{"local": path, "key": r2_key, "url": public_url}, …]
    """
    s3 = build_s3_client()

    if not slug:
        slug = slugify(os.path.basename(os.path.normpath(image_dir)))

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"rednote/{slug}/{timestamp}"

    images = collect_images(image_dir)
    results: list[dict] = []

    for filepath in images:
        filename = os.path.basename(filepath)
        key = f"{prefix}/{filename}"
        public_url = f"{R2_PUBLIC_BASE}/{key}"

        print(f"  Uploading {filename} → {key} …", end=" ", flush=True)
        s3.upload_file(
            filepath,
            R2_BUCKET,
            key,
            ExtraArgs={"ContentType": "image/png"},
        )
        print("✓")

        results.append({"local": filepath, "key": key, "url": public_url})

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Upload Rednote post images to Cloudflare R2"
    )
    parser.add_argument("image_dir", help="Directory containing PNG images to upload")
    parser.add_argument(
        "--slug",
        default=None,
        help="Post slug for the R2 key path (default: derived from directory name)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.image_dir):
        print(f"ERROR: {args.image_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Uploading images from: {args.image_dir}")
    results = upload(args.image_dir, args.slug)

    print(f"\n{'='*60}")
    print(f"Uploaded {len(results)} image(s). Public URLs:\n")
    for r in results:
        print(f"  {r['url']}")
    print(f"\n{'='*60}")

    # Also print Notion markdown embed snippet
    print("\nNotion markdown (copy-paste):\n")
    for r in results:
        name = os.path.splitext(os.path.basename(r["local"]))[0]
        print(f"![{name}]({r['url']})")


if __name__ == "__main__":
    main()
