import os
import sys
import csv
import datetime
from collections import defaultdict
import json # For passing data to Chart.js
import tempfile
import pathlib

# Configuração para evitar erro de diretório home no ambiente de produção
os.environ['HOME'] = tempfile.gettempdir()
os.environ['USERPROFILE'] = tempfile.gettempdir()

# Monkey patch para Path.home()
original_home = pathlib.Path.home
def patched_home():
    return pathlib.Path(tempfile.gettempdir())
pathlib.Path.home = patched_home

import gspread
from google.oauth2.service_account import Credentials

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, render_template, request, redirect, url_for, flash

app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Ajuste de caminhos para funcionar tanto em desenvolvimento quanto em produção
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

EVALUATIONS_CSV_FILE_PATH = os.path.join(DATA_DIR, 'avaliacoes_lideres.csv')
LIDERES_CSV_FILE_PATH = os.path.join(DATA_DIR, 'lideres.csv')
GOOGLE_CREDS_PATH = os.path.join(BASE_DIR, 'google_creds.json')
GOOGLE_SHEET_ID = '1gmIdczCSqAwJasvOOoY1rsz1bW0L0dfcFA_8020eF18'
GOOGLE_SHEET_WORKSHEET_NAME = 'RespostasAvaliacao'

# Ensure the header includes the new field in the correct position
EVALUATIONS_CSV_HEADER = [
    'data_avaliacao', 'nome_lider', 'area_atuacao', 'semana_referencia',
    'produtividade_time', 'qualidade_entregas', 'gestao_absenteismo', 'turnover_equipe',
    'clima_engajamento', 'comunicacao_eficaz', 'lideranca_influencia', 
    'resolucao_problemas', 'gestao_conflitos', 'delegacao_desenvolvimento',
    'percentual_atendimento_esteira', # Corrected field name to match form and previous backend logic
    'observacoes_adicionais'
]
# CRITERIA_FIELDS are for the 0-10 radar chart, percentual_atendimento_esteira is separate
CRITERIA_FIELDS = EVALUATIONS_CSV_HEADER[4:14] 
LIDERES_CSV_HEADER = ['nome']

# --- Google Sheets Helper Functions ---
def get_gsheet_client():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"Error creating Google Sheets client: {e}")
        return None

def append_to_gsheet(data_row_dict):
    client = get_gsheet_client()
    if not client:
        return False
    try:
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_SHEET_WORKSHEET_NAME)
        header_row = sheet.row_values(1) 
        if not header_row or header_row != EVALUATIONS_CSV_HEADER:
            sheet.clear() 
            sheet.update('A1', [EVALUATIONS_CSV_HEADER])
            print("Google Sheet header reset/updated.")
        
        row_to_append = [data_row_dict.get(col, '') for col in EVALUATIONS_CSV_HEADER]
        sheet.append_row(row_to_append, value_input_option='USER_ENTERED')
        print("Data appended to Google Sheet successfully.")
        return True
    except gspread.exceptions.WorksheetNotFound:
        print(f"Worksheet '{GOOGLE_SHEET_WORKSHEET_NAME}' not found in Google Sheet.")
        return False
    except Exception as e:
        print(f"Error appending to Google Sheet: {e}")
        return False

def get_evaluations_from_gsheet():
    """Obter todas as avaliações do Google Sheets"""
    client = get_gsheet_client()
    if not client:
        print("Não foi possível conectar ao Google Sheets")
        return []
    
    try:
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_SHEET_WORKSHEET_NAME)
        # Obter todos os dados da planilha
        all_values = sheet.get_all_records()
        print(f"Dados obtidos do Google Sheets: {len(all_values)} registros")
        return all_values
    except Exception as e:
        print(f"Erro ao ler dados do Google Sheets: {e}")
        return []

def update_gsheet_after_deletion(evaluations):
    """Atualizar o Google Sheets após exclusão de um registro"""
    client = get_gsheet_client()
    if not client:
        return False
    
    try:
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_SHEET_WORKSHEET_NAME)
        # Limpar a planilha e reescrever todos os dados
        sheet.clear()
        sheet.update('A1', [EVALUATIONS_CSV_HEADER])
        if evaluations:
            rows_to_update = []
            for row in evaluations:
                rows_to_update.append([row.get(col, '') for col in EVALUATIONS_CSV_HEADER])
            sheet.update('A2', rows_to_update)
        print("Google Sheet atualizado após exclusão.")
        return True
    except Exception as e:
        print(f"Erro ao atualizar Google Sheet após exclusão: {e}")
        return False

def get_lideres_from_gsheet():
    """Obter lista de líderes do Google Sheets"""
    client = get_gsheet_client()
    if not client:
        print("Não foi possível conectar ao Google Sheets")
        return []
    
    try:
        # Tentar obter a planilha de líderes
        try:
            sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet('Lideres')
        except gspread.exceptions.WorksheetNotFound:
            # Se a planilha não existir, criar uma nova
            sheet = client.open_by_key(GOOGLE_SHEET_ID).add_worksheet(title='Lideres', rows=100, cols=1)
            sheet.update('A1', ['nome'])
            default_lideres = ['ADRIANA', 'EDUARDO', 'VANDERLEYA', 'LILIANE', 'BRUNA', 'FLAVIO', 'RODRIGO', 'RUDNEY', 'WELLINGTON']
            for i, lider in enumerate(default_lideres):
                sheet.update(f'A{i+2}', [[lider]])
        
        # Obter todos os líderes
        all_values = sheet.get_all_records()
        lideres = [row.get('nome') for row in all_values if row.get('nome')]
        
        # Se não houver líderes, usar lista padrão
        if not lideres:
            lideres = ['ADRIANA', 'EDUARDO', 'VANDERLEYA', 'LILIANE', 'BRUNA', 'FLAVIO', 'RODRIGO', 'RUDNEY', 'WELLINGTON']
        
        return sorted(list(set(lideres)))
    except Exception as e:
        print(f"Erro ao ler líderes do Google Sheets: {e}")
        return ['ADRIANA', 'EDUARDO', 'VANDERLEYA', 'LILIANE', 'BRUNA', 'FLAVIO', 'RODRIGO', 'RUDNEY', 'WELLINGTON']

def update_lideres_in_gsheet(lideres):
    """Atualizar lista de líderes no Google Sheets"""
    client = get_gsheet_client()
    if not client:
        return False
    
    try:
        try:
            sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet('Lideres')
        except gspread.exceptions.WorksheetNotFound:
            sheet = client.open_by_key(GOOGLE_SHEET_ID).add_worksheet(title='Lideres', rows=100, cols=1)
        
        # Limpar a planilha e reescrever todos os dados
        sheet.clear()
        sheet.update('A1', ['nome'])
        
        # Adicionar cada líder em uma linha
        for i, lider in enumerate(sorted(list(set(lideres)))):
            sheet.update(f'A{i+2}', [[lider]])
        
        print("Lista de líderes atualizada no Google Sheets.")
        return True
    except Exception as e:
        print(f"Erro ao atualizar líderes no Google Sheets: {e}")
        return False

# --- Leader Management Helper Functions ---
def get_lideres():
    # Usar a função que obtém líderes do Google Sheets
    return get_lideres_from_gsheet()

def save_lideres(lideres):
    # Usar a função que atualiza líderes no Google Sheets
    return update_lideres_in_gsheet(lideres)

# --- Date Helper Functions ---
def format_date_for_display(date_str):
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%d/%m/%Y')
    except:
        return date_str

def is_date_in_range(date_str, start_date, end_date):
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        
        if start_date:
            start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            if date_obj < start_date_obj:
                return False
                
        if end_date:
            end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            if date_obj > end_date_obj:
                return False
                
        return True
    except:
        return True  # If date parsing fails, include the record

# --- Flask Routes ---
# Configuração de autenticação básica
from functools import wraps
from flask import session, request

# Credenciais de usuário (em produção, isso deveria estar em um banco de dados)
USERS = {
    'admin': 'shopee2025',
    'supervisor': 'shopeet3'
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            error = 'Credenciais inválidas. Por favor, tente novamente.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    lideres = get_lideres()
    return render_template('avaliacao_form.html', lideres=lideres)

@app.route('/submit_evaluation', methods=['POST'])
@login_required
def submit_evaluation():
    if request.method == 'POST':
        data = {}
        for key in EVALUATIONS_CSV_HEADER:
            data[key] = request.form.get(key, '')

        if data.get('area_atuacao') != 'Esteiras':
            data['percentual_atendimento_esteira'] = '' 
        
        # Salvar diretamente no Google Sheets como fonte primária
        gsheet_success = append_to_gsheet(data)
        
        if gsheet_success:
            flash('Avaliação enviada com sucesso e salva no Google Sheets!', 'success')
            return redirect(url_for('success'))
        else:
            flash('Erro ao salvar a avaliação no Google Sheets. Verifique a conexão e tente novamente.', 'error')
            return redirect(url_for('index'))

@app.route('/success')
@login_required
def success():
    return render_template('success.html')

@app.route('/view_evaluations')
@login_required
def view_evaluations():
    # Obter avaliações diretamente do Google Sheets
    evaluations = get_evaluations_from_gsheet()
    if not evaluations:
        flash('Não foi possível carregar as avaliações do Google Sheets ou não há avaliações registradas.', 'warning')
    # Pass the full header list to the template for dynamic column generation
    return render_template('view_evaluations.html', evaluations=evaluations, header_fields=EVALUATIONS_CSV_HEADER)

@app.route('/delete_evaluation')
@login_required
def delete_evaluation():
    # Obter avaliações diretamente do Google Sheets
    evaluations = get_evaluations_from_gsheet()
    if not evaluations:
        flash('Não foi possível carregar as avaliações do Google Sheets ou não há avaliações registradas.', 'warning')
    return render_template('delete_evaluation.html', evaluations=evaluations)

@app.route('/delete_evaluation_record', methods=['POST'])
@login_required
def delete_evaluation_record():
    record_index = request.form.get('record_index')
    if record_index is None:
        flash('Índice de registro inválido.', 'error')
        return redirect(url_for('delete_evaluation'))
    
    try:
        record_index = int(record_index)
        
        # Obter avaliações diretamente do Google Sheets
        evaluations = get_evaluations_from_gsheet()
        
        if not evaluations:
            flash('Não foi possível carregar as avaliações do Google Sheets.', 'error')
            return redirect(url_for('delete_evaluation'))
        
        if record_index < 0 or record_index >= len(evaluations):
            flash('Índice de registro fora dos limites.', 'error')
            return redirect(url_for('delete_evaluation'))
        
        # Remover o registro
        deleted_record = evaluations.pop(record_index)
        
        # Atualizar o Google Sheets com a lista atualizada
        success = update_gsheet_after_deletion(evaluations)
        
        if success:
            flash(f'Avaliação de {deleted_record["nome_lider"]} do dia {deleted_record["data_avaliacao"]} excluída com sucesso!', 'success')
        else:
            flash('Erro ao atualizar o Google Sheets após exclusão. Tente novamente.', 'error')
        return redirect(url_for('delete_evaluation'))
    except Exception as e:
        print(f"Erro ao excluir avaliação: {e}")
        flash('Erro ao excluir a avaliação. Tente novamente.', 'error')
        return redirect(url_for('delete_evaluation'))




@app.route('/manage_lideres', methods=['GET'])
@login_required
def manage_lideres():
    lideres = get_lideres()
    return render_template('manage_lideres.html', lideres=lideres)

@app.route('/add_lider', methods=['POST'])
@login_required
def add_lider():
    nome_lider_adicionar = request.form.get('nome_lider_adicionar', '').strip().upper()
    if nome_lider_adicionar:
        lideres = get_lideres()
        if nome_lider_adicionar not in lideres:
            lideres.append(nome_lider_adicionar)
            save_lideres(lideres)
            flash(f'Líder "{nome_lider_adicionar}" adicionado com sucesso!', 'success')
        else:
            flash(f'Líder "{nome_lider_adicionar}" já existe.', 'warning')
    else:
        flash('Nome do líder não pode ser vazio.', 'error')
    return redirect(url_for('manage_lideres'))

@app.route('/remove_lider', methods=['POST'])
@login_required
def remove_lider():
    nome_lider_remover = request.form.get('nome_lider_remover', '').strip().upper()
    if nome_lider_remover:
        lideres = get_lideres()
        if nome_lider_remover in lideres:
            lideres.remove(nome_lider_remover)
            save_lideres(lideres)
            flash(f'Líder "{nome_lider_remover}" removido com sucesso!', 'success')
        else:
            flash(f'Líder "{nome_lider_remover}" não encontrado.', 'error')
    return redirect(url_for('manage_lideres'))

@app.route('/leader_dashboard', methods=['GET'])
@login_required
def leader_dashboard_select():
    todos_lideres = get_lideres()
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
        # Obter avaliações diretamente do Google Sheets
        all_evaluations = get_evaluations_from_gsheet()
        
        # Filtrar avaliações pelo líder selecionado
        evaluations_lider = [
            row for row in all_evaluations 
            if row.get('nome_lider') == selected_lide
(Content truncated due to size limit. Use line ranges to read in chunks)