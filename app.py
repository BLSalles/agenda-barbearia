import streamlit as st
import sqlite3
from sqlite3 import Connection
from datetime import datetime, date, time
import pandas as pd

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
]

BUSINESS_START = time(9, 0)
BUSINESS_END = time(19, 0)
WORKING_DAYS = {0, 1, 2, 3, 4, 5}

ADMIN_USER = "admin"
ADMIN_PASS = "1234"


def get_conn() -> Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
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
    cur = conn.cursor()
    cur.execute(
        """SELECT 1 FROM appointments
           WHERE barber_id=? AND appt_date=? AND appt_time=? AND status!='CANCELLED'""",
        (barber_id, appt_date.isoformat(), appt_time.strftime("%H:%M"))
    )
    found = cur.fetchone() is not None
    conn.close()
    return found


def save_appointment(name, email, phone, barber_id, services, total, appt_date, appt_time):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO appointments
           (client_name, client_email, client_phone, barber_id, services, total, appt_date, appt_time, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            name, email, phone, barber_id,
            ", ".join(services), total,
            appt_date.isoformat(), appt_time.strftime('%H:%M'),
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()


def calculate_total(services):
    return sum(SERVICES[s] for s in services)


def barber_by_id(bid):
    for b in BARBERS:
        if b["id"] == bid:
            return b
    return None


# Streamlit setup
st.set_page_config(page_title="Barbearia", layout="centered")
init_db()

st.title("💈 Sistema de Agendamentos da Barbearia")

opcao = st.selectbox("Escolha o tipo de acesso:", ["Cliente", "Admin"])

# CLIENTE
if opcao == "Cliente":
    st.header("📅 Agendar um horário")
    with st.form("form_agendamento"):
        name = st.text_input("Nome completo")
        email = st.text_input("Email (opcional)")
        phone = st.text_input("WhatsApp do cliente", placeholder="55119XXXXXXXX")
        barber_id = st.selectbox(
            "Escolha o barbeiro",
            [b["id"] for b in BARBERS],
            format_func=lambda x: barber_by_id(x)["name"]
        )
        services = st.multiselect("Serviços", list(SERVICES.keys()))
        appt_date = st.date_input("Data", min_value=date.today())
        appt_time = st.time_input("Horário", time(9, 0))
        submitted = st.form_submit_button("Confirmar agendamento")

    if submitted:
        if not name:
            st.error("Digite o nome do cliente.")
        elif not services:
            st.error("Selecione pelo menos um serviço.")
        else:
            if appt_date.weekday() not in WORKING_DAYS:
                st.error("Atendemos somente de segunda a sábado.")
            elif not (BUSINESS_START <= appt_time <= BUSINESS_END):
                st.error("Horário fora do expediente.")
            elif find_conflict(barber_id, appt_date, appt_time):
                st.error("Esse horário já está ocupado.")
            else:
                total = calculate_total(services)
                save_appointment(name, email, phone, barber_id, services, total, appt_date, appt_time)
                st.success("Agendamento criado com sucesso!")
                st.info(f"Total: R$ {total:.2f}")


# ADMIN
elif opcao == "Admin":
    st.header("🔐 Login Administrativo")
    user = st.text_input("Usuário")
    pw = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if user == ADMIN_USER and pw == ADMIN_PASS:
            st.success("Login autorizado!")

            # 🔧 Carrega corretamente o DataFrame com nomes das colunas
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM appointments")
            rows = cur.fetchall()
            columns = [col[0] for col in cur.description]
            df = pd.DataFrame(rows, columns=columns)
            conn.close()

            if df.empty:
                st.info("Nenhum agendamento registrado.")
            else:
                # KPIs
                st.subheader("📊 Dashboard Geral")
                st.metric("💰 Lucro total", f"R$ {df['total'].sum():.2f}")
                st.metric("✂️ Total de agendamentos", len(df))

                # Total por barbeiro
                st.subheader("💈 Total por Barbeiro")
                total_por_barber = df.groupby("barber_id")["total"].sum().reset_index()
                total_por_barber["barber"] = total_por_barber["barber_id"].apply(
                    lambda x: barber_by_id(x)["name"]
                )
                st.dataframe(total_por_barber[["barber", "total"]])

                # Quantidade por barbeiro
                st.subheader("📅 Agendamentos por Barbeiro")
                qtd_por_barber = df.groupby("barber_id")["id"].count().reset_index()
                qtd_por_barber["barber"] = qtd_por_barber["barber_id"].apply(
                    lambda x: barber_by_id(x)["name"]
                )
                qtd_por_barber = qtd_por_barber.rename(columns={"id": "agendamentos"})
                st.dataframe(qtd_por_barber[["barber", "agendamentos"]])

                # Tabela geral
                st.subheader("📄 Lista completa")
                st.dataframe(df)

        else:
            st.error("Usuário ou senha incorretos.")
