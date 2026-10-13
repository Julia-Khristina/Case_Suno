"""Carousel export helpers."""
import zipfile
from pathlib import Path


def create_carousel_zip(image_paths: list[Path], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in image_paths:
            archive.write(path, arcname=path.name)
    return output