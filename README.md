
# Sistema de Avaliação de Líderes - Turno T3

Este sistema permite o registro semanal de avaliações de líderes operacionais com envio automático para o Google Sheets, além de dashboards e gestão de dados.

## Como executar localmente

1. Crie um ambiente virtual:
```
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
```

2. Instale as dependências:
```
pip install -r requirements.txt
```

3. Execute o servidor:
```
python main.py
```

## Implantação online

Recomenda-se o uso da plataforma [Render.com](https://render.com/) para publicar este app Flask.

- Comando de inicialização: `gunicorn main:app`
- Python Version: 3.10+
- Configure a variável de ambiente GOOGLE_CREDS_JSON com o conteúdo do seu `google_creds.json` se não for usar como arquivo
