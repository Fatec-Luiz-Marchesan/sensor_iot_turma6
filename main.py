from time import time
import serial
import threading
import time

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from flask import Flask, jsonify, render_template, render_template_string

cred = credentials.Certificate('firebase_key.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)

dados_sensor = {
    "distancia": 0, 
    "timestamp":"",
    "ultima_gravacao_hora": "--:--:--",
    "ultimo_valor_gravado": "--"
}

PORTA_SERIAL = 'COM11'
BAUD_RATE_RATE = 9600
INTERVALO = 5

distancia_atual =0.0

def salvar_no_firebase(distancia_atual):
    try:
        db.collection("historico_distancia").add({
            "distancia":distancia_atual,
            "timestamp":firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Erro do Firebase: {e}")

def ler_porta_serial():
    global distancia_atual, dados_sensor
    flag = 0
    try:
        ser = serial.Serial(PORTA_SERIAL, BAUD_RATE_RATE, timeout=1)
        time.sleep(2)
        print(f"Conectado ao Sensor Arduino na porta: {PORTA_SERIAL}")

        while True:
            if ser.in_waiting > 0:
                linha = ser.readline().decode('utf-8').strip()

                if "Distancia: Analogica -" in linha:
                    try:
                        valor_str = linha.split("-")[1].strip()
                        distancia_atual = float(valor_str)
                        dados_sensor["distancia"] = distancia_atual
                        dados_sensor["timestamp"] = time.time()
                        agora = time.time()

                        if agora - flag >= INTERVALO:
                            salvar_no_firebase(distancia_atual)
                            dados_sensor["ultima_gravacao_hora"] = time.strftime('%H:%M:%S', time.localtime(agora))
                            dados_sensor["ultimo_valor_gravado"] = distancia_atual
                            flag=agora
                    except ValueError:
                        pass
    except Exception as e:
        print(f"Erro na conector serial Arduino: {e}")
        print("Verifique os sensores e portas do serial [COM]")
        time.sleep(5)
        print("Tentando reconectar...")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sensor Distância - SR04</title>
    <style>
        body{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f4f9;
            padding-top: 10%;
        }
        .card{
            background-color: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgb(0, 0, 0, 0.2); 
            display: inline-block;
        }
        h1{
            color:#333;
            margin-top: 0;
        }
        .valor{
            font-size: 5em;
            font-weight: bold;
            color: #0078d7;
        }
        .unidade{
            font-size: 0,3em;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Distância Atual</h1>
        <div class="valor" id="distancia-display"> 
            --
            <span class="unidade">cm</span> 
        </div>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px;">
        <h3 style="color: #666; font-size: 1.2em; margin-bottom: 10px;">Ultimo Registro no Firebase: (&lt;)</h3>
        <div style="font-size: 1.5em; color: #333">
            <span id="Ultimo Valor"> -- </span>
        </div>
        <div style="font-size: 0.9em; color: #888; margin-top: 10px;">
            às <span id="Ultima hora: "> --:--:-- </span>
        </div>
    </div>
    <footer>
        <script>
            function buscarDistancia(){
                function buscarDistancia(){
                    fetch('/api/dados')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('distancia-display').innerHTML = Fixed(2) + '<span class="unidade"> cm</span>'
                    if(data.ultimo_valor_gravado !== "--"){
                        document.getElementById('ultimo-valor').innerText = parseFloat(data.ultimo_valor_gravado).toFixed(2)
                    }else{
                        document.getElementById('ultima-hora').innerText = data.ultima_gravacao_hora
                    }
                    }).catch(error => console.error('Erro de conector Script API: ', error))
                }
            }
            setInterval(buscarDistancia, 5000)
        </script>
    </footer>
</body>
</html>
"""
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)
@app.route('/api/dados')
def api_dados():
    return jsonify(dados_sensor)

if __name__ == '__main__':
    thread_arduino = threading.Thread(target=ler_porta_serial, daemon=True)
    thread_arduino.start()

    print("servider de leitura de Arduino funcional porta 80.")
    app.run(host='0.0.0.0', port=80)