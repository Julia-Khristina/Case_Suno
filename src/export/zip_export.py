"""Compatibility alias for carousel ZIP export."""
from src.export.carousel_export import create_carousel_zip

def create_zip(image_paths, output_path):
    return create_carousel_zip(image_paths, output_path)