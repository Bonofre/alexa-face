import cv2
import smtplib
import os
import signal
import sys
import time
import logging
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

def _cargar_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_cargar_env()

SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = os.environ["SMTP_USER"]
SMTP_PASS     = os.environ["SMTP_PASS"]
EMAIL_TO      = os.environ["EMAIL_TO"]
_cam_env      = os.environ.get("CAMERA_SOURCE", "2")
CAMERA_SOURCE = int(_cam_env) if _cam_env.isdigit() else _cam_env
ESP_IP        = os.environ.get("ESP_IP", "")
COOLDOWN      = 30    # segundos entre alertas
AREA_MIN      = 5000  # px² mínimos para considerar movimiento
CLIP_DURATION = 15    # segundos de grabación

_running = True

def _handle_signal(_sig, _frame):
    global _running
    log.info("Señal recibida, cerrando...")
    _running = False

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def notificar_esp(estado: str) -> None:
    if not ESP_IP:
        return
    for intento in range(2):
        try:
            req = urllib.request.Request(
                f"http://{ESP_IP}/{estado}",
                data=b"",
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
            log.info("ESP cara → %s", estado)
            return
        except Exception as e:
            if intento == 0:
                time.sleep(0.5)
            else:
                log.warning("ESP sin respuesta: %s", e)


def grabar_clip(cap, frame_inicial: cv2.typing.MatLike) -> str:
    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0

    video_path = f"/tmp/alerta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    log.info("Grabando %ds...", CLIP_DURATION)
    out.write(frame_inicial)

    deadline = time.time() + CLIP_DURATION
    while time.time() < deadline and _running:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)

    out.release()
    log.info("Clip listo: %s (%.1f MB)", video_path, os.path.getsize(video_path) / 1e6)
    return video_path


def enviar_video(video_path: str) -> bool:
    msg = MIMEMultipart()
    msg["From"]    = f"Jarvis Seguridad <{SMTP_USER}>"
    msg["To"]      = EMAIL_TO
    msg["Subject"] = f"Movimiento detectado - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    msg.attach(MIMEText("Se detectó movimiento. Video adjunto.", "plain"))

    with open(video_path, "rb") as f:
        parte = MIMEBase("video", "mp4")
        parte.set_payload(f.read())
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", "attachment",
                         filename=os.path.basename(video_path))
        msg.attach(parte)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
        log.info("Video enviado a %s", EMAIL_TO)
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("Error de autenticación SMTP — revisa SMTP_USER y SMTP_PASS en .env")
    except smtplib.SMTPException as e:
        log.error("Error SMTP: %s", e)
    except OSError as e:
        log.error("Error de red: %s", e)
    return False


def detectar_movimiento():
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    if not cap.isOpened():
        log.error("No se pudo abrir la cámara con índice %d", CAMERA_SOURCE)
        sys.exit(1)

    log.info("Cámara %d abierta — vigilando (Ctrl+C para salir)", CAMERA_SOURCE)

    ret, frame1 = cap.read()
    ret, frame2 = cap.read()
    if not ret:
        log.error("No se pudo leer frames iniciales")
        cap.release()
        sys.exit(1)

    ultimo_envio = 0.0

    try:
        while _running:
            diff      = cv2.absdiff(frame1, frame2)
            gray      = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            blur      = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
            dilated   = cv2.dilate(thresh, None, iterations=3)
            contornos, _ = cv2.findContours(
                dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )

            hay_movimiento = any(cv2.contourArea(c) >= AREA_MIN for c in contornos)

            if hay_movimiento:
                ahora = time.time()
                if ahora - ultimo_envio >= COOLDOWN:
                    log.info("Movimiento detectado! Iniciando grabación...")
                    notificar_esp("sorprendido")

                    video_path = grabar_clip(cap, frame2)
                    if enviar_video(video_path):
                        ultimo_envio = time.time()
                    try:
                        os.remove(video_path)
                    except OSError:
                        pass

                    notificar_esp("idle")

                    # Refresca frames tras la grabación
                    ret, frame1 = cap.read()
                    if ret:
                        ret, frame2 = cap.read()
                    continue

            # Avance normal de frames
            frame1 = frame2
            ret, frame2 = cap.read()
            if not ret:
                log.warning("Frame perdido, reintentando...")
                time.sleep(0.1)
                ret, frame2 = cap.read()
                if not ret:
                    log.error("No se puede leer la cámara, cerrando")
                    break
    finally:
        cap.release()
        log.info("Cámara liberada. Bye.")


if __name__ == "__main__":
    detectar_movimiento()
