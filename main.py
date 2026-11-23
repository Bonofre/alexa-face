from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import network, socket, time
from os import urandom

try:
    from config import WIFI_SSID, WIFI_PASS
except ImportError:
    WIFI_SSID = "red"
    WIFI_PASS = "clave"

i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)
wlan = network.WLAN(network.STA_IF)

ESTADOS = frozenset(("idle", "feliz", "triste", "enojado", "sorprendido", "aburrido", "pensando", "hablando"))
estado_actual = "idle"

HTML = (
    "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
    "<h2>Alexa Face</h2>"
    "<style>button{margin:4px;padding:8px 14px;font-size:14px;cursor:pointer}</style>"
    "<script>function s(e){fetch('/'+e,{method:'POST'})}</script>"
    "<button onclick=\"s('idle')\">Idle</button>"
    "<button onclick=\"s('feliz')\">Feliz</button>"
    "<button onclick=\"s('triste')\">Triste</button>"
    "<button onclick=\"s('enojado')\">Enojado</button>"
    "<button onclick=\"s('sorprendido')\">Sorprendido</button>"
    "<button onclick=\"s('aburrido')\">Aburrido</button>"
    "<button onclick=\"s('pensando')\">Pensando</button>"
    "<button onclick=\"s('hablando')\">Hablando</button>"
)

# ── Primitives ───────────────────────────────────────────────────────────────

def circle(x0, y0, r, col=1):
    x, y, d = r, 0, 1 - r
    while x >= y:
        for dx, dy in [(x,y),(-x,y),(x,-y),(-x,-y),(y,x),(-y,x),(y,-x),(-y,-x)]:
            oled.pixel(x0+dx, y0+dy, col)
        oled.fill_rect(x0-x, y0+y, 2*x+1, 1, col)
        oled.fill_rect(x0-x, y0-y, 2*x+1, 1, col)
        if d < 0:
            d += 2*y + 3
        else:
            d += 2*(y - x) + 5
            x -= 1
        y += 1

def draw_eyes(ox=0, oy=0):
    circle(35+ox, 25+oy, 14)
    circle(93+ox, 25+oy, 14)
    circle(35+ox, 27+oy, 9, 0)
    circle(93+ox, 27+oy, 9, 0)
    oled.fill_rect(21+ox, 36+oy, 28, 4, 0)  # corta el arco inferior (sin párpado)
    oled.fill_rect(79+ox, 36+oy, 28, 4, 0)
    oled.fill_rect(38+ox, 17+oy, 3, 2, 1)   # destello
    oled.fill_rect(96+ox, 17+oy, 3, 2, 1)

# ── Expresiones ──────────────────────────────────────────────────────────────

def draw_face(estado):
    oled.fill(0)
    if estado == "idle":
        draw_eyes()
        oled.fill_rect(35, 48, 58, 4, 1)
    elif estado == "feliz":
        draw_eyes()
        for x in range(-20, 21):
            y = 52 - (x*x)//30
            if 0 <= 64+x <= 127 and 0 <= y <= 63:
                oled.pixel(64+x, y, 1)
                oled.pixel(64+x, y+1, 1)
    elif estado == "triste":
        draw_eyes()
        oled.fill_rect(20, 10, 20, 4, 1)
        oled.fill_rect(88, 10, 20, 4, 1)
        for x in range(-20, 21):
            y = 44 + (x*x)//30
            if 0 <= 64+x <= 127 and 0 <= y <= 63:
                oled.pixel(64+x, y, 1)
                oled.pixel(64+x, y+1, 1)
    elif estado == "enojado":
        draw_eyes()
        for i in range(20):
            oled.pixel(20+i, 10+i//3, 1)
            oled.pixel(20+i, 11+i//3, 1)
            oled.pixel(88+i, 10+(19-i)//3, 1)
            oled.pixel(88+i, 11+(19-i)//3, 1)
        oled.fill_rect(38, 48, 52, 3, 1)
    elif estado == "sorprendido":
        circle(35, 25, 14)
        circle(93, 25, 14)
        circle(35, 25, 4, 0)
        circle(93, 25, 4, 0)
        oled.fill_rect(37, 17, 3, 2, 1)
        oled.fill_rect(95, 17, 3, 2, 1)
        circle(64, 50, 12)
        circle(64, 50, 8, 0)
    elif estado == "aburrido":
        draw_eyes()
        oled.fill_rect(21, 11, 28, 13, 0)   # párpados caídos
        oled.fill_rect(79, 11, 28, 13, 0)
        oled.fill_rect(48, 48, 32, 3, 1)
    elif estado == "pensando":
        draw_eyes()
        oled.fill_rect(82, 10, 26, 4, 1)
        oled.fill_rect(35, 48, 30, 4, 1)
        oled.fill_rect(65, 44, 18, 4, 1)
    oled.show()

# ── Animaciones ──────────────────────────────────────────────────────────────

def parpadeo():
    oled.fill_rect(21, 11, 28, 28, 0)
    oled.fill_rect(79, 11, 28, 28, 0)
    oled.fill_rect(21, 24, 28, 5, 1)
    oled.fill_rect(79, 24, 28, 5, 1)
    oled.show()
    time.sleep_ms(120)

def mirar_lado(lado):
    oled.fill(0)
    px = 5 if lado == "der" else -5
    circle(35, 25, 14)                      # esclerótica fija
    circle(93, 25, 14)
    circle(35+px, 27, 9, 0)                 # solo la pupila se mueve
    circle(93+px, 27, 9, 0)
    oled.fill_rect(38+px, 17, 3, 2, 1)
    oled.fill_rect(96+px, 17, 3, 2, 1)
    oled.fill_rect(35, 48, 58, 4, 1)
    oled.show()
    time.sleep_ms(600)

def bostezar():
    draw_face("idle")
    time.sleep_ms(300)
    for r in range(3, 11, 2):
        oled.fill_rect(44, 44, 40, 16, 0)
        circle(64, 51, r)
        oled.show()
        time.sleep_ms(150)
    time.sleep_ms(400)
    for r in range(9, 2, -2):
        oled.fill_rect(44, 44, 40, 16, 0)
        circle(64, 51, r)
        oled.show()
        time.sleep_ms(150)
    draw_face("idle")

def gesto_aleatorio():
    r = urandom(1)[0] % 8
    if r == 0:
        parpadeo()
        time.sleep_ms(80)
        parpadeo()
    elif r == 1:
        mirar_lado("der")
    elif r == 2:
        mirar_lado("izq")
    elif r == 3:
        bostezar()
    # r 4–7: sin gesto, cara idle sin cambios

# ── WiFi ─────────────────────────────────────────────────────────────────────

def conectar_wifi():
    oled.fill(0)
    oled.text("Conectando...", 0, 28)
    oled.show()
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    for _ in range(20):
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            oled.fill(0)
            oled.text("WiFi OK!", 20, 20)
            oled.text(ip, 10, 35)
            oled.show()
            time.sleep(2)
            return ip
        time.sleep(1)
    oled.fill(0)
    oled.text("Sin WiFi", 25, 28)
    oled.show()
    return None

# ── HTTP ─────────────────────────────────────────────────────────────────────

def parse_request(data):
    try:
        line = data.split('\r\n')[0]
        parts = line.split(' ')
        if len(parts) < 2:
            return None, None
        return parts[0], parts[1].strip('/')
    except Exception:
        return None, None

def extract_estado(path, body):
    if path in ESTADOS:
        return path
    # compatibilidad con clientes que envían la emoción en el cuerpo
    for e in ESTADOS:
        if e in body:
            return e
    return None

# ── Main ─────────────────────────────────────────────────────────────────────

ip = conectar_wifi()
if not ip:
    raise SystemExit("Sin red")

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(('', 80))
srv.listen(3)
srv.settimeout(0.1)

draw_face("idle")
contador = 0
boca_abierta = False

while True:
    if not wlan.isconnected():
        draw_face("triste")
        conectar_wifi()
        draw_face(estado_actual)
        contador = 0

    nuevo_estado = None
    try:
        conn, addr = srv.accept()
        try:
            data = conn.recv(512).decode('utf-8', 'ignore')
            method, path = parse_request(data)
            if method == "GET":
                conn.send(HTML)
            elif method == "POST":
                nuevo = extract_estado(path, data)
                if nuevo:
                    estado_actual = nuevo
                    nuevo_estado = nuevo
                    boca_abierta = False
                    contador = 0
                conn.send("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Type: text/plain\r\n\r\nOK")
            else:
                conn.send("HTTP/1.1 404 Not Found\r\n\r\n")
        except Exception:
            pass
        finally:
            conn.close()
    except OSError:
        pass

    if nuevo_estado:
        draw_face(nuevo_estado)

    if estado_actual == "hablando":
        oled.fill(0)
        draw_eyes()
        if boca_abierta:
            circle(64, 50, 10)
            circle(64, 50, 6, 0)
        else:
            oled.fill_rect(38, 50, 52, 4, 1)
        oled.show()
        boca_abierta = not boca_abierta
        time.sleep_ms(100)
    else:
        contador += 1
        if contador >= 15:
            parpadeo()
            time.sleep_ms(120)
            draw_face(estado_actual)
            if estado_actual == "idle":
                gesto_aleatorio()
                draw_face("idle")
            contador = 0
        time.sleep_ms(200)
