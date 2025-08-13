# Sistema de Digitação e Gerenciamento de Trabalhos Acadêmicos

## Visão Geral

Sistema web desenvolvido em Python com Flask para ensino de digitação e gerenciamento de trabalhos acadêmicos, com perfis distintos para professores e alunos.

## Funcionalidades Principais

### Para Professores
- Cadastro de usuários
- Gerenciamento de frases para digitação
- Criação e atribuição de trabalhos
- Avaliação de entregas
- Compartilhamento de arquivos/links
- Visualização de ranking

### Para Alunos
- Jogo de digitação com níveis variados
- Acesso a materiais compartilhados
- Entrega de trabalhos
- Acompanhamento de desempenho
- Ranking de classificação

## Tecnologias Utilizadas

- **Backend**: Python 3, Flask, SQLAlchemy
- **Frontend**: HTML5, CSS3, JavaScript
- **Banco de Dados**: SQLite
- **Comunicação**: Socket.IO

## Estrutura do Projeto

```
sistema-digitação/
├── app.py                # Aplicação principal
├── static/
│   └── style.css         # Estilos CSS
├── templates/
│   ├── base.html         # Template base
│   ├── arquivos.html     # Arquivos compartilhados
│   ├── avaliar_entrega.html # Avaliação de trabalhos
│   ├── cadastro.html     # Cadastro de usuários
│   ├── entregas_aluno.html # Entregas (aluno)
│   ├── entregas_professor.html # Entregas (professor)
│   ├── equipes.html      # Gerenciamento de equipes
│   ├── frases.html       # Gerenciamento de frases
│   ├── index.html        # Página inicial
│   ├── jogo.html         # Jogo de digitação
│   ├── login.html        # Página de login
│   ├── notas.html        # Gerenciamento de notas
│   ├── perfil.html       # Perfil do usuário
│   ├── ranking.html      # Ranking de desempenho
│   ├── trabalhos.html    # Gerenciamento de trabalhos
│   └── upload.html       # Upload de arquivos/links
├── uploads/              # Armazenamento de arquivos
└── db.sqlite             # Banco de dados
```

## Requisitos do Sistema (requirements.txt)

```
Flask==2.0.1
Flask-SQLAlchemy==2.5.1
Flask-Login==0.5.0
Flask-SocketIO==5.1.1
python-socketio==5.5.2
python-engineio==4.3.1
Werkzeug==2.0.1
pytz==2021.3
```

## Modelos do Banco de Dados

Principais entidades:
- User (usuários)
- Arquivo (materiais compartilhados)
- Desempenho (resultados de digitação)
- FraseDigitação (frases para exercícios)
- Equipe (grupos de alunos)
- Trabalho (atividades acadêmicas)
- Entrega (submissões de trabalhos)
- Avaliacao (avaliações dos professores)

## Como Executar

### Pré-requisitos
- Python 3.7+
- pip

### Instalação
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### Configuração
Crie um arquivo `.env` com:
```env
SECRET_KEY=sua_chave_secreta_aleatoria
DATABASE_URL=sqlite:///db.sqlite
```

### Execução
```bash
python app.py
```
Acesse: `http://localhost:5000`

## Autor
Wabney Campos Dos Santos - wabney55santos92@gmail.com