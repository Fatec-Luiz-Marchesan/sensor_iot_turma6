
import re
import threading
import time
import serial
from serial.tools import list_ports

# pyrefly: ignore [missing-import]
import firebase_admin
# pyrefly: ignore [missing-import]
from firebase_admin import credentials
# pyrefly: ignore [missing-import]
from firebase_admin import firestore
# pyrefly: ignore [missing-import]
from flask import Flask, jsonify, render_template_string, send_file

cred = credentials.Certificate('firebase_key.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)

dados_sensor = {
    "distancia": 0.0,
    "timestamp": "--:--:--",
    "ultima_gravacao_hora": "--:--:--",
    "ultimo_valor_gravado": "--",
    "status": "Aguardando leitura serial..."
}

PORTA_SERIAL = 'COM9'
BAUD_RATE = 9600
INTERVALO = 5

distancia_atual = 0.0
lock = threading.Lock()


def salvar_no_firebase(valor_distancia: float) -> None:
    try:
        db.collection("historico_distancia").add({
            "distancia": valor_distancia,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Erro ao salvar no firebase: {e}")


def extrair_distancia(linha: str) -> float | None:
    """Extrai o valor numérico da leitura enviada pelo Arduino via Serial."""
    if not linha:
        return None

    trecho = linha.split("-")[-1] if "-" in linha else linha
    correspondencias = re.findall(r"\d+(?:[.,]\d+)?", trecho)
    if not correspondencias:
        return None

    try:
        return float(correspondencias[-1].replace(",", "."))
    except ValueError:
        return None


def obter_porta_serial(porta_preferida: str) -> str:
    """Retorna a porta configurada ou detecta automaticamente a porta do Arduino."""
    portas_disponiveis = [p.device for p in list_ports.comports()]
    if porta_preferida in portas_disponiveis or not portas_disponiveis:
        return porta_preferida

    print(f"Porta {porta_preferida} não encontrada. Portas disponíveis: {portas_disponiveis}")
    return portas_disponiveis[0]


def ler_porta_serial() -> None:
    global distancia_atual, dados_sensor
    flag = 0.0

    while True:
        porta_alvo = obter_porta_serial(PORTA_SERIAL)
        try:
            with serial.Serial(porta_alvo, BAUD_RATE, timeout=1) as ser:
                time.sleep(2)
                ser.reset_input_buffer()
                print(f"Conectado ao Arduino na porta {porta_alvo}")

                with lock:
                    dados_sensor["status"] = f"Conectado ({porta_alvo})"

                while True:
                    linha_bytes = ser.readline()
                    if not linha_bytes:
                        continue

                    linha = linha_bytes.decode('utf-8', errors='ignore').strip()
                    if not linha:
                        continue

                    print(f"[Serial {porta_alvo}] {linha}")

                    valor = extrair_distancia(linha)
                    if valor is not None:
                        agora = time.time()
                        hora_formatada = time.strftime('%H:%M:%S', time.localtime(agora))

                        with lock:
                            distancia_atual = valor
                            dados_sensor["distancia"] = distancia_atual
                            dados_sensor["timestamp"] = hora_formatada
                            dados_sensor["status"] = f"Ativo ({porta_alvo})"

                        if agora - flag >= INTERVALO:
                            if distancia_atual < 150:
                                threading.Thread(
                                    target=salvar_no_firebase,
                                    args=(distancia_atual,),
                                    daemon=True
                                ).start()
                                with lock:
                                    dados_sensor["ultima_gravacao_hora"] = hora_formatada
                                    dados_sensor["ultimo_valor_gravado"] = distancia_atual
                            flag = agora
        except Exception as e:
            erro_str = str(e)
            if "PermissionError" in erro_str or "Acesso negado" in erro_str or "Access is denied" in erro_str:
                msg_status = f"⚠️ Porta {porta_alvo} ocupada! Feche o Monitor Serial da Arduino IDE."
            else:
                msg_status = f"Erro Serial ({porta_alvo}): conectando..."

            with lock:
                dados_sensor["status"] = msg_status

            print(f"Erro na comunicação Serial ({porta_alvo}): {e}")
            print("Verifique se a porta está correta ou se o Monitor Serial da Arduino IDE está fechado.")
            time.sleep(2)
            print("Tentando reconectar...")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor de Distância HC-SR04</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; background-color: #f4f4f9; padding-top: 100px; }
        .card { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); display: inline-block; min-width: 320px; }
        h1 { color: #333; margin-top: 0; }
        .valor { font-size: 5em; font-weight: bold; color: #0078D7; }
        .unidade { font-size: 0.3em; color: #666; }
        .status { font-size: 0.85em; color: #666; margin-top: 12px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Distância Atual</h1>
        <div class="valor" id="distancia-display">-- <span class="unidade">cm</span></div>
        <div class="status">Status: <strong id="status-serial">Conectando...</strong></div>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <h3 style="color: #666; font-size: 1.2em; margin-bottom: 10px;">Último Registro no Firebase (&lt; 150cm)</h3>
        <div style="font-size: 1.5em; color: #333;">
            <span id="ultimo-valor">--</span> <span class="unidade">cm</span>
        </div>
        <div style="font-size: 0.9em; color: #888; margin-top: 5px;">
            às <span id="ultima-hora">--:--:--</span>
        </div>
    </div>

    <script>
        function buscarDistancia() {
            fetch('/api/dados', { cache: 'no-store' })
                .then(response => response.json())
                .then(data => {
                    const dist = Number(data.distancia);
                    document.getElementById('distancia-display').innerHTML =
                        (!isNaN(dist) && dist > 0 ? dist.toFixed(2) : '--') + ' <span class="unidade">cm</span>';

                    if (data.ultimo_valor_gravado !== "--" && data.ultimo_valor_gravado !== undefined) {
                        document.getElementById('ultimo-valor').innerText = parseFloat(data.ultimo_valor_gravado).toFixed(2);
                    } else {
                        document.getElementById('ultimo-valor').innerText = "--";
                    }
                    document.getElementById('ultima-hora').innerText = data.ultima_gravacao_hora || "--:--:--";
                    if (data.status) {
                        document.getElementById('status-serial').innerText = data.status;
                    }
                })
                .catch(error => console.error('Erro de conexão:', error));
        }

        buscarDistancia();
        setInterval(buscarDistancia, 1000);
    </script>
</body>
</html>
"""


@app.after_request
def adicionar_cabecalhos_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/interface.html')
@app.route('/interface')
def interface_page():
    return send_file('interface.html')


@app.route('/api/dados')
def api_dados():
    with lock:
        return jsonify(dados_sensor)


if __name__ == '__main__':
    thread_arduino = threading.Thread(target=ler_porta_serial, daemon=True)
    thread_arduino.start()

    print("Iniciando servidor web em http://127.0.0.1:80 ...")
    app.run(host='0.0.0.0', port=80, use_reloader=False)
