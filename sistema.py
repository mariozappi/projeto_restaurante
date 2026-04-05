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
    "Interna 4": 3,
    "Externa 1": 3,
    "Externa 2": 3,
    "Balcão": 3
}

# =========================
# Funções auxiliares
# =========================
def alocar_mesas(data, hora, pessoas, mesa_escolhida):
    """
    Tenta alocar a mesa escolhida. Se as pessoas excederem o limite,
    busca mesas contíguas adicionais.
    """
    if mesa_escolhida not in mesas:
        return False, "Mesa inválida."
        
    try:
        data_datetime = datetime.strptime(data, "%Y-%m-%d")
        dia_da_semana = data_datetime.weekday()
        h, m = map(int, hora.split(':'))
        horario_valido = False
        if dia_da_semana in (2, 3, 4):
            if 17 <= h <= 21 or (h == 22 and m == 0):
                horario_valido = True
        elif dia_da_semana in (5, 6):
            if (12 <= h <= 15) or (h == 16 and m == 0) or (18 <= h <= 21) or (h == 22 and m == 0):
                horario_valido = True
                
        if not horario_valido:
            return False, "Horário de funcionamento não permitido para o dia escolhido."
    except Exception:
        pass

    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mesa, hora FROM reservas
        WHERE data=? AND status IN ('reservado','confirmado')
    ''', (data,))
    reservas_do_dia = cursor.fetchall()
    conn.close()

    hora_obj = datetime.strptime(hora, "%H:%M")
    
    ocupadas = set()
    for r_mesa, r_hora in reservas_do_dia:
        r_hora_obj = datetime.strptime(r_hora, "%H:%M")
        r_hora_fim = r_hora_obj + timedelta(hours=1)
        hora_fim = hora_obj + timedelta(hours=1)
        
        if max(r_hora_obj, hora_obj) < min(r_hora_fim, hora_fim):
            ocupadas.add(r_mesa)

    if mesa_escolhida in ocupadas:
        return False, "Sua mesa primária escolhida já está reservada neste horário."

    mesas_alocadas = [mesa_escolhida]
    pessoas_restantes = pessoas - mesas[mesa_escolhida]
    
    if pessoas_restantes <= 0:
        return True, mesas_alocadas

    _prefix = mesa_escolhida.split()[0]
    outras_mesas = [m for m in mesas.keys() if m != mesa_escolhida and m not in ocupadas]
    outras_mesas.sort(key=lambda x: (x.split()[0] != _prefix, x)) 

    for m in outras_mesas:
        if pessoas_restantes <= 0:
            break
        mesas_alocadas.append(m)
        pessoas_restantes -= mesas[m]

    if pessoas_restantes > 0:
        return False, "Não há mesas livres suficientes neste horário para comportar todos os convidados."

    return True, mesas_alocadas

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
    horarios = [f"{h:02d}:{m:02d}" for h in range(12, 23) for m in (0,30)]
    if "22:30" in horarios: horarios.remove("22:30")
    
    data_hoje = datetime.now().date().isoformat()
    hora_agora = datetime.now().strftime("%H:%M")
    
    opcoes_hora = ''
    for h in horarios:
        opcoes_hora += f'<option value="{h}">{h}</option>'
        
    opcoes_mesa = ''
    for mesa, cap in mesas.items():
        opcoes_mesa += f'<option value="{mesa}">{mesa} (Até {cap} pessoas)</option>'

    return f'''
    <h2>Reserva de Mesa</h2>
    <form method="POST" action="/reservar">
        Nome: <input name="nome" required><br><br>
        Telefone: <input name="telefone" value="{telefone}" required><br><br>
        Mesa: <select name="mesa" required>{opcoes_mesa}</select><br><br>
        Data: <input type="date" name="data" id="data_input" min="{data_hoje}" required><br><br>
        Hora: <select name="hora" required id="hora">{opcoes_hora}</select><br><br>
        Pessoas: <input type="number" name="pessoas" min="1" max="10" required><br><br>
        <button type="submit" id="btn_reservar">Reservar</button>
    </form>
    <div id="aviso" style="color: red; font-weight: bold; margin-top: 10px;"></div>
    <script>
    const dataInput = document.getElementById('data_input');
    const horaSelect = document.getElementById('hora');
    const aviso = document.getElementById('aviso');
    const btnReservar = document.getElementById('btn_reservar');
    const dataHoje = "{data_hoje}";
    const horaAgora = "{hora_agora}";
    
    function atualizarHorarios() {{
        const selectedData = dataInput.value;
        if (!selectedData) return;
        
        const dateObj = new Date(selectedData + "T00:00:00");
        const diaSemana = dateObj.getDay();
        
        let fechado = false;
        if (diaSemana === 1 || diaSemana === 2) fechado = true;
        
        if (fechado) {{
            aviso.innerText = "Estamos fechados de segunda e terça-feira.";
            btnReservar.disabled = true;
            horaSelect.innerHTML = '<option value="">Fechado</option>';
            return;
        }} else {{
            aviso.innerText = "";
            btnReservar.disabled = false;
        }}
        
        let opcoesHtml = '';
        const todosHorarios = {horarios};
        
        todosHorarios.forEach(h => {{
            let hNum = parseInt(h.split(':')[0]);
            let mNum = parseInt(h.split(':')[1]);
            
            let permitido = false;
            if (diaSemana >= 3 && diaSemana <= 5) {{
                if ((hNum >= 17 && hNum <= 21) || (hNum === 22 && mNum === 0)) permitido = true;
            }}
            else if (diaSemana === 6 || diaSemana === 0) {{
                if ((hNum >= 12 && hNum <= 15) || (hNum === 16 && mNum === 0) || 
                    (hNum >= 18 && hNum <= 21) || (hNum === 22 && mNum === 0)) permitido = true;
            }}
            
            if (permitido) {{
                let text = h;
                let disabled = false;
                if (selectedData === dataHoje && h < horaAgora) {{
                    disabled = true;
                    text = h + " (passado)";
                }}
                if (disabled) {{
                    opcoesHtml += `<option value="${{h}}" disabled>${{text}}</option>`;
                }} else {{
                    opcoesHtml += `<option value="${{h}}">${{text}}</option>`;
                }}
            }}
        }});
        
        if (opcoesHtml === '') {{
            opcoesHtml = '<option value="">Fora do horário final</option>';
            btnReservar.disabled = true;
        }}
        horaSelect.innerHTML = opcoesHtml;
    }}
    
    dataInput.addEventListener('change', atualizarHorarios);
    if(dataInput.value) atualizarHorarios();
    </script>
    '''

@app.route('/reservar', methods=['POST'])
def reservar():
    dados = request.form
    try:
        data_obj = datetime.strptime(dados['data'], "%Y-%m-%d").date()
        data_iso = str(data_obj)
    except ValueError:
        return "<h3>Data inválida.</h3>"

    sucesso, resultado = alocar_mesas(
        data_iso, 
        dados['hora'], 
        int(dados['pessoas']),
        dados['mesa']
    )
    
    if sucesso:
        mesas_string = ",".join(resultado)
        return f'''
        <h2>Confirme sua Reserva</h2>
        <p><strong>Nome:</strong> {dados['nome']}</p>
        <p><strong>Telefone:</strong> {dados['telefone']}</p>
        <p><strong>Data:</strong> {dados['data']}</p>
        <p><strong>Hora:</strong> {dados['hora']}</p>
        <p><strong>Pessoas:</strong> {dados['pessoas']}</p>
        <p><strong>Mesas Alocadas:</strong> {mesas_string}</p>
        
        <form method="POST" action="/efetivar_reserva">
            <input type="hidden" name="nome" value="{dados['nome']}">
            <input type="hidden" name="telefone" value="{dados['telefone']}">
            <input type="hidden" name="data" value="{data_iso}">
            <input type="hidden" name="hora" value="{dados['hora']}">
            <input type="hidden" name="pessoas" value="{dados['pessoas']}">
            <input type="hidden" name="mesas" value="{mesas_string}">
            <button type="submit" style="background-color: green; color: white; padding: 10px;">Confirmar Agendamento</button>
            <a href="/" style="margin-left: 15px; color: red; text-decoration: none;">Cancelar e Voltar</a>
        </form>
        '''
    else:
        return f"<h3>Erro na reserva: {resultado}</h3> <br><a href='/'>Tentar Novamente</a>"

@app.route('/efetivar_reserva', methods=['POST'])
def efetivar_reserva():
    dados = request.form
    nome = dados['nome']
    telefone = dados['telefone']
    data = dados['data']
    hora = dados['hora']
    pessoas = int(dados['pessoas'])
    mesas_alocadas = dados['mesas'].split(',')
    
    status = "reservado"
    conn = sqlite3.connect('reservas.db')
    cursor = conn.cursor()
    
    for m in mesas_alocadas:
        cursor.execute('''
            INSERT INTO reservas (nome, telefone, data, hora, pessoas, mesa, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nome, telefone, data, hora, pessoas, m, status))
        
    conn.commit()
    conn.close()
    
    return "<h3>Reserva confirmada com sucesso! Você receberá nosso contato.</h3> <br><a href='/'>Início</a>"

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