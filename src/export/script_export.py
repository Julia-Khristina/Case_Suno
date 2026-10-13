"""Script export helpers."""
from src.generation.models import Script


def to_person_script(script: Script) -> str:
    lines = []
    for scene in script.scenes:
        lines.append(f"Cena {scene.order} ({scene.start_sec:.1f}s-{scene.end_sec:.1f}s) - {scene.role}")
        lines.append(f"Fala: {scene.spoken}")
        lines.append(f"Texto na tela: {scene.screen_text}")
        lines.append(f"Visual: {scene.visual}")
        lines.append(f"Enquadramento: {scene.framing}")
        lines.append("")
    lines.append(f"Duracao total: {script.total_duration_sec:.1f}s")
    return "\n".join(lines)


def to_ai_prompt(script: Script) -> str:
    scenes = []
    for scene in script.scenes:
        scenes.append(f"Cena {scene.order}: {scene.visual}; fala: {scene.spoken}; tela: {scene.screen_text}")
    return "Video vertical 9:16, ate 60 segundos, paleta vermelha e branca, portugues do Brasil, tom sobrio, sem emojis. " + " ".join(scenes)