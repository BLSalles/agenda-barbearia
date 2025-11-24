# NOVA VERSÃO — App Barbearia com WhatsApp via Link e Portal do Barbeiro

import streamlit as st
import sqlite3
from sqlite3 import Connection
from datetime import datetime, date, time
import os
from typing import List

# Banco de dados
DB_PATH = "appointments.db"

SERVICES = {
    "Corte": 35.0,
    "Barba": 20.0,
    "Penteado": 40.0,
    "Progressiva": 120.0,
    "Corte + Barba": 50.0
}

BARBERS = [
    {"id": 1, "name": "Bruno", "phone": "5511956996426"},
    {"id": 2, "name": "Carlos", "phone": "55119xxxxxxx"},
]

BUSINESS_START = time(9, 0)
BUSINESS_END = time(19, 0)
WORKING_DAYS = {0, 1, 2, 3, 4, 5}  # segunda a sábado


def get_conn() -> Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        client_email TEXT,
        client_phone TEXT,
        barber_id INTEGER NOT NULL,
        services TEXT NOT NULL,
        total REAL NOT NULL,
        appt_date TEXT NOT NULL,
        appt_time TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING'
    )
    """)
    conn.commit()
    conn.close()


def find_conflict(barber_id, appt_date, appt_time):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM appointments WHERE barber_id=? AND appt_date=? AND appt_time=? AND status!='CANCELLED'",
              (barber_id, appt_date.isoformat(), appt_time.strftime("%H:%M")))
    found = c.fetchone() is not None
    conn.close()
    return found


def save_appointment(name, email, phone, barber_id, services, total, appt_date, appt_time):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO appointments (client_name, client_email, client_phone, barber_id, services, total, appt_date, appt_time, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (name, email, phone, barber_id, ", ".join(services), total,
               appt_date.isoformat(), appt_time.strftime('%H:%M'), datetime.utcnow().isoformat()))
    appt_id = c.lastrowid
    conn.commit()
    conn.close()
    return appt_id


def calculate_total(services: List[str]):
    return sum(SERVICES[s] for s in services)


def barber_by_id(bid):
    for b in BARBERS:
        if b["id"] == bid:
            return b
    return None


st.set_page_config(page_title="Agendamento Barbearia", layout="centered")
init_db()

st.title("Barbearia — Sistema de Agendamentos")

menu = st.sidebar.selectbox("Menu", ["Agendar", "Agenda do Barbeiro", "Admin"])

# ------------------------------------------------------
# 1 — Tela de Agendamentos
# ------------------------------------------------------
if menu == "Agendar":
    st.header("Criar Agendamento")

    with st.form("form_appt"):
        name = st.text_input("Nome completo")
        email = st.text_input("Email (opcional)")
        phone = st.text_input("WhatsApp do cliente", placeholder="55119XXXXXXXX")

        barber_id = st.selectbox(
            "Escolha o barbeiro", [b["id"] for b in BARBERS],
            format_func=lambda x: barber_by_id(x)["name"]
        )

        services = st.multiselect("Serviços", list(SERVICES.keys()))
        appt_date = st.date_input("Data", min_value=date.today())
        appt_time = st.time_input("Horário", time(9, 0))

        submitted = st.form_submit_button("Confirmar agendamento")

    if submitted:
        if not name:
            st.error("Informe o nome do cliente.")
        elif not services:
            st.error("Escolha ao menos um serviço.")
        else:
            if appt_date.weekday() not in WORKING_DAYS:
                st.error("Atendemos somente de segunda a sábado.")
            elif not (BUSINESS_START <= appt_time <= BUSINESS_END):
                st.error("Horário fora do expediente.")
            elif find_conflict(barber_id, appt_date, appt_time):
                st.error("Esse horário já está ocupado para esse barbeiro.")
            else:
                total = calculate_total(services)
                appt_id = save_appointment(name, email, phone, barber_id, services, total, appt_date, appt_time)

                st.success(f"Agendamento criado com sucesso! ID {appt_id}")
                st.info(f"Total: R$ {total:.2f}")

                # LINK DE WHATSAPP PARA O BARBEIRO
                barber = barber_by_id(barber_id)
                msg_text = f"Novo agendamento!%0ACliente: {name}%0AServiços: {', '.join(services)}%0AData: {appt_date}%0AHora: {appt_time.strftime('%H:%M')}%0ATotal: R$ {total:.2f}"
                wa_link = f"https://wa.me/{barber['phone']}?text={msg_text}"

                st.markdown(f"### Notificar o barbeiro")
                st.markdown(f"[Enviar WhatsApp para {barber['name']}]({wa_link})", unsafe_allow_html=True)


# ------------------------------------------------------
# 2 — Portal do Barbeiro
# ------------------------------------------------------
elif menu == "Agenda do Barbeiro":
    st.header("Consulta da Agenda — Barbeiro")

    barber_id = st.selectbox(
        "Selecione o barbeiro", [b["id"] for b in BARBERS],
        format_func=lambda x: barber_by_id(x)["name"]
    )

    conn = get_conn()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM appointments WHERE barber_id=? ORDER BY appt_date, appt_time", (barber_id,)).fetchall()
    conn.close()

    if rows:
        st.subheader("Próximos horários")
        for r in rows:
            st.write(f"**{r['appt_date']} – {r['appt_time']}** | {r['client_name']} | Serviços: {r['services']} | R$ {r['total']:.2f}")
    else:
        st.info("Nenhum agendamento para este barbeiro.")


# ------------------------------------------------------
# 3 — Painel Admin
# ------------------------------------------------------
elif menu == "Admin":
    st.header("Painel Administrativo")

    conn = get_conn()
    rows = conn.execute("SELECT * FROM appointments ORDER BY appt_date, appt_time").fetchall()

    if rows:
        import pandas as pd
        df = pd.DataFrame(rows)
        st.dataframe(df)
    else:
        st.info("Nenhum agendamento cadastrado.")

    conn.close()
