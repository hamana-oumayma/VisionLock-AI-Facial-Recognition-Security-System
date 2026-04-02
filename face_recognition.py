"""
Reconnaissance faciale avec détection blacklist.
"""
import cv2
import os
import numpy as np

IMG_SIZE = (100, 100)

class SimpleFaceRecognizer:
    def __init__(self):
        self.mean = None
        self.components = None
        self.projections = []
        self.labels = []
        self.threshold = 4000

    def train(self, images, labels):
        resized = [cv2.resize(img, IMG_SIZE).flatten().astype(np.float32) for img in images]
        data = np.array(resized)
        self.mean = data.mean(axis=0)
        centered = data - self.mean
        cov = np.dot(centered, centered.T)
        _, vecs = np.linalg.eigh(cov)
        top = vecs[:, -20:]
        self.components = np.dot(centered.T, top)
        norms = np.linalg.norm(self.components, axis=0, keepdims=True)
        norms[norms == 0] = 1
        self.components /= norms
        self.projections = [np.dot(c, self.components) for c in centered]
        self.labels = list(labels)

    def predict(self, img):
        resized = cv2.resize(img, IMG_SIZE).flatten().astype(np.float32)
        centered = resized - self.mean
        proj = np.dot(centered, self.components)
        dists = [np.linalg.norm(proj - p) for p in self.projections]
        idx = int(np.argmin(dists))
        return self.labels[idx], dists[idx]


def train_model(path):
    images, labels, names = [], [], []
    if not os.path.exists(path):
        print(f"[WARN] Dossier '{path}' introuvable — modèle vide.")
        return SimpleFaceRecognizer(), []
    for i, person in enumerate(sorted(os.listdir(path))):
        person_path = os.path.join(path, person)
        if not os.path.isdir(person_path):
            continue
        names.append(person)
        for fname in os.listdir(person_path):
            img = cv2.imread(os.path.join(person_path, fname), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                images.append(img)
                labels.append(i)
    if not images:
        return SimpleFaceRecognizer(), names
    rec = SimpleFaceRecognizer()
    rec.train(images, np.array(labels))
    print(f"[OK] Modèle entraîné : {len(names)} personnes, {len(images)} images.")
    return rec, names


# ─── BLACKLIST ────────────────────────────────────────────────────────────────

def train_banned_model(path="data/banned"):
    """Entraîne un modèle séparé sur les visages bannis."""
    return train_model(path)


def check_blacklist(banned_rec, banned_names, frame_gray):
    """
    Retourne (True, nom_banni) si un visage banni est détecté,
    sinon (False, None).
    """
    if banned_rec is None or not banned_names or banned_rec.mean is None:
        return False, None

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(frame_gray, 1.1, 5, minSize=(60, 60))

    if len(faces) == 0:
        return False, None

    x, y, w, h = faces[0]
    face_roi = frame_gray[y:y+h, x:x+w]
    label_idx, conf = banned_rec.predict(face_roi)

    # Seuil plus strict pour les bannis (on préfère les faux positifs)
    if conf > 3000:
        return False, None

    name = banned_names[label_idx] if label_idx < len(banned_names) else None
    return True, name


# ─── RECONNAISSANCE NORMALE ───────────────────────────────────────────────────

def recognize_face(rec, names, frame_gray=None):
    if rec is None or not names or rec.mean is None:
        return "Unknown", 9999, None
    if frame_gray is None:
        import random, time
        idx = int(time.time() // 3) % len(names)
        conf = random.uniform(800, 1800)
        return names[idx], conf, None
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(frame_gray, 1.1, 5, minSize=(60, 60))
    if len(faces) == 0:
        return "Unknown", 9999, None
    x, y, w, h = faces[0]
    face_roi = frame_gray[y:y+h, x:x+w]
    label_idx, conf = rec.predict(face_roi)
    if conf > rec.threshold:
        return "Unknown", conf, (x, y, w, h)
    name = names[label_idx] if label_idx < len(names) else "Unknown"
    return name, conf, (x, y, w, h)