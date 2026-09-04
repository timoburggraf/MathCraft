# -*- coding: utf-8 -*-
"""Erzeugt die Illustrationen für MathCraft mit Google Nano Banana.

  .venv/bin/python build/make_images.py            # nur fehlende Bilder
  .venv/bin/python build/make_images.py hero logik
  .venv/bin/python build/make_images.py --force geo

Der Schlüssel (GEMINI_API_KEY) kommt aus konfig.py, niemals aus dem Quelltext.
"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # fundus.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # konfig.py

import fundus as F                                                # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "img" / "raw"
MODEL = "gemini-3-pro-image-preview"

# Gemeinsamer Stil. Zielgruppe ist ein achtjähriger Junge, der Aufbau- und
# Abenteuerspiele mag — also Spielgrafik-Ästhetik statt Kinderbuch, aber ohne
# Anleihen bei einer bestimmten Marke. Keine Figuren, keine Logos, keine Schrift.
STYLE = (
    "Polished contemporary game-art illustration with cinematic lighting — bold geometric forms, "
    "clean silhouettes, a sense of scale and adventure, like key art for an exploration game. "
    "Deep midnight-blue and indigo shadows lit by teal, cyan, amber and warm orange accents; "
    "volumetric light shafts, atmospheric haze, crisp highlights, generous depth. "
    "Adventurous and inviting, never sugary. "
    "NOT cartoonish, NOT chibi, NOT babyish, no cute mascots, no comic outlines, no clip-art, "
    "no characters or faces. "
    "ABSOLUTELY NO text, no letters, no words, no digits, no signage, no numerals anywhere."
)

# key -> (Seitenverhältnis, Motiv)
SCENES = {
 "hero": ("16:9",
   "A vast floating archipelago of geometric islands drifting above a sea of clouds at golden hour, "
   "connected by slender light bridges, distant monolithic shapes catching the sun, a glowing path "
   "leading into the depth of the scene. Cinematic, expansive, the opening shot of an adventure."),

 "win": ("16:9",
   "Night over the floating islands with a spectacular burst of fireworks in cyan, gold and orange "
   "above the peaks, light reflecting off crystal surfaces below. Triumphant and cinematic."),

 "levelup": ("16:9",
   "Sunrise breaking over the floating islands, the first shafts of amber light cutting through "
   "drifting mist, a stairway of stone platforms rising toward the light. Epic and uplifting."),

 # ------------------------------- die elf Welten -------------------------------
 "zahl": ("4:3",
   "A canyon of colossal smooth monoliths standing in ordered rows like a forest of pillars, "
   "each one a different height, warm light raking across them at dusk, a narrow path winding "
   "between their bases. Monumental and calm."),

 "plus": ("4:3",
   "A great unfinished bridge of stacked stone blocks spanning a misty chasm, two halves reaching "
   "toward each other, single blocks hovering in mid-air as if about to slot into place, "
   "warm light from below. Constructive, satisfying."),

 "mal": ("4:3",
   "An enormous cavern wall of glowing crystals growing in a perfect grid of rows and columns, "
   "teal and amber light pulsing through the formation, a small platform in the foreground for "
   "scale. Ordered, dazzling."),

 "muster": ("4:3",
   "A vast spiral staircase of repeating geometric tiles seen from above, the pattern rotating and "
   "growing outward, glowing seams between the tiles, mist in the lower turns. Hypnotic, elegant."),

 "geo": ("4:3",
   "Massive polyhedra — a cube, a pyramid, a sphere — floating above a mirror-still lake at blue "
   "hour, each perfectly reflected, thin beams of light connecting their vertices. Serene, "
   "architectural."),

 "logik": ("4:3",
   "A moonlit labyrinth of high stone walls seen at a low angle, glowing gates and levers along the "
   "corridors, one path lit brighter than the rest, fog pooling in the dead ends. Mysterious, "
   "inviting to solve."),

 # V2 (03.09.2026): zwölfte Welt für die Disziplin Algorithmik — Befehle
 # geben, Wege planen, Fehler reparieren. Ein Roboter ohne Gesicht, kein
 # Maskottchen: die Werkstatt ist das Motiv, nicht eine Figur.
 "algo": ("4:3",
   "A vast workshop hall inside a floating island: a glowing grid of luminous floor tiles like a "
   "circuit board stretching into the distance, a small faceless boxy rover machine mid-path on the "
   "tiles, illuminated arrow markers on the floor showing a route around obstacle blocks, "
   "conveyor arms and gears along the walls, teal and amber light. Ordered, inviting, "
   "the feeling of a puzzle waiting to be solved."),
 "komb": ("4:3",
   "A hall of branching portals: a single path splitting into many glowing archways that split "
   "again and again into the distance, each branch a slightly different colour. Vast, tempting."),

 "groess": ("4:3",
   "A colossal ancient balance scale in a desert canyon at sunset, one pan loaded with stone "
   "spheres, a giant sundial and a stretched measuring chain nearby, long shadows. Weighty, "
   "monumental."),

 "daten": ("4:3",
   "A futuristic skyline where the towers are luminous bars of different heights rising from dark "
   "water, their reflections forming a second skyline below, teal and amber glow. Sleek, striking."),

 "geheim": ("4:3",
   "A hidden vault deep in rock: a huge circular stone door engraved with glowing geometric runes, "
   "scattered crystals of unequal size on the floor, a single shaft of light from above. "
   "Secretive, treasure-like."),

 "sach": ("4:3",
   "A bustling night market on a floating island: lantern-strung stalls, crates and barrels, "
   "a laden cart, steam rising from a food stand, warm pools of light against the blue dusk. "
   "Lively and full of stories."),
}


def get_key():
    import konfig
    return konfig.geheim("GEMINI_API_KEY")


def main():
    from google import genai
    from google.genai import types
    from PIL import Image

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv
    todo = args or list(SCENES)

    OUT.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=get_key())
    failed = []

    for name in todo:
        if name not in SCENES:
            print(f"[?]  unbekannt: {name}")
            continue
        dest = OUT / f"{name}.png"
        if dest.exists() and not force:
            print(f"[=]  {name} existiert schon")
            continue
        if dest.exists():
            # --force: das bisherige Bild kommt in den Fundus, bevor das neue
            # darüber geschrieben wird. Ein Bild kostet Geld und lässt sich
            # nicht reproduzieren — dasselbe Motiv kommt nie zweimal gleich.
            ab = F.lege_datei_ab(dest, "bilder")
            if ab:
                print(f"[ar] {name:9s} alte Fassung im Fundus: {ab.name}")

        aspect, motif = SCENES[name]
        prompt = f"{motif}\n\nSTYLE: {STYLE}"
        for attempt in range(1, 4):
            try:
                resp = client.models.generate_content(
                    model=MODEL, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio=aspect),
                    ),
                )
                blob = next((p.inline_data.data for p in resp.candidates[0].content.parts
                             if getattr(p, "inline_data", None)), None)
                if not blob:
                    raise RuntimeError("keine Bilddaten in der Antwort")
                img = Image.open(io.BytesIO(blob))
                img.save(dest)
                print(f"[OK] {name:9s} {img.width}x{img.height}")
                break
            except Exception as e:
                print(f"[!]  {name} Versuch {attempt}: {type(e).__name__}: {str(e)[:130]}")
                time.sleep(3 * attempt)
        else:
            failed.append(name)
        time.sleep(1)

    if failed:
        print("\nFehlgeschlagen:", " ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
