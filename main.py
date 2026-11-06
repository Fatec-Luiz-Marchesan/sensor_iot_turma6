import os
import time
import random
import threading
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string

try:
    import serial
except ImportError:
    serial = None

app = Flask(__name__)

PORTA_SERIAL = os.getenv('PORTA_SERIAL', 'COM8')
BAUD_RATE = 9600
INTERVALO = 1

PORTA_WEB = int(os.getenv('PORT', 8080))

dados_sensor = {
    "distancia": 0.0,
    "timestamp": "--:--:--",
    "status": "Iniciando...",
    "origem": "Nenhuma leitura ainda"
}

lock = threading.Lock()
def ler_porta_serial():
    """
    Tenta se conectar à porta serial física do Arduino.
    Se o código estiver rodando na VM do Google Cloud (onde a porta COM8 física
    não existe), ativa automaticamente a simulação para exibição na tela.
    """
    global dados_sensor
    simulando = False

    while True:
        if serial and not simulando:
            try:
                print(f"[SERIAL] Tentando conectar na porta: {PORTA_SERIAL} a {BAUD_RATE} bps...")
                ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
                time.sleep(2)
                print(f"[SERIAL] ✅ Conectado com sucesso na porta: {PORTA_SERIAL}")

                while True:
                    if ser.in_waiting > 0:
                        linha = ser.readline().decode('utf-8', errors='ignore').strip()

                        if "distancia" in linha.lower():
                            try:
                                delimitador = "-" if "-" in linha else ":"
                                valor_str = linha.split(delimitador)[1].replace("cm", "").strip()
                                dist = float(valor_str)
                                with lock:
                                    dados_sensor["distancia"] = round(dist, 2)
                                    dados_sensor["timestamp"] = datetime.now().strftime("%H:%M:%S")
                                    dados_sensor["status"] = "Conectado (Arduino Físico)"
                                    dados_sensor["origem"] = f"Porta {PORTA_SERIAL}"
                            except (ValueError, IndexError):
                                pass
                        else:
                            try:
                                dist = float(linha)
                                with lock:
                                    dados_sensor["distancia"] = round(dist, 2)
                                    dados_sensor["timestamp"] = datetime.now().strftime("%H:%M:%S")
                                    dados_sensor["status"] = "Conectado (Arduino Físico)"
                                    dados_sensor["origem"] = f"Porta {PORTA_SERIAL}"
                            except ValueError:
                                pass

                    time.sleep(0.05)

            except Exception as e:
                print(f"[AVISO] Porta serial {PORTA_SERIAL} indisponível: {e}")
                print("[INFO] Como o servidor está rodando na VM do Google Cloud, a porta física COM8 não existe na nuvem.")
                print("[INFO] Ativando modo de simulação realista para exibição na tela da Cloud VM...")
                simulando = True

        if simulando:
            valor_base = 30.0
            while simulando:
                variacao = random.uniform(-3.5, 3.5)
                valor_base = max(4.0, min(80.0, valor_base + variacao))

                with lock:
                    dados_sensor["distancia"] = round(valor_base, 2)
                    dados_sensor["timestamp"] = datetime.now().strftime("%H:%M:%S")
                    dados_sensor["status"] = "Ativo (Simulação Cloud VM)"
                    dados_sensor["origem"] = "Google Cloud Environment"

                time.sleep(INTERVALO)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor de Proximidade Arduino - Google Cloud VM</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            text-align: center;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: rgba(30, 41, 59, 0.85);
            backdrop-filter: blur(12px);
            padding: 40px 30px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            max-width: 480px;
            width: 100%;
        }
        h1 {
            color: #f8fafc;
            font-size: 1.6rem;
            margin-bottom: 6px;
        }
        .subtitulo {
            color: #94a3b8;
            font-size: 0.85rem;
            margin-bottom: 25px;
        }
        .valor-container {
            margin: 20px 0;
            display: flex;
            align-items: baseline;
            justify-content: center;
            gap: 6px;
        }
        .valor {
            font-size: 5rem;
            font-weight: 800;
            color: #38bdf8;
            line-height: 1;
            transition: color 0.3s ease;
        }
        .unidade {
            font-size: 1.6rem;
            color: #94a3b8;
            font-weight: 600;
        }
        /* Barra de proximidade visual */
        .barra-track {
            height: 12px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 999px;
            overflow: hidden;
            margin: 20px 0 10px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .barra-fill {
            height: 100%;
            width: 0%;
            background: #10b981;
            border-radius: 999px;
            transition: width 0.3s ease, background-color 0.3s ease;
        }
        .alerta-status {
            display: inline-block;
            margin-top: 10px;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
        }
        .info-footer {
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            margin-top: 25px;
            padding-top: 15px;
            font-size: 0.8rem;
            color: #94a3b8;
            display: flex;
            justify-content: space-between;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Distância Atual</h1>
        <div class="subtitulo">Sensor de Proximidade • Google Cloud VM</div>

        <div class="valor-container">
            <span class="valor" id="distancia-display">--</span>
            <span class="unidade">cm</span>
        </div>

        <div class="barra-track">
            <div class="barra-fill" id="barra-fill"></div>
        </div>

        <div>
            <span class="alerta-status" id="alerta-status">Aguardando Leitura...</span>
        </div>

        <div class="info-footer">
            <span>Status: <strong id="status-texto" style="color: #fff">Conectando...</strong></span>
            <span>Hora: <strong id="timestamp-texto" style="color: #fff">--:--:--</strong></span>
        </div>
    </div>

    <script>
        function classificarDistancia(dist) {
            if (dist < 10) {
                return { texto: "⚠️ Perigo: Muito Próximo!", cor: "#ef4444", bg: "rgba(239, 68, 68, 0.2)" };
            } else if (dist < 30) {
                return { texto: "⚡ Atenção: Proximidade Média", cor: "#f59e0b", bg: "rgba(245, 158, 11, 0.2)" };
            } else {
                return { texto: "✅ Seguro: Área Livre", cor: "#10b981", bg: "rgba(16, 185, 129, 0.2)" };
            }
        }

        function buscaDistancia() {
            fetch('/api/dados')
                .then(response => response.json())
                .then(data => {
                    const dist = parseFloat(data.distancia);
                    const display = document.getElementById('distancia-display');
                    const fill = document.getElementById('barra-fill');
                    const badge = document.getElementById('alerta-status');

                    if (isNaN(dist) || dist <= 0) {
                        display.innerText = "--";
                    } else {
                        display.innerText = dist.toFixed(1);
                        const info = classificarDistancia(dist);

                        display.style.color = info.cor;
                        badge.innerText = info.texto;
                        badge.style.color = info.cor;
                        badge.style.backgroundColor = info.bg;

                        const porcentagem = Math.min(100, Math.max(5, (dist / 80) * 100));
                        fill.style.width = porcentagem + '%';
                        fill.style.backgroundColor = info.cor;
                    }

                    document.getElementById('status-texto').innerText = data.status || "Ativo";
                    document.getElementById('timestamp-texto').innerText = data.timestamp || "--:--:--";
                })
                .catch(err => {
                    console.error("Erro na busca:", err);
                    document.getElementById('status-texto').innerText = "Erro de Conexão";
                });
        }

        // Atualiza a cada 1 segundo (1000ms)
        window.onload = function() {
            buscaDistancia();
            setInterval(buscaDistancia, 1000);
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/dados')
def api_dados():
    with lock:
        return jsonify(dados_sensor)


@app.route('/api/sensor/leitura', methods=['POST'])
def api_sensor_leitura():
    """
    Permite que o seu computador local envie as leituras do Arduino
    para a VM do Google Cloud via HTTP POST.
    Exemplo de payload: {"distancia": 24.5}
    """
    dados = request.get_json(silent=True)
    if not dados or 'distancia' not in dados:
        return jsonify({"erro": "Campo 'distancia' ausente"}), 400

    try:
        dist = float(dados['distancia'])
        with lock:
            dados_sensor["distancia"] = round(dist, 2)
            dados_sensor["timestamp"] = datetime.now().strftime("%H:%M:%S")
            dados_sensor["status"] = "Conectado via HTTP (Local -> Nuvem)"
            dados_sensor["origem"] = dados.get("origem", "Agente Local")
        return jsonify({"sucesso": True}), 200
    except (ValueError, TypeError) as e:
        return jsonify({"erro": f"Distância inválida: {e}"}), 400

if __name__ == '__main__':
    thread_arduino = threading.Thread(target=ler_porta_serial, daemon=True)
    thread_arduino.start()

    print("=" * 65)
    print("🚀 SERVIDOR WEB INICIADO")
    print(f"📡 Porta: {PORTA_WEB}")
    print(f"🌐 Acesse localmente: http://localhost:{PORTA_WEB}")
    print("☁️ No Google Cloud Shell: Clique no botão 'Web Preview' (Porta 8080)")
    print("=" * 65)

    app.run(host='0.0.0.0', port=PORTA_WEB)