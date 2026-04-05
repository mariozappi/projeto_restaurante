from flask import Flask, request, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

# =========================
# Banco de Dados
# =========================
def criar_banco():
    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT,
        data TEXT,
        hora TEXT,
        pessoas INTEGER,
        mesa TEXT,
        status TEXT
    )
    ''')
    conn.commit()
    conn.close()

criar_banco()

# =========================
# Configuração das Mesas
# =========================
mesas = {
    "Interna 1": 2,
    "Interna 2": 2,
    "Interna 3": 2,
    "Interna 4": 2,
    "Externa 1": 3,
    "Externa 2": 3,
    "Balcão": 3
}

# =========================
# Funções auxiliares
# =========================
def buscar_mesa_disponivel(data, hora, pessoas):
    """
    Retorna a primeira mesa disponível para o número de pessoas.
    Considera duração de 1 hora para cada reserva.
    """
    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mesa, hora FROM reservas
        WHERE data=? AND status IN ('reservado','confirmado')
    ''', (data,))
    reservas_do_dia = cursor.fetchall()
    conn.close()

    hora_obj = datetime.strptime(hora, "%H:%M")
    
    ocupadas = []
    for r_mesa, r_hora in reservas_do_dia:
        r_hora_obj = datetime.strptime(r_hora, "%H:%M")
        r_hora_fim = r_hora_obj + timedelta(hours=1)
        hora_fim = hora_obj + timedelta(hours=1)
        
        # Se os intervalos se sobrepõem: Max das entradas < Min das saídas
        if max(r_hora_obj, hora_obj) < min(r_hora_fim, hora_fim):
            ocupadas.append(r_mesa)

    for mesa, capacidade in mesas.items():
        if mesa not in ocupadas and pessoas <= capacidade:
            return mesa
    return None  # Nenhuma mesa disponível

def agendar_reserva(nome, telefone, data, hora, pessoas):
    """Agendar reserva em uma mesa disponível."""
    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
        data_iso = str(data_obj)
    except ValueError:
        try:
            data_obj = datetime.strptime(data, "%d/%m/%Y").date()
            data_iso = str(data_obj)
        except ValueError:
            return None, "data_invalida"

    mesa_disponivel = buscar_mesa_disponivel(data_iso, hora, pessoas)
    if mesa_disponivel:
        mesa = mesa_disponivel
        status = "reservado"
    else:
        mesa = None
        status = "espera"

    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reservas (nome, telefone, data, hora, pessoas, mesa, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, telefone, data_iso, hora, pessoas, mesa, status))
    conn.commit()
    conn.close()
    return mesa, status

# =========================
# Thread de notificações
# =========================
def notificar_clientes():
    while True:
        try:
            now = datetime.now()
            conn = sqlite3.connect('reservas.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, nome, telefone, data, hora, status FROM reservas
                WHERE status IN ('reservado', 'confirmado')
            ''')
            reservas = cursor.fetchall()
            for r in reservas:
                try:
                    reserva_time = datetime.strptime(f"{r[3]} {r[4]}", "%Y-%m-%d %H:%M")
                except ValueError:
                    continue

                segundos_ate_reserva = (reserva_time - now).total_seconds()

                if r[5] == "reservado" and 0 < segundos_ate_reserva <= 3600:
                    # Aqui enviar WhatsApp real depois
                    print(f"[NOTIFICAÇÃO] Enviar WhatsApp para {r[2]} sobre reserva {r[0]} (confirme para garantir)")
                    
                if r[5] == "reservado" and segundos_ate_reserva <= -1200:
                    cursor.execute("DELETE FROM reservas WHERE id=?", (r[0],))
                    print(f"[LIBERADO] Reserva {r[0]} não confirmada após 20min, mesa liberada")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ERRO THREAD] {e}")
        time.sleep(60)

threading.Thread(target=notificar_clientes, daemon=True).start()

# =========================
# Rotas
# =========================
@app.route('/')
def index():
    telefone = request.args.get('telefone', '')
    horarios = [f"{h:02d}:{m:02d}" for h in range(8, 22) for m in (0,30)]
    data_hoje = datetime.now().date().isoformat()
    hora_agora = datetime.now().strftime("%H:%M")
    
    opcoes_hora = ''
    for h in horarios:
        opcoes_hora += f'<option value="{h}">{h}</option>'

    return f'''
    <h2>Reserva de Mesa</h2>
    <form method="POST" action="/reservar">
        Nome: <input name="nome" required><br><br>
        Telefone: <input name="telefone" value="{telefone}" required><br><br>
        Data: <input type="date" name="data" id="data_input" min="{data_hoje}" required><br><br>
        Hora: <select name="hora" required id="hora">{opcoes_hora}</select><br><br>
        Pessoas: <input type="number" name="pessoas" min="1" max="3" required><br><br>
        <button type="submit">Reservar</button>
    </form>
    <script>
    const dataInput = document.getElementById('data_input');
    const horaSelect = document.getElementById('hora');
    const dataHoje = "{data_hoje}";
    const horaAgora = "{hora_agora}";
    
    function atualizarHorarios() {{
        const selectedData = dataInput.value;
        Array.from(horaSelect.options).forEach(opt => {{
            if (selectedData === dataHoje) {{
                if (opt.value < horaAgora) {{
                    opt.disabled = true;
                    opt.text = opt.value + " (passado)";
                }} else {{
                    opt.disabled = false;
                    opt.text = opt.value;
                }}
            }} else {{
                opt.disabled = false;
                opt.text = opt.value;
            }}
        }});
    }}
    
    dataInput.addEventListener('change', atualizarHorarios);
    if(dataInput.value) atualizarHorarios();
    </script>
    '''

@app.route('/reservar', methods=['POST'])
def reservar():
    dados = request.form
    mesa, status = agendar_reserva(dados['nome'], dados['telefone'], dados['data'], dados['hora'], int(dados['pessoas']))
    if status == "data_invalida":
        return "<h3>Data inválida. Use o formato correto.</h3>"
    if status in ("reservado", "confirmado"):
        return f"<h3>Reserva {status}! Mesa {mesa}</h3>"
    else:
        return "<h3>Sem vagas. Você entrou na fila de espera.</h3>"

@app.route('/confirmar/<int:id>')
def confirmar(id):
    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE reservas SET status='confirmado' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return f"<h3>Reserva {id} confirmada com sucesso!</h3>"

@app.route('/painel')
def painel():
    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, telefone, data, hora, pessoas, mesa, status FROM reservas ORDER BY data, hora")
    reservas = cursor.fetchall()
    conn.close()

    html = "<h2>Painel do Salão</h2><table border='1' cellpadding='5'>"
    html += "<tr><th>Nome</th><th>Telefone</th><th>Data</th><th>Hora</th><th>Pessoas</th><th>Mesa</th><th>Status</th><th>Ações</th></tr>"
    for r in reservas:
        html += f"<tr><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td><td>{r[7]}</td>"
        html += f"<td><form method='POST' action='/excluir' style='display:inline;'><input type='hidden' name='id' value='{r[0]}'><button>Excluir</button></form></td></tr>"
    html += "</table><br>"
    html += '<form method="POST" action="/resetar" onsubmit="return confirm(\'Tem certeza que deseja resetar todas as reservas?\');"><button style="background:red;color:white;">Resetar Todas</button></form>'
    return html

@app.route('/excluir', methods=['POST'])
def excluir():
    id = request.form['id']
    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservas WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('painel'))

@app.route('/resetar', methods=['POST'])
def resetar():
    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservas")
    conn.commit()
    conn.close()
    return "<h3>Todas as reservas foram resetadas!</h3>"

if __name__ == "__main__":
    app.run(debug=True)