"""
Génère des données de test pour SmartAccess MAX.
Crée des visages synthétiques par personne dans data/users/.
"""

import cv2
import numpy as np
import os

USERS = ["Alice", "Bob", "Charlie"]
PHOTOS_PER_USER = 10
OUTPUT_DIR = "data/users"

def make_face(seed, name):
    """Génère un visage synthétique reproductible via une graine."""
    rng = np.random.RandomState(seed)
    img = np.ones((100, 100), dtype=np.uint8) * int(rng.randint(200, 230))

    # Visage (ellipse)
    skin = int(rng.randint(160, 210))
    cv2.ellipse(img, (50, 52), (32, 38), 0, 0, 360, skin, -1)

    # Yeux
    eye_y = 44
    for ex in [36, 64]:
        cv2.ellipse(img, (ex, eye_y), (7, 5), 0, 0, 360, 60, -1)
        cv2.circle(img, (ex, eye_y), 3, 20, -1)

    # Nez
    nose_pts = np.array([[50,52],[45,64],[55,64]], np.int32)
    cv2.polylines(img, [nose_pts], True, 130, 1)

    # Bouche
    cv2.ellipse(img, (50, 72), (10, 5), 0, 0, 180, 100, 2)

    # Cheveux (couleur unique par personne)
    hair_color = int(rng.randint(30, 120))
    cv2.ellipse(img, (50, 30), (32, 22), 0, 180, 360, hair_color, -1)
    cv2.rectangle(img, (18, 18), (82, 36), hair_color, -1)

    # Légère variation pour simuler différentes prises
    noise = rng.randint(-8, 8, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return img

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = 0

    for i, name in enumerate(USERS):
        user_dir = os.path.join(OUTPUT_DIR, name)
        os.makedirs(user_dir, exist_ok=True)

        for j in range(PHOTOS_PER_USER):
            seed = i * 1000 + j
            face = make_face(seed, name)
            path = os.path.join(user_dir, f"{j+1}.jpg")
            cv2.imwrite(path, face)
            total += 1

        print(f"  ✓ {name} — {PHOTOS_PER_USER} photos générées")

    print(f"\nTotal : {total} images dans '{OUTPUT_DIR}/'")
    print("Tu peux maintenant lancer : python gui.py")

if __name__ == "__main__":
    print("Génération des données de test...\n")
    main()
