"""Copy the static dashboard to Vercel's CDN directory after a Next export."""

from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "apps" / "web" / "out"
destination = root / "public"
if not (source / "index.html").is_file():
    raise SystemExit("Run the Next.js static build first.")
shutil.copytree(source, destination, dirs_exist_ok=True)
print("Static dashboard prepared for CDN delivery.")
