import sqlite3
from datetime import datetime, timedelta

DB = "reservas.db"

mesas = {
    "Interna 1": 2,
    "Interna 2": 2,
    "Interna 3": 2,
    "Interna 4": 3,
    "Externa 1": 3,
    "Externa 2": 3,
    "Balcão": 3
}

def alocar_mesas(data, hora, pessoas, mesa_escolhida):
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
            return False, "Horário não permitido para o dia escolhido."
    except Exception:
        pass

    conn = sqlite3.connect(DB)
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
        if pessoas_restantes <= 0: break
        mesas_alocadas.append(m)
        pessoas_restantes -= mesas[m]

    if pessoas_restantes > 0:
        return False, "Não há mesas suficientes."

    return True, mesas_alocadas

def efetivar_reserva(nome, telefone, data, hora, pessoas, mesas_alocadas):
    status = "reservado"
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    
    for m in mesas_alocadas:
        cursor.execute('''
            INSERT INTO reservas (nome, telefone, data, hora, pessoas, mesa, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nome, telefone, data, hora, pessoas, m, status))
        
    conn.commit()
    conn.close()
    return True

def teste_agrupamento():
    hoje = datetime.now()
    dias_ate_sabado = (5 - hoje.weekday()) % 7 
    if dias_ate_sabado == 0: dias_ate_sabado = 7
    data_teste = (hoje + timedelta(days=dias_ate_sabado)).date().isoformat()
    hora_teste = "19:00"
    
    print(f"Testando aglomerado para {data_teste} às {hora_teste}\n")
    
    # 5 pessoas na Interna 1 (tem 2 de cap). Faltam 3 lugares.
    sucesso, res = alocar_mesas(data_teste, hora_teste, 5, "Interna 1")
    print(f"Alocando 5 pessoas em Interna 1: {sucesso} -> Mesas alocadas: {res}")
    
    if sucesso:
        efetivar_reserva("Cliente Teste", "123", data_teste, hora_teste, 5, res)
        print("Registros gravados no banco.")
        
    # Testar colisão logo em seguida
    sucesso_col, res_col = alocar_mesas(data_teste, hora_teste, 2, "Interna 2")
    if not sucesso_col:
        print(f"Esperado: Interna 2 está ocupada por ter sido tragada no agrupamento acima. Mensagem: {res_col}")

if __name__ == "__main__":
    teste_agrupamento()