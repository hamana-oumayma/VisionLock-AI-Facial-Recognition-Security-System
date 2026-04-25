
from logging import root
import sys
import cv2
import sqlite3
import datetime
import random
import os
import shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QGraphicsDropShadowEffect,
    QProgressBar, QSpacerItem, QInputDialog, QMessageBox, QFileDialog
)
from PyQt5.QtGui import (
    QImage, QPixmap, QFont, QColor, QPalette, QLinearGradient,
    QBrush, QPainter, QPen
)
from PyQt5.QtCore import (
    QTimer, Qt, QSize, QUrl
)
from PyQt5.QtGui import QDesktopServices

from face_recognition import train_model, train_banned_model, recognize_face, check_blacklist
from database import connect, init_db
from anti_hacker import detect_attack
from export_pdf import export_logs

BG_DEEP  = "#050a0f"
BG_PANEL = "#0b1520"
BG_CARD  = "#0f1e2e"
ACCENT   = "#00e5ff"
ACCENT2  = "#0066ff"
GREEN    = "#00ff9d"
RED      = "#ff2d55"
YELLOW   = "#ffd60a"
ORANGE   = "#ff6b2b"
TEXT_PRI = "#e8f4f8"
TEXT_SEC = "#5a7a8a"
BORDER   = "#1a3a4a"


def card_style(extra=""):
    return f"background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;{extra}"


def glow(color=ACCENT, blur=20, strength=0.5):
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(blur)
    c = QColor(color)
    c.setAlphaF(strength)
    s.setColor(c)
    s.setOffset(0, 0)
    return s


# ── NAV BUTTON ────────────────────────────────────────────────────────────────

class NavButton(QPushButton):
    def __init__(self, icon_text, label, parent=None):
        super().__init__(parent)
        self.icon_text  = icon_text
        self.label_text = label
        self._active    = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._refresh()

    def setActive(self, active):
        self._active = active
        self._refresh()

    def _refresh(self):
        if self._active:
            bg    = f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT2}55,stop:1 transparent);"
            bl    = f"border-left:3px solid {ACCENT};"
            color = TEXT_PRI
            fw    = "700"
        else:
            bg    = "background:transparent;"
            bl    = "border-left:3px solid transparent;"
            color = TEXT_SEC
            fw    = "400"
        self.setStyleSheet(f"""
            QPushButton {{{bg}{bl}border-right:none;border-top:none;border-bottom:none;
            color:{color};font-family:'Consolas',monospace;font-size:13px;font-weight:{fw};
            text-align:left;padding-left:20px;border-radius:0px;}}
            QPushButton:hover{{background:{BG_PANEL};color:{TEXT_PRI};}}
        """)
        self.setText(f"  {self.icon_text}   {self.label_text}")


# ── STAT CARD ─────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    def __init__(self, icon, title, value, color=ACCENT, parent=None):
        super().__init__(parent)
        self.setStyleSheet(card_style())
        self.setFixedHeight(110)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)

        top = QHBoxLayout()
        il  = QLabel(icon)
        il.setStyleSheet(f"color:{color};font-size:22px;background:transparent;border:none;")
        top.addWidget(il)
        top.addStretch()

        tl = QLabel(title.upper())
        tl.setStyleSheet(
            f"color:{TEXT_SEC};font-size:10px;letter-spacing:2px;"
            f"background:transparent;border:none;"
        )
        self.vl = QLabel(str(value))
        self.vl.setStyleSheet(
            f"color:{color};font-size:28px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        lay.addLayout(top)
        lay.addWidget(tl)
        lay.addWidget(self.vl)
        self.setGraphicsEffect(glow(color, 15, 0.3))

    def set_value(self, v):
        self.vl.setText(str(v))


# ── CAMERA PAGE ───────────────────────────────────────────────────────────────

class CameraPage(QWidget):
    def __init__(self, recognizer, names, banned_rec=None, banned_names=None, parent=None):
        super().__init__(parent)
        self.recognizer        = recognizer
        self.names             = names
        self.banned_rec        = banned_rec
        self.banned_names      = banned_names or []
        self.cap               = None
        self.timer             = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self._fail_count       = 0
        self._activity_log     = []
        self._last_logged_status = None
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(12)

        # Feed frame
        feed_frame = QFrame()
        feed_frame.setStyleSheet(
            f"background:#000;border:1px solid {ACCENT}44;border-radius:12px;"
        )
        feed_frame.setGraphicsEffect(glow(ACCENT, 30, 0.25))
        fl = QVBoxLayout(feed_frame)
        fl.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background:{BG_PANEL};border-radius:12px 12px 0 0;"
            f"border-bottom:1px solid {BORDER};"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        for clr in [RED, YELLOW, GREEN]:
            d = QLabel("●")
            d.setStyleSheet(f"color:{clr};font-size:10px;background:transparent;border:none;")
            hl.addWidget(d)
        hl.addStretch()
        cl = QLabel("LIVE FEED  —  CAM #01")
        cl.setStyleSheet(
            f"color:{TEXT_SEC};font-size:11px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        hl.addWidget(cl)
        hl.addStretch()
        fl.addWidget(hdr)

        self._placeholder = QLabel("[ NO SIGNAL ]")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setMinimumHeight(340)
        self._placeholder.setStyleSheet(
            f"color:{TEXT_SEC};font-size:14px;font-family:'Consolas',monospace;"
            f"letter-spacing:4px;background:#000;border:none;"
        )
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(480, 340)
        self.video_label.setStyleSheet("background:#000;border:none;")
        self.video_label.hide()
        fl.addWidget(self._placeholder)
        fl.addWidget(self.video_label)
        left.addWidget(feed_frame, stretch=1)

        # Control buttons
        ctrl = QHBoxLayout()
        ctrl.setSpacing(12)

        self.btn_start = QPushButton("▶  START CAMERA")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setFixedHeight(44)
        self.btn_start.setStyleSheet(f"""
            QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT2},stop:1 {ACCENT});
            color:#000;font-family:'Consolas',monospace;font-size:13px;font-weight:700;
            border-radius:8px;border:none;letter-spacing:1px;}}
            QPushButton:hover{{background:{ACCENT};}}
        """)
        self.btn_start.clicked.connect(self._toggle_cam)
        self.btn_start.setGraphicsEffect(glow(ACCENT, 18, 0.5))

        self.btn_export = QPushButton("⬇  EXPORT PDF")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setFixedHeight(44)
        self.btn_export.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{ACCENT};font-family:'Consolas',monospace;
            font-size:13px;font-weight:600;border-radius:8px;border:1px solid {ACCENT}55;letter-spacing:1px;}}
            QPushButton:hover{{background:{ACCENT}22;border-color:{ACCENT};}}
        """)
        self.btn_export.clicked.connect(self._do_export)

        self.btn_download = QPushButton("💾 DOWNLOAD PDF")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.setFixedHeight(44)
        self.btn_download.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{GREEN};
            font-family:'Consolas',monospace;font-size:13px;font-weight:600;
            border-radius:8px;border:1px solid {GREEN}55;letter-spacing:1px;}}
            QPushButton:hover{{background:{GREEN}22;border-color:{GREEN};}}
        """)
        self.btn_download.clicked.connect(self._download_pdf)

        ctrl.addWidget(self.btn_start,    stretch=2)
        ctrl.addWidget(self.btn_export,   stretch=1)
        ctrl.addWidget(self.btn_download, stretch=1)
        left.addLayout(ctrl)
        root.addLayout(left, stretch=3)

        # Right panel
        right = QVBoxLayout()
        right.setSpacing(14)

        # Identity card
        id_card = QFrame()
        id_card.setStyleSheet(card_style())
        id_card.setFixedHeight(200)
        idl = QVBoxLayout(id_card)
        idl.setContentsMargins(20, 16, 20, 16)
        idl.setSpacing(8)

        tit = QLabel("IDENTITY")
        tit.setStyleSheet(
            f"color:{TEXT_SEC};font-size:10px;letter-spacing:3px;"
            f"background:transparent;border:none;"
        )
        self.lbl_name = QLabel("UNKNOWN")
        self.lbl_name.setStyleSheet(
            f"color:{ACCENT};font-size:26px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        self.lbl_conf = QLabel("Confidence: —")
        self.lbl_conf.setStyleSheet(
            f"color:{TEXT_SEC};font-size:12px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setFixedHeight(6)
        self.conf_bar.setTextVisible(False)
        self.conf_bar.setStyleSheet(f"""
            QProgressBar{{background:{BORDER};border-radius:3px;border:none;}}
            QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT2},stop:1 {ACCENT});border-radius:3px;}}
        """)
        self.status_badge = QLabel("● IDLE")
        self.status_badge.setFixedWidth(130)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setStyleSheet(
            f"background:{TEXT_SEC}22;color:{TEXT_SEC};border:1px solid {TEXT_SEC}33;"
            f"border-radius:4px;padding:2px 8px;font-size:11px;"
            f"font-family:'Consolas',monospace;font-weight:600;"
        )
        idl.addWidget(tit)
        idl.addWidget(self.lbl_name)
        idl.addWidget(self.lbl_conf)
        idl.addWidget(self.conf_bar)
        idl.addStretch()
        idl.addWidget(self.status_badge)
        right.addWidget(id_card)

        # Threat monitor card
        thr_card = QFrame()
        thr_card.setStyleSheet(card_style())
        tl = QVBoxLayout(thr_card)
        tl.setContentsMargins(20, 16, 20, 16)
        tl.setSpacing(10)

        tt = QLabel("THREAT MONITOR")
        tt.setStyleSheet(
            f"color:{TEXT_SEC};font-size:10px;letter-spacing:3px;"
            f"background:transparent;border:none;"
        )
        self.threat_lbl = QLabel("● SYSTEM SECURE")
        self.threat_lbl.setStyleSheet(
            f"color:{GREEN};font-size:14px;font-weight:600;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        self.attempt_lbl = QLabel("Failed attempts: 0 / 3")
        self.attempt_lbl.setStyleSheet(
            f"color:{TEXT_SEC};font-size:12px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        self.banned_indicator = QLabel()
        n_banned = len(self.banned_names)
        self.banned_indicator.setText(f"⛔  BLACKLIST : {n_banned} BANNI(S)")
        color_ind = RED if n_banned > 0 else TEXT_SEC
        self.banned_indicator.setStyleSheet(
            f"color:{color_ind};font-size:11px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        tl.addWidget(tt)
        tl.addWidget(self.threat_lbl)
        tl.addWidget(self.attempt_lbl)
        tl.addWidget(self.banned_indicator)
        right.addWidget(thr_card)

        # Recent activity card
        act_card = QFrame()
        act_card.setStyleSheet(card_style())
        al = QVBoxLayout(act_card)
        al.setContentsMargins(20, 16, 20, 16)
        al.setSpacing(8)

        at = QLabel("RECENT ACTIVITY")
        at.setStyleSheet(
            f"color:{TEXT_SEC};font-size:10px;letter-spacing:3px;"
            f"background:transparent;border:none;"
        )
        al.addWidget(at)

        self.activity_items = []
        for _ in range(4):
            item = QLabel("—")
            item.setStyleSheet(
                f"color:{TEXT_SEC};font-size:11px;font-family:'Consolas',monospace;"
                f"background:transparent;border:none;padding:4px 0;"
            )
            al.addWidget(item)
            self.activity_items.append(item)

        right.addWidget(act_card)
        right.addStretch()
        root.addLayout(right, stretch=1)

    # ── Camera toggle ──────────────────────────────────────────────────────────

    def _toggle_cam(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            self.timer.start(30)
            self.btn_start.setText("■  STOP CAMERA")
            self._placeholder.hide()
            self.video_label.show()
            self._set_badge("● SCANNING", YELLOW)
        else:
            self.timer.stop()
            self.cap.release()
            self.cap = None
            self.btn_start.setText("▶  START CAMERA")
            self.video_label.hide()
            self._placeholder.show()
            self._set_badge("● IDLE", TEXT_SEC)

    def _set_badge(self, text, color):
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"background:{color}22;color:{color};border:1px solid {color}55;"
            f"border-radius:4px;padding:2px 8px;font-size:11px;"
            f"font-family:'Consolas',monospace;font-weight:600;"
        )

    # ── Main frame update ──────────────────────────────────────────────────────

    def _update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Blacklist check (priority)
        is_banned, banned_name = check_blacklist(self.banned_rec, self.banned_names, gray)

        if is_banned:
            display_name = (banned_name or "BANNI").upper()
            self.lbl_name.setText(f"⚠ {display_name}")
            self.lbl_name.setStyleSheet(
                f"color:{RED};font-size:22px;font-weight:700;"
                f"font-family:'Consolas',monospace;background:transparent;border:none;"
            )
            self.lbl_conf.setText("BLACKLISTED IDENTITY")
            self.lbl_conf.setStyleSheet(
                f"color:{RED};font-size:12px;font-family:'Consolas',monospace;"
                f"background:transparent;border:none;"
            )
            self.conf_bar.setValue(100)
            self.conf_bar.setStyleSheet(f"""
                QProgressBar{{background:{BORDER};border-radius:3px;border:none;}}
                QProgressBar::chunk{{background:{RED};border-radius:3px;}}
            """)
            self._set_badge("⛔ BANNI !", RED)

            self.threat_lbl.setText("⛔  VISAGE BANNI DÉTECTÉ !")
            self.threat_lbl.setStyleSheet(
                f"color:{RED};font-size:13px;font-weight:700;"
                f"font-family:'Consolas',monospace;background:transparent;border:none;"
            )

            log_key = f"BANNED_{banned_name}"
            if log_key != self._last_logged_status:
                self._last_logged_status = log_key
                try:
                    ts_full = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn = connect()
                    conn.execute(
                        "INSERT INTO logs (user, status, watermark) VALUES (?, ?, ?)",
                        (banned_name or "BANNI", "BANNED", ts_full)
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"DB banned insert error: {e}")

            cv2.putText(frame, f"BANNED: {display_name}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 45, 85), 2)
            cv2.putText(frame, "!! BLACKLIST ALERT !!", (20, 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 45, 85), 2)

            ts    = datetime.datetime.now().strftime("%H:%M:%S")
            entry = f"{ts}  {display_name[:12]:<12}  ⛔ BANNI"
            self._push_activity(entry, RED)
            self._render_frame(frame)
            return

        # Normal recognition
        name, conf, bbox = recognize_face(self.recognizer, self.names, gray)
        success = (name != "Unknown")
        status  = detect_attack(success)

        self.lbl_name.setText(name.upper())
        conf_int = max(0, min(100, int(100 - conf) if conf else 0))
        self.lbl_conf.setText(f"Confidence: {conf_int}%")
        self.lbl_conf.setStyleSheet(
            f"color:{TEXT_SEC};font-size:12px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        self.conf_bar.setValue(conf_int)
        self.conf_bar.setStyleSheet(f"""
            QProgressBar{{background:{BORDER};border-radius:3px;border:none;}}
            QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT2},stop:1 {ACCENT});border-radius:3px;}}
        """)

        color      = GREEN if success else RED
        badge_text = "● GRANTED" if success else "● DENIED"
        self.lbl_name.setStyleSheet(
            f"color:{color};font-size:26px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        self._set_badge(badge_text, color)

        if not success:
            self._fail_count += 1
        else:
            self._fail_count = 0

        log_status = "GRANTED" if success else "DENIED"
        if log_status != self._last_logged_status:
            self._last_logged_status = log_status
            try:
                ts_full = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = connect()
                conn.execute(
                    "INSERT INTO logs (user, status, watermark) VALUES (?, ?, ?)",
                    (name, log_status, ts_full)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"DB insert error: {e}")

        if "ATTACK" in status:
            self.threat_lbl.setText("⚠  ATTACK DETECTED")
            self.threat_lbl.setStyleSheet(
                f"color:{RED};font-size:14px;font-weight:600;"
                f"font-family:'Consolas',monospace;background:transparent;border:none;"
            )
        else:
            self.threat_lbl.setText("● SYSTEM SECURE")
            self.threat_lbl.setStyleSheet(
                f"color:{GREEN};font-size:14px;font-weight:600;"
                f"font-family:'Consolas',monospace;background:transparent;border:none;"
            )
        self.attempt_lbl.setText(f"Failed attempts: {self._fail_count} / 3")

        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"{ts}  {name.upper()[:12]:<12}  {'✓ GRANTED' if success else '✗ DENIED'}"
        self._push_activity(entry, color)

        clr_cv = (0, 255, 157) if success else (255, 45, 85)
        cv2.putText(frame, name, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, clr_cv, 2)
        cv2.putText(frame, "ACCESS GRANTED" if success else "ACCESS DENIED",
                    (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.55, clr_cv, 1)
        self._render_frame(frame)

    def _push_activity(self, entry, color):
        self._activity_log.insert(0, (entry, color))
        self._activity_log = self._activity_log[:4]
        for i, item in enumerate(self.activity_items):
            if i < len(self._activity_log):
                txt, clr = self._activity_log[i]
                item.setText(txt)
                item.setStyleSheet(
                    f"color:{clr};font-size:11px;font-family:'Consolas',monospace;"
                    f"background:transparent;border:none;padding:4px 0;"
                )
            else:
                item.setText("—")

    def _render_frame(self, frame):
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img     = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.video_label.setPixmap(
            QPixmap.fromImage(img).scaled(
                self.video_label.width(), self.video_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def _do_export(self):
        try:
            export_logs()
            pdf_path = os.path.abspath("logs_report.pdf")
            if not os.path.exists(pdf_path):
                QMessageBox.warning(self, "Erreur", "Le PDF n'a pas pu être généré.")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._push_activity(f"{ts}  PDF exporté", ACCENT)
        except Exception as e:
            QMessageBox.warning(self, "Erreur export", str(e))
            print(f"Export error: {e}")

    def _download_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer PDF",
            "logs_report.pdf",
            "PDF Files (*.pdf)"
        )
        if not path:
            return

        if not os.path.exists("logs_report.pdf"):
            QMessageBox.warning(self, "Erreur", "Le fichier PDF n'existe pas !")
            return

        try:
            shutil.copy("logs_report.pdf", path)
            QMessageBox.information(self, "Succès", "PDF téléchargé avec succès !")
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))


# ── LOGS PAGE ─────────────────────────────────────────────────────────────────

class LogsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        self.stat_total   = StatCard("📋", "Total Logs", "—", ACCENT)
        self.stat_granted = StatCard("✅", "Granted",    "—", GREEN)
        self.stat_denied  = StatCard("🚫", "Denied",     "—", RED)
        self.stat_banned  = StatCard("⛔", "Banned",     "—", ORANGE)

        sr = QHBoxLayout()
        sr.setSpacing(14)
        for c in [self.stat_total, self.stat_granted, self.stat_denied, self.stat_banned]:
            sr.addWidget(c)
        root.addLayout(sr)

        tc = QFrame()
        tc.setStyleSheet(card_style())
        tl = QVBoxLayout(tc)
        tl.setContentsMargins(20, 16, 20, 16)
        tl.setSpacing(12)

        hdr = QHBoxLayout()
        t   = QLabel("ACCESS LOGS")
        t.setStyleSheet(
            f"color:{TEXT_PRI};font-size:14px;font-weight:600;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        self.btn_refresh = QPushButton("↻  REFRESH")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(110, 32)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{ACCENT};border:1px solid {ACCENT}55;
            border-radius:6px;font-family:'Consolas',monospace;font-size:12px;}}
            QPushButton:hover{{background:{ACCENT}22;}}
        """)
        self.btn_refresh.clicked.connect(self.load_data)
        hdr.addWidget(t)
        hdr.addStretch()
        hdr.addWidget(self.btn_refresh)
        tl.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "USER", "STATUS", "WATERMARK"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget{{background:transparent;color:{TEXT_PRI};font-family:'Consolas',monospace;
            font-size:12px;border:none;outline:none;}}
            QTableWidget::item{{padding:10px 12px;border-bottom:1px solid {BORDER};}}
            QTableWidget::item:selected{{background:{ACCENT}22;color:{ACCENT};}}
            QTableWidget::item:alternate{{background:{BG_PANEL};}}
            QHeaderView::section{{background:{BG_PANEL};color:{TEXT_SEC};font-family:'Consolas',monospace;
            font-size:10px;letter-spacing:2px;padding:10px 12px;border:none;border-bottom:1px solid {BORDER};}}
            QScrollBar:vertical{{background:{BG_PANEL};width:6px;border-radius:3px;}}
            QScrollBar::handle:vertical{{background:{ACCENT}44;border-radius:3px;}}
        """)
        tl.addWidget(self.table)
        root.addWidget(tc, stretch=1)
        self.load_data()

    def load_data(self):
        try:
            conn = connect()
            cur  = conn.cursor()
            cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50")
            rows = cur.fetchall()
            conn.close()

            self.table.setRowCount(len(rows))
            granted = denied = banned = 0
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    item = QTableWidgetItem(str(val) if val else "—")
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    if c == 2:
                        v = str(val).upper()
                        if "GRANT" in v:
                            item.setForeground(QColor(GREEN))
                            granted += 1
                        elif "BANNED" in v:
                            item.setForeground(QColor(ORANGE))
                            banned += 1
                        elif "DENY" in v or "FAIL" in v:
                            item.setForeground(QColor(RED))
                            denied += 1
                    self.table.setItem(r, c, item)
                    self.table.setRowHeight(r, 42)

            self.stat_total.set_value(len(rows))
            self.stat_granted.set_value(granted)
            self.stat_denied.set_value(denied)
            self.stat_banned.set_value(banned)
        except Exception as e:
            print(f"DB error: {e}")


# ── BLACKLIST PAGE ────────────────────────────────────────────────────────────

class BlacklistPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        self.stat_total  = StatCard("⛔", "Total Bannis",         "—", RED)
        self.stat_alerts = StatCard("🚨", "Alertes Déclenchées", "—", ORANGE)
        sr = QHBoxLayout()
        sr.setSpacing(14)
        sr.addWidget(self.stat_total)
        sr.addWidget(self.stat_alerts)
        sr.addStretch()
        root.addLayout(sr)

        mc = QFrame()
        mc.setStyleSheet(card_style())
        ml = QVBoxLayout(mc)
        ml.setContentsMargins(20, 16, 20, 16)
        ml.setSpacing(12)

        hdr = QHBoxLayout()
        t   = QLabel("BLACKLIST — VISAGES BANNIS")
        t.setStyleSheet(
            f"color:{RED};font-size:14px;font-weight:600;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;letter-spacing:1px;"
        )

        self.btn_add = QPushButton("＋  AJOUTER BANNI")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setFixedHeight(32)
        self.btn_add.setStyleSheet(f"""
            QPushButton{{background:{RED}22;color:{RED};border:1px solid {RED}55;border-radius:6px;
            font-family:'Consolas',monospace;font-size:12px;padding:0 12px;}}
            QPushButton:hover{{background:{RED}44;}}
        """)
        self.btn_add.clicked.connect(self._add_banned)

        self.btn_refresh2 = QPushButton("↻  REFRESH")
        self.btn_refresh2.setCursor(Qt.PointingHandCursor)
        self.btn_refresh2.setFixedSize(110, 32)
        self.btn_refresh2.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{ACCENT};border:1px solid {ACCENT}55;
            border-radius:6px;font-family:'Consolas',monospace;font-size:12px;}}
            QPushButton:hover{{background:{ACCENT}22;}}
        """)
        self.btn_refresh2.clicked.connect(self.load_data)

        hdr.addWidget(t)
        hdr.addStretch()
        hdr.addWidget(self.btn_add)
        hdr.addWidget(self.btn_refresh2)
        ml.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "NOM", "RAISON", "DATE AJOUT"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget{{background:transparent;color:{TEXT_PRI};font-family:'Consolas',monospace;
            font-size:12px;border:none;outline:none;}}
            QTableWidget::item{{padding:10px 12px;border-bottom:1px solid {BORDER};}}
            QTableWidget::item:selected{{background:{RED}22;color:{RED};}}
            QTableWidget::item:alternate{{background:{BG_PANEL};}}
            QHeaderView::section{{background:{BG_PANEL};color:{TEXT_SEC};font-family:'Consolas',monospace;
            font-size:10px;letter-spacing:2px;padding:10px 12px;border:none;border-bottom:1px solid {BORDER};}}
            QScrollBar:vertical{{background:{BG_PANEL};width:6px;border-radius:3px;}}
            QScrollBar::handle:vertical{{background:{RED}44;border-radius:3px;}}
        """)
        ml.addWidget(self.table)

        btn_del = QPushButton("🗑  SUPPRIMER LA SÉLECTION")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setFixedHeight(36)
        btn_del.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{RED};border:1px solid {RED}33;border-radius:6px;
            font-family:'Consolas',monospace;font-size:12px;}}
            QPushButton:hover{{background:{RED}22;}}
        """)
        btn_del.clicked.connect(self._delete_selected)
        ml.addWidget(btn_del)

        root.addWidget(mc, stretch=1)

        info = QFrame()
        info.setStyleSheet(card_style(f"border-color:{RED}33;"))
        il   = QHBoxLayout(info)
        il.setContentsMargins(16, 12, 16, 12)
        info_txt = QLabel(
            "ℹ  Ajoute les photos du visage banni dans  data/banned/<NOM>/  "
            "(ex: data/banned/Intrus1/1.jpg)  "
            "puis redémarre l'application pour que le modèle se réentraîne."
        )
        info_txt.setWordWrap(True)
        info_txt.setStyleSheet(
            f"color:{TEXT_SEC};font-size:11px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        il.addWidget(info_txt)
        root.addWidget(info)

        self.load_data()

    def load_data(self):
        try:
            conn = connect()
            cur  = conn.cursor()
            cur.execute("SELECT * FROM blacklist ORDER BY id DESC")
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM logs WHERE status='BANNED'")
            nb_alerts = cur.fetchone()[0]
            conn.close()

            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    item = QTableWidgetItem(str(val) if val else "—")
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    if c == 1:
                        item.setForeground(QColor(RED))
                    self.table.setItem(r, c, item)
                    self.table.setRowHeight(r, 42)

            self.stat_total.set_value(len(rows))
            self.stat_alerts.set_value(nb_alerts)
        except Exception as e:
            print(f"Blacklist DB error: {e}")

    def _add_banned(self):
        name, ok = QInputDialog.getText(self, "Ajouter un banni", "Nom du banni :")
        if not ok or not name.strip():
            return
        reason, ok2 = QInputDialog.getText(self, "Raison", "Raison du bannissement :")
        if not ok2:
            reason = "Non spécifiée"
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = connect()
            conn.execute(
                "INSERT OR IGNORE INTO blacklist (name, reason, added_at) VALUES (?, ?, ?)",
                (name.strip(), reason.strip() or "Non spécifiée", ts)
            )
            conn.commit()
            conn.close()
            QMessageBox.information(
                self, "Banni ajouté",
                f"'{name}' ajouté à la blacklist.\n\n"
                f"N'oublie pas de placer les photos dans :\n"
                f"data/banned/{name}/1.jpg, 2.jpg ...\n\n"
                f"Puis redémarre l'application."
            )
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))

    def _delete_selected(self):
        rows = self.table.selectedItems()
        if not rows:
            return
        row_idx   = self.table.currentRow()
        id_item   = self.table.item(row_idx, 0)
        name_item = self.table.item(row_idx, 1)
        if not id_item:
            return
        reply = QMessageBox.question(
            self, "Confirmer",
            f"Supprimer '{name_item.text() if name_item else '?'}' de la blacklist ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                conn = connect()
                conn.execute("DELETE FROM blacklist WHERE id=?", (int(id_item.text()),))
                conn.commit()
                conn.close()
                self.load_data()
            except Exception as e:
                QMessageBox.warning(self, "Erreur", str(e))


# ── MAIN WINDOW ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setWindowTitle("VisionLock")
        self.setMinimumSize(1200, 700)
        self.setStyleSheet(f"background:{BG_DEEP};color:{TEXT_PRI};")

        try:
            self.recognizer, self.names = train_model("data/users")
        except Exception as e:
            print(f"[WARN] train_model: {e}")
            self.recognizer, self.names = None, []

        try:
            self.banned_rec, self.banned_names = train_banned_model("data/banned")
            print(f"[OK] Blacklist chargée : {len(self.banned_names)} banni(s).")
        except Exception as e:
            print(f"[WARN] train_banned_model: {e}")
            self.banned_rec, self.banned_names = None, []

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QHBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # Sidebar
        sb = QFrame()
        sb.setFixedWidth(220)
        sb.setStyleSheet(f"background:{BG_PANEL};border-right:1px solid {BORDER};")
        sbl = QVBoxLayout(sb)
        sbl.setContentsMargins(0, 0, 0, 0)
        sbl.setSpacing(0)

        lf = QFrame()
        lf.setFixedHeight(80)
        lf.setStyleSheet(f"background:{BG_PANEL};border-bottom:1px solid {BORDER};")
        ll = QVBoxLayout(lf)
        ll.setContentsMargins(20, 0, 20, 0)
        lt = QLabel("VisionLock")
        lt.setStyleSheet(
            f"color:{ACCENT};font-size:18px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;letter-spacing:1px;"
        )
        lb = QLabel("AI SECURITY ")
        lb.setStyleSheet(
            f"color:{TEXT_SEC};font-size:9px;font-family:'Consolas',monospace;"
            f"letter-spacing:3px;background:transparent;border:none;"
        )
        ll.addStretch()
        ll.addWidget(lt)
        ll.addWidget(lb)
        ll.addStretch()
        sbl.addWidget(lf)
        sbl.addSpacing(16)

        nl = QLabel("NAVIGATION")
        nl.setStyleSheet(
            f"color:{TEXT_SEC};font-size:9px;letter-spacing:3px;"
            f"padding-left:20px;background:transparent;border:none;"
        )
        sbl.addWidget(nl)
        sbl.addSpacing(6)

        self.nav_camera    = NavButton("📷", "Camera / Scan")
        self.nav_logs      = NavButton("📋", "Access Logs")
        self.nav_blacklist = NavButton("⛔", "Blacklist")

        self.nav_camera.clicked.connect(lambda: self._switch(0))
        self.nav_logs.clicked.connect(lambda: self._switch(1))
        self.nav_blacklist.clicked.connect(lambda: self._switch(2))

        sbl.addWidget(self.nav_camera)
        sbl.addWidget(self.nav_logs)
        sbl.addWidget(self.nav_blacklist)
        sbl.addStretch()

        if self.banned_names:
            bl_badge = QFrame()
            bl_badge.setStyleSheet(
                f"background:{RED}18;border:1px solid {RED}33;"
                f"border-radius:6px;margin:8px 12px;"
            )
            bbl = QVBoxLayout(bl_badge)
            bbl.setContentsMargins(10, 8, 10, 8)
            bbl.setSpacing(2)
            bl_t = QLabel(f"⛔  {len(self.banned_names)} BANNI(S)")
            bl_t.setStyleSheet(
                f"color:{RED};font-size:10px;font-weight:700;"
                f"font-family:'Consolas',monospace;background:transparent;border:none;"
            )
            bl_s = QLabel("Surveillance active")
            bl_s.setStyleSheet(
                f"color:{RED}99;font-size:9px;font-family:'Consolas',monospace;"
                f"background:transparent;border:none;"
            )
            bbl.addWidget(bl_t)
            bbl.addWidget(bl_s)
            sbl.addWidget(bl_badge)

        sf = QFrame()
        sf.setFixedHeight(56)
        sf.setStyleSheet(f"border-top:1px solid {BORDER};background:{BG_PANEL};")
        stl = QHBoxLayout(sf)
        stl.setContentsMargins(20, 0, 20, 0)
        dot     = QLabel("●")
        dot.setStyleSheet(f"color:{GREEN};font-size:10px;background:transparent;border:none;")
        sys_lbl = QLabel("SYSTEM ONLINE")
        sys_lbl.setStyleSheet(
            f"color:{TEXT_SEC};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        stl.addWidget(dot)
        stl.addWidget(sys_lbl)
        stl.addStretch()
        sbl.addWidget(sf)
        ml.addWidget(sb)

        # Content area
        content = QFrame()
        content.setStyleSheet(f"background:{BG_DEEP};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        topbar = QFrame()
        topbar.setFixedHeight(56)
        topbar.setStyleSheet(f"background:{BG_PANEL};border-bottom:1px solid {BORDER};")
        tbl = QHBoxLayout(topbar)
        tbl.setContentsMargins(24, 0, 24, 0)

        self.page_title = QLabel("CAMERA / SCAN")
        self.page_title.setStyleSheet(
            f"color:{TEXT_PRI};font-size:14px;font-weight:600;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;letter-spacing:2px;"
        )
        now  = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M")
        tl2  = QLabel(now)
        tl2.setStyleSheet(
            f"color:{TEXT_SEC};font-size:11px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        tbl.addWidget(self.page_title)
        tbl.addStretch()
        tbl.addWidget(tl2)
        cl.addWidget(topbar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background:transparent;")

        self.cam_page       = CameraPage(
            self.recognizer, self.names,
            banned_rec=self.banned_rec,
            banned_names=self.banned_names
        )
        self.logs_page      = LogsPage()
        self.blacklist_page = BlacklistPage()

        self.stack.addWidget(self.cam_page)
        self.stack.addWidget(self.logs_page)
        self.stack.addWidget(self.blacklist_page)
        cl.addWidget(self.stack, stretch=1)
        ml.addWidget(content, stretch=1)
        self._switch(0)

    def _switch(self, idx):
        self.stack.setCurrentIndex(idx)
        self.nav_camera.setActive(idx == 0)
        self.nav_logs.setActive(idx == 1)
        self.nav_blacklist.setActive(idx == 2)
        titles = ["CAMERA / SCAN", "ACCESS LOGS", "BLACKLIST"]
        self.page_title.setText(titles[idx])
        if idx == 1:
            self.logs_page.load_data()
        if idx == 2:
            self.blacklist_page.load_data()


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(BG_DEEP))
    palette.setColor(QPalette.WindowText,      QColor(TEXT_PRI))
    palette.setColor(QPalette.Base,            QColor(BG_CARD))
    palette.setColor(QPalette.AlternateBase,   QColor(BG_PANEL))
    palette.setColor(QPalette.Text,            QColor(TEXT_PRI))
    palette.setColor(QPalette.Button,          QColor(BG_PANEL))
    palette.setColor(QPalette.ButtonText,      QColor(TEXT_PRI))
    palette.setColor(QPalette.Highlight,       QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#000"))
    app.setPalette(palette)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())