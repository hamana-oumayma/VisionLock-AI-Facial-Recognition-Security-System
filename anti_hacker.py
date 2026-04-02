attempts = 0
BANNED_ALERT = False  # flag global pour la GUI

def detect_attack(success, banned=False):
    global attempts, BANNED_ALERT

    # Priorité absolue : visage banni détecté
    if banned:
        BANNED_ALERT = True
        return "BANNED_FACE_DETECTED"

    BANNED_ALERT = False
    if not success:
        attempts += 1
    else:
        attempts = 0

    if attempts >= 3:
        return "ATTACK DETECTED - SYSTEM LOCKED"
    return "OK"