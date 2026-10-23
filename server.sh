echo "Atualizando Requerimentos..."
source ./engine/bin/activate
pip install --update
pip install -r requirements.txt
echo "Sistema Atualizado e Requirimentos Instalados"