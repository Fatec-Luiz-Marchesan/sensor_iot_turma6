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

