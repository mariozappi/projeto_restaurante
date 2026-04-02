import sqlite3
from datetime import datetime, timedelta

# =========================
# Banco usado pelo sistema
# =========================
DB = "reservas.db"  # mesmo banco do Flask

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
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mesa FROM reservas
        WHERE data=? AND hora=? AND status IN ('reservado','confirmado')
    ''', (data, hora))
    ocupadas = [r[0] for r in cursor.fetchall()]
    conn.close()

    for mesa, capacidade in mesas.items():
        if mesa not in ocupadas and pessoas <= capacidade:
            return mesa
    return None

def agendar_reserva(nome, telefone, data, hora, pessoas):
    mesa_disponivel = buscar_mesa_disponivel(data, hora, pessoas)
    if mesa_disponivel:
        mesa = mesa_disponivel
        status = "reservado"
    else:
        mesa = None
        status = "espera"

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reservas (nome, telefone, data, hora, pessoas, mesa, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, telefone, data, hora, pessoas, mesa, status))
    conn.commit()
    conn.close()
    return mesa, status

# =========================
# Teste: preencher todas as mesas
# =========================
def teste_reservas_cheias():
    data_teste = (datetime.now() + timedelta(days=1)).date().isoformat()  # amanhã
    hora_teste = "15:00"
    nomes = ["Cliente 1", "Cliente 2", "Cliente 3", "Cliente 4", "Cliente 5", "Cliente 6", "Cliente 7", "Cliente 8"]

    print(f"Testando reservas para {data_teste} às {hora_teste}\n")
    for i, nome in enumerate(nomes):
        mesa, status = agendar_reserva(nome, f"9999999{i}", data_teste, hora_teste, 1)
        print(f"{nome} -> Mesa: {mesa}, Status: {status}")

if __name__ == "__main__":
    teste_reservas_cheias()