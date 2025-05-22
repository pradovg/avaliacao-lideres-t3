import os
import sys
import csv
import datetime
from collections import defaultdict
import tempfile
import pathlib
import json
import io

# Configuração de ambiente para Render
os.environ['HOME'] = tempfile.gettempdir()
os.environ['USERPROFILE'] = tempfile.gettempdir()

# Corrigindo Path.home() no Render
original_home = pathlib.Path.home
def patched_home():
    return pathlib.Path(tempfile.gettempdir())
pathlib.Path.home = patched_home

# Imports externos
import gspread
from google.oauth2 import service_account
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response

# PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import cm

# App Flask
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Constantes e caminhos
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
GOOGLE_SHEET_ID = '1gmIdczCSqAwJasvOOoY1rsz1bW0L0dfcFA_8020eF18'
GOOGLE_SHEET_WORKSHEET_NAME = 'RespostasAvaliacao'
os.makedirs(DATA_DIR, exist_ok=True)

EVALUATIONS_CSV_HEADER = [
    'data_avaliacao', 'nome_lider', 'area_atuacao', 'semana_referencia',
    'produtividade_time', 'qualidade_entregas', 'gestao_absenteismo', 'turnover_equipe',
    'clima_engajamento', 'comunicacao_eficaz', 'lideranca_influencia',
    'resolucao_problemas', 'gestao_conflitos', 'delegacao_desenvolvimento',
    'percentual_atendimento_esteira', 'observacoes_adicionais'
]
CRITERIA_FIELDS = EVALUATIONS_CSV_HEADER[4:14]

# --- Autenticação Google Sheets ---
def get_gsheet_client():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_info = json.loads(os.environ.get("GOOGLE_CREDS_JSON", "{}"))
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"[Google Auth Error] {e}")
        return None

# --- Helpers ---
def get_evaluations_from_gsheet():
    client = get_gsheet_client()
    if not client:
        return []
    try:
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_SHEET_WORKSHEET_NAME)
        return sheet.get_all_records()
    except Exception as e:
        print(f"[Erro leitura planilha] {e}")
        return []

def format_date_for_display(date_str):
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except:
        return date_str

def is_date_in_range(date_str, start_date, end_date):
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        if start_date:
            if date_obj < datetime.datetime.strptime(start_date, '%Y-%m-%d'):
                return False
        if end_date:
            if date_obj > datetime.datetime.strptime(end_date, '%Y-%m-%d'):
                return False
        return True
    except:
        return True

def get_lideres_from_gsheet():
    client = get_gsheet_client()
    if not client:
        return []
    try:
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Lideres")
        all_values = sheet.get_all_records()
        return sorted(list(set(row['nome'] for row in all_values if row.get('nome'))))
    except:
        return []

# --- Autenticação simples ---
from functools import wraps
USERS = {
    'admin': 'shopee2025',
    'supervisor': 'shopeet3',
    'manual': '12345678'
}

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        if u in USERS and USERS[u] == p:
            session['logged_in'], session['username'] = True, u
            return redirect(request.args.get('next') or url_for('index'))
        else:
            error = 'Credenciais inválidas.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Rota principal de formulário ---
@app.route('/')
@login_required
def index():
    lideres = get_lideres_from_gsheet()
    return render_template('avaliacao_form.html', lideres=lideres)

# --- Geração do PDF ---
@app.route('/gerar_pdf', methods=['POST'])
@login_required
def gerar_pdf():
    nome_lider = request.form.get("lider_nome", "Líder")
    data_inicio = request.form.get("data_inicio")
    data_fim = request.form.get("data_fim")
    periodo = f"{data_inicio} a {data_fim}" if data_inicio or data_fim else "Período completo"

    # Buscar avaliações
    avaliacoes = get_evaluations_from_gsheet()
    observacoes = [
        row["observacoes_adicionais"]
        for row in avaliacoes
        if row.get("nome_lider") == nome_lider and row.get("observacoes_adicionais")
        and is_date_in_range(row.get("data_avaliacao"), data_inicio, data_fim)
    ]
    texto_obs = "\n".join(f"- {o}" for o in observacoes) if observacoes else "Sem observações registradas."

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    logo_path = os.path.join(app.static_folder, "img", "shopee_logo.png")
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        c.drawImage(logo, x=2*cm, y=height - 5*cm, width=6*cm, height=3.5*cm, mask='auto')

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 6.5*cm, "Relatório de Desempenho Semanal")

    c.setFont("Helvetica", 12)
    c.drawString(2*cm, height - 8*cm, f"Líder Avaliado: {nome_lider}")
    c.drawString(2*cm, height - 8.8*cm, f"Período: {periodo}")

    c.rect(2*cm, height - 15*cm, width - 4*cm, 6*cm)
    c.drawCentredString(width / 2, height - 12*cm, "[Gráficos Aqui]")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, height - 16.5*cm, "Observações:")
    c.setFont("Helvetica", 11)
    text = c.beginText(2*cm, height - 17.5*cm)
    text.setLeading(14)
    for linha in texto_obs.splitlines():
        text.textLine(linha)
    c.drawText(text)

    y_ass = 4*cm
    c.line(2*cm, y_ass, 7*cm, y_ass)
    c.drawString(2*cm, y_ass - 0.6*cm, "Supervisor")

    c.line(8*cm, y_ass, 13*cm, y_ass)
    c.drawString(8*cm, y_ass - 0.6*cm, "Testemunha")

    c.line(14*cm, y_ass, width - 2*cm, y_ass)
    c.drawString(14*cm, y_ass - 0.6*cm, nome_lider)

    c.showPage()
    c.save()
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=relatorio_{nome_lider}.pdf'
    return response

# --- Dashboard ---
@app.route('/leader_dashboard')
@login_required
def leader_dashboard_select():
    todos_lideres = get_lideres_from_gsheet()
    selected_lider_nome = request.args.get('lider_nome')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    evaluations_lider = []
    radar_chart_data_lider = {'labels': [], 'data': []}
    periodo_filtro = None

    if data_inicio and data_fim:
        periodo_filtro = f"{format_date_for_display(data_inicio)} a {format_date_for_display(data_fim)}"
    elif data_inicio:
        periodo_filtro = f"A partir de {format_date_for_display(data_inicio)}"
    elif data_fim:
        periodo_filtro = f"Até {format_date_for_display(data_fim)}"

    if selected_lider_nome:
        all_evaluations = get_evaluations_from_gsheet()
        evaluations_lider = [
            row for row in all_evaluations
            if row.get('nome_lider') == selected_lider_nome
            and is_date_in_range(row.get('data_avaliacao'), data_inicio, data_fim)
        ]
        if evaluations_lider:
            criterio_somas = {c: 0 for c in CRITERIA_FIELDS}
            for row in evaluations_lider:
                for c in CRITERIA_FIELDS:
                    try:
                        criterio_somas[c] += int(row.get(c, 0))
                    except ValueError:
                        pass
            radar_chart_data_lider['labels'] = CRITERIA_FIELDS
            radar_chart_data_lider['data'] = [
                round(criterio_somas[c] / len(evaluations_lider), 2) for c in CRITERIA_FIELDS
            ]

    return render_template(
        'leader_dashboard.html',
        todos_lideres=todos_lideres,
        selected_lider_nome=selected_lider_nome,
        evaluations_lider=evaluations_lider,
        radar_chart_data_lider=radar_chart_data_lider,
        data_inicio=data_inicio,
        data_fim=data_fim,
        periodo_filtro=periodo_filtro
    )
