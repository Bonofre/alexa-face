# Alexa Face

Una "cara" animada con emociones para una pantalla OLED conectada a un ESP8266/ESP32, más un script de cámara de seguridad que detecta movimiento y avisa por correo.

## Objetivo
Proyecto de laboratorio para practicar **IoT, MicroPython y visión por computador**: un pequeño asistente con expresiones que reacciona a lo que pasa en casa.

## Cómo funciona

### 1. La cara (`main.py`, MicroPython)
- Dibuja ojos y boca en una pantalla **OLED SSD1306 128×64** por I2C.
- Tiene 8 estados: `idle`, `feliz`, `triste`, `enojado`, `sorprendido`, `aburrido`, `pensando` y `hablando`.
- Hace gestos solos: parpadea, mira a los lados y bosteza.
- Se conecta al WiFi y levanta un **mini servidor web**: desde el navegador (o con un `POST /<estado>`) se le cambia la emoción.

### 2. Cámara de seguridad (`camara_seguridad.py`, Python + OpenCV)
- Lee una cámara y **detecta movimiento** comparando cuadros.
- Al detectar algo, **graba un clip** y lo **envía por correo** (SMTP).
- Avisa al ESP para que la cara cambie de expresión.

## Configuración
```bash
cp config.example.py config.py   # WiFi del ESP
cp .env.example .env             # correo y cámara
```
Variables de `.env`: `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`, `CAMERA_SOURCE`, `ESP_IP`.

## Uso
- Copiar `main.py`, `config.py` y la librería `ssd1306.py` al ESP (por ejemplo con Thonny o `mpremote`).
- En el PC: `pip install opencv-python` y `python camara_seguridad.py`.
