from multiprocessing.pool import MapResult
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from flask_socketio import SocketIO, emit
import random
import time
import pytz

cuiaba_tz = pytz.timezone('America/Cuiaba')
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'xlsx', 'docx'}

db = SQLAlchemy(app)
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Especifica a rota de login
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info"
# Tabela de associação para muitos-para-muitos entre User e Equipe
equipe_membros = db.Table('equipe_membros',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('equipe_id', db.Integer, db.ForeignKey('equipe.id'), primary_key=True)
)

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))  # 'aluno' ou 'professor'
    
    # Modifique esta linha - mude o backref para 'equipe_membros'
    equipes = db.relationship('Equipe', 
                            secondary='equipe_membros',
                            backref=db.backref('equipe_membros', lazy=True))
class Arquivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    path = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz)) 
    is_link = db.Column(db.Boolean, default=False)
    description = db.Column(db.String(200)) 

class Desempenho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    wpm = db.Column(db.Float)
    accuracy = db.Column(db.Float)
    difficulty = db.Column(db.Integer)
    errors = db.Column(db.Integer, default=0)  # Novo campo
    date = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz))
    user = db.relationship('User', backref=db.backref('desempenhos', lazy=True))

class FraseDigitação(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(500), nullable=False)
    nivel_dificuldade = db.Column(db.Integer, nullable=False)  # 1-4
    criado_por = db.Column(db.Integer, db.ForeignKey('user.id'))
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz))

class Nota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    professor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    valor = db.Column(db.Float)
    descricao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz))
    aluno = db.relationship('User', foreign_keys=[user_id], backref=db.backref('notas_recebidas', lazy=True))
    professor = db.relationship('User', foreign_keys=[professor_id], backref=db.backref('notas_dadas', lazy=True))

class GameResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)
    level = db.Column(db.Integer, nullable=False)
    wpm = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float, nullable=False)
    errors = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    time_played = db.Column(db.Integer, nullable=False)  # em segundos
    date_played = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(cuiaba_tz))
    
    user = db.relationship('User', backref=db.backref('game_results', lazy=True))

class Aluno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ativo = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref=db.backref('aluno_info', lazy=True))


# Tabela de associação (mantenha no topo do arquivo)
equipe_trabalho = db.Table('equipe_trabalho',
    db.Column('equipe_id', db.Integer, db.ForeignKey('equipe.id'), primary_key=True),
    db.Column('trabalho_id', db.Integer, db.ForeignKey('trabalho.id'), primary_key=True),
    db.Column('data_atribuicao', db.DateTime, default=datetime.now))

# Modelo Equipe
class Equipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz))
    # Relacionamento com trabalhos (usando back_populates em vez de backref)
    trabalhos = db.relationship('Trabalho', secondary='equipe_trabalho', back_populates='equipes')
    #trabalhos = db.relationship('Trabalho', secondary=equipe_trabalho, back_populates='equipes')
    
    # Atualize a propriedade para usar o novo backref
    @property
    def membros(self):
        return self.equipe_membros
    
    @property
    def is_individual(self):
        return len(self.equipe_membros) == 1
    
    def get_aluno_individual(self):
        if self.is_individual:
            return self.equipe_membros[0]
        return None
    
# Modelo Trabalho
class Trabalho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz))
    data_entrega = db.Column(db.DateTime)
    professor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Relacionamentos
    professor = db.relationship('User', backref=db.backref('trabalhos_criados', lazy=True))
    equipes = db.relationship('Equipe', secondary=equipe_trabalho, back_populates='trabalhos')

class Entrega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trabalho_id = db.Column(db.Integer, db.ForeignKey('trabalho.id'), nullable=False)
    equipe_id = db.Column(db.Integer, db.ForeignKey('equipe.id'), nullable=False)
    data_entrega = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz))
    comentarios = db.Column(db.Text)
    arquivo_id = db.Column(db.Integer, db.ForeignKey('arquivo.id'))
    nota = db.Column(db.Float)  # Adicione este campo
    feedback = db.Column(db.Text)  # Adicione este campo
    
    trabalho = db.relationship('Trabalho', backref=db.backref('entregas', lazy=True))
    equipe = db.relationship('Equipe', backref=db.backref('entregas', lazy=True))
    arquivo = db.relationship('Arquivo')

class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entrega_id = db.Column(db.Integer, db.ForeignKey('entrega.id'), nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nota = db.Column(db.Float, nullable=False)
    comentarios = db.Column(db.Text)
    data_avaliacao = db.Column(db.DateTime, default=lambda: datetime.now(cuiaba_tz))
    # Relacionamentos
    entrega = db.relationship('Entrega', backref=db.backref('avaliacoes', lazy=True))
    professor = db.relationship('User', backref=db.backref('avaliacoes_feitas', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Rotas de autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Se já estiver logado, redireciona para index
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next') or url_for('index')
            return redirect(next_page)
        flash('Usuário ou senha incorretos.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Rotas principais
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/frases', methods=['GET', 'POST'])
@login_required
def gerenciar_frases():
    if current_user.role != 'professor':
        flash('Apenas professores podem gerenciar frases.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        texto = request.form.get('texto')
        nivel = int(request.form.get('nivel'))
        
        if not texto or len(texto) < 5:
            flash('Frase muito curta. Mínimo 5 caracteres.', 'error')
        else:
            nova_frase = FraseDigitação(
                texto=texto,
                nivel_dificuldade=nivel,
                criado_por=current_user.id
            )
            db.session.add(nova_frase)
            db.session.commit()
            flash('Frase adicionada com sucesso!', 'success')
    
    frases = FraseDigitação.query.order_by(FraseDigitação.nivel_dificuldade).all()
    return render_template('frases.html', frases=frases)

@app.route('/frases/remover/<int:id>')
@login_required
def remover_frase(id):
    if current_user.role != 'professor':
        flash('Apenas professores podem remover frases.', 'error')
        return redirect(url_for('index'))
    
    frase = FraseDigitação.query.get(id)
    if frase:
        db.session.delete(frase)
        db.session.commit()
        flash('Frase removida com sucesso!', 'success')
    return redirect(url_for('gerenciar_frases'))

@app.route('/perfil')
@login_required
def perfil():
    # Obter equipes do aluno e trabalhos atribuídos
    equipes_com_trabalhos = []
    for equipe in current_user.equipes:
        trabalhos = equipe.trabalhos
        for trabalho in trabalhos:
            equipes_com_trabalhos.append({
                'equipe': equipe,
                'trabalho': trabalho,
                'entrega': Entrega.query.filter_by(
                    trabalho_id=trabalho.id,
                    equipe_id=equipe.id
                ).first()
            })
    
    return render_template('perfil.html', 
                         equipes_com_trabalhos=equipes_com_trabalhos,
                         user=current_user)

@app.route('/arquivos')
@login_required
def arquivos():
    files = Arquivo.query.all()
    return render_template('arquivos.html', files=files)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if current_user.role != 'professor':
        flash('Apenas professores podem enviar arquivos.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Verifica se é um link
        if 'link' in request.form and request.form['link']:
            link = request.form['link']
            description = request.form.get('description', 'Link compartilhado')
            
            if not (link.startswith('http://') or link.startswith('https://')):
                flash('O link deve começar com http:// ou https://', 'error')
                return redirect(url_for('upload_file'))
            
            try:
                new_file = Arquivo(
                    filename=description,
                    path=link,
                    user_id=current_user.id,
                    is_link=True,
                    description=description  # Adicionado aqui
                )
                db.session.add(new_file)
                db.session.commit()
                flash('Link compartilhado com sucesso!', 'success')
                return redirect(url_for('arquivos'))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao salvar o link: {str(e)}', 'error')
                return redirect(url_for('upload_file'))
        
        # Processamento de arquivo
        elif 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # Obter a descrição do formulário ou usar o nome do arquivo como padrão
                description = request.form.get('description', filename)
                
                new_file = Arquivo(
                    filename=filename,
                    path=file_path,
                    user_id=current_user.id,
                    is_link=False,
                    description=description  # Adicionado aqui
                )
                db.session.add(new_file)
                db.session.commit()
                flash('Arquivo enviado com sucesso!', 'success')
                return redirect(url_for('arquivos'))
        
        flash('Nenhum arquivo ou link válido fornecido.', 'error')
    
    return render_template('upload.html')

@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    file = Arquivo.query.get(file_id)
    return send_from_directory(directory=app.config['UPLOAD_FOLDER'], path=file.filename, as_attachment=True)

@app.route('/notas', methods=['GET', 'POST'])
@login_required
def gerenciar_notas():
    if current_user.role != 'professor':
        flash('Apenas professores podem gerenciar notas.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        valor = float(request.form.get('valor'))
        descricao = request.form.get('descricao')
        
        nova_nota = Nota(
            user_id=aluno_id,
            professor_id=current_user.id,
            valor=valor,
            descricao=descricao
        )
        db.session.add(nova_nota)
        db.session.commit()
        flash('Nota adicionada com sucesso!', 'success')
    
    alunos = User.query.filter_by(role='aluno').all()
    return render_template('notas.html', alunos=alunos)

@app.route('/jogo')
@login_required
def jogo():
    return render_template('jogo.html')

@app.route('/cadastro', methods=['GET', 'POST'])
@login_required
def cadastro():
    if current_user.role != 'professor':
        flash('Apenas professores podem cadastrar usuários.')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Usuário já existe.')
        else:
            new_user = User(username=username, password=generate_password_hash(password), role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('Usuário cadastrado com sucesso!')
    return render_template('cadastro.html')
@app.route('/save_results', methods=['POST'])
def save_results():
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Usuário não autenticado'})
    
    data = request.get_json()
    
    try:
        # Crie um novo registro no banco de dados
        new_result = GameResult(
            user_id=current_user.id,
            difficulty=data['difficulty'],
            level=data['level'],
            wpm=data['wpm'],
            accuracy=data['accuracy'],
            errors=data['errors'],
            score=data['score'],
            time_played=data['time_played'],
            date_played=datetime.utcnow()
        )
        
        db.session.add(new_result)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Resultados salvos com sucesso!'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    
@socketio.on('save_game_results')
def handle_save_results(data):
    try:
        if not current_user.is_authenticated:
            emit('results_saved', {'success': False, 'error': 'Usuário não autenticado'})
            return
        
        # Criar novo registro no banco de dados
        new_result = GameResult(
            user_id=current_user.id,
            difficulty=data['difficulty'],
            level=data['level'],
            wpm=data['wpm'],
            accuracy=data['accuracy'],
            errors=data['errors'],
            score=data['score'],
            time_played=data['time_played'],
            date_played=datetime.utcnow()
        )
        
        db.session.add(new_result)
        db.session.commit()
        
        # Também salvar no modelo Desempenho para compatibilidade
        new_performance = Desempenho(
            user_id=current_user.id,
            wpm=data['wpm'],
            accuracy=data['accuracy'],
            difficulty=data['difficulty'],
            errors=data['errors'],
            date=datetime.utcnow()
        )
        db.session.add(new_performance)
        db.session.commit()
        
        emit('results_saved', {'success': True})
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar resultados do jogo: {str(e)}")
        emit('results_saved', {'success': False, 'error': str(e)})
@app.route('/ranking')
@login_required
def ranking():
    # Obter todos os usuários com seus melhores desempenhos
    usuarios = User.query.all()
    ranking_data = []
    
    for usuario in usuarios:
        melhor_desempenho = Desempenho.query.filter_by(user_id=usuario.id)\
                              .order_by(Desempenho.wpm.desc())\
                              .first()
        if melhor_desempenho:
            ranking_data.append({
                'username': usuario.username,
                'wpm': melhor_desempenho.wpm,
                'accuracy': melhor_desempenho.accuracy,
                'difficulty': melhor_desempenho.difficulty,
                'date': melhor_desempenho.date
            })
    
    # Ordenar por WPM (maior primeiro)
    ranking_data.sort(key=lambda x: x['wpm'], reverse=True)
    
    return render_template('ranking.html', ranking_data=ranking_data)

# Jogo de digitação via SocketIO
@socketio.on('get_phrase')
def handle_get_phrase(data):
    difficulty = data.get('difficulty', 1)
    level = data.get('level', 1)
    
    # Fórmula para aumentar complexidade com o nível
    min_words = 3 + (difficulty - 1) * 2 + (level // 5)
    max_words = min_words + 2 + (level // 10)
    
    # Buscar frases no banco com número de palavras adequado
    frases = FraseDigitação.query.filter(
        FraseDigitação.nivel_dificuldade == difficulty,
        func.length(FraseDigitação.texto.split()) >= min_words,
        func.length(FraseDigitação.texto.split()) <= max_words
    ).all()
    
    if frases:
        frase = random.choice(frases).texto
    else:
        # Fallback para frases padrão
        frases_padrao = [
            "Aprender a digitar rápido é essencial",
            "A prática constante leva à perfeição",
            "Digitar sem olhar para o teclado é importante",
            "Velocidade e precisão são fundamentais",
            "Erros são oportunidades de aprendizado"
        ]
        frase = random.choice(frases_padrao)
    
    socketio.emit('new_phrase', {'phrase': frase}, room=request.sid)

@socketio.on('submit_game')
def handle_submit_game(data):
    if current_user.is_authenticated:
        try:
            novo_desempenho = Desempenho(
                user_id=current_user.id,
                wpm=float(data.get('wpm', 0)),
                accuracy=float(data.get('accuracy', 0)),
                difficulty=int(data.get('difficulty', 1)),
                errors=int(data.get('errors', 0)),
                date=datetime.utcnow()
            )
            db.session.add(novo_desempenho)
            db.session.commit()
            print(f"Dados salvos: WPM={novo_desempenho.wpm}, Precisão={novo_desempenho.accuracy}")
        except Exception as e:
            print(f"Erro ao salvar desempenho: {str(e)}")
            db.session.rollback()

@app.template_filter('esta_no_prazo')
def esta_no_prazo(data_entrega):
    if not data_entrega:
        return False
    agora = datetime.now(cuiaba_tz)
    return data_entrega.replace(tzinfo=cuiaba_tz) > agora

# Adicione esta linha antes de executar o app
app.jinja_env.filters['esta_no_prazo'] = esta_no_prazo

# Rotas para gerenciar trabalhos e entregas
@app.route('/trabalhos/novo', methods=['GET', 'POST'])
@login_required
def novo_trabalho():
    if current_user.role != 'professor':
        flash('Apenas professores podem criar trabalhos.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        data_entrega_str = request.form.get('data_entrega')
        
        try:
            data_entrega = datetime.strptime(data_entrega_str, '%Y-%m-%dT%H:%M')
        except:
            data_entrega = None
        
        if not titulo or not descricao:
            flash('Preencha todos os campos obrigatórios.', 'error')
        else:
            novo_trabalho = Trabalho(
                titulo=titulo,
                descricao=descricao,
                data_entrega=data_entrega,
                professor_id=current_user.id
            )
            db.session.add(novo_trabalho)
            db.session.commit()
            flash('Trabalho criado com sucesso!', 'success')
            return redirect(url_for('listar_trabalhos'))
    
    return render_template('novo_trabalho.html')

@app.route('/entregas/<int:trabalho_id>', methods=['GET', 'POST'])
@login_required
def entregas_aluno(trabalho_id):
    trabalho = Trabalho.query.get_or_404(trabalho_id)
    equipe = Equipe.query.join(equipe_membros).filter(
        equipe_membros.c.user_id == current_user.id,
        Equipe.trabalhos.any(id=trabalho_id)
    ).first()

    if not equipe:
        flash('Você não está em uma equipe para este trabalho.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        arquivo = request.files.get('arquivo')
        comentarios = request.form.get('comentarios', '')
        
        if arquivo and allowed_file(arquivo.filename):
            filename = secure_filename(arquivo.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            arquivo.save(filepath)
            
            novo_arquivo = Arquivo(
                filename=filename,
                path=filepath,
                user_id=current_user.id,
                description=f'Entrega para {trabalho.titulo}'
            )
            db.session.add(novo_arquivo)
            db.session.flush()
            
            nova_entrega = Entrega(
                trabalho_id=trabalho.id,
                equipe_id=equipe.id,
                comentarios=comentarios,
                arquivo_id=novo_arquivo.id
            )
            db.session.add(nova_entrega)
            db.session.commit()
            
            flash('Entrega realizada com sucesso!', 'success')
            return redirect(url_for('entregas_aluno', trabalho_id=trabalho.id))
        else:
            flash('Arquivo inválido ou não enviado.', 'error')

    entregas = Entrega.query.filter_by(
        trabalho_id=trabalho.id,
        equipe_id=equipe.id
    ).order_by(Entrega.data_entrega.desc()).all()

    return render_template('entregas_aluno.html', 
                        trabalho=trabalho,
                        equipe=equipe,
                        entregas=entregas)
    
@app.route('/equipes/excluir/<int:equipe_id>', methods=['POST'])
@login_required
def excluir_equipe(equipe_id):
    if current_user.role != 'professor':
        flash('Apenas professores podem excluir equipes.', 'error')
        return redirect(url_for('index'))

    equipe = Equipe.query.get(equipe_id)
    
    if equipe:
        try:
            # Remove primeiro os membros da equipe
            db.session.execute(equipe_membros.delete().where(equipe_membros.c.equipe_id == equipe_id))
            
            # Remove os trabalhos vinculados
            equipe.trabalhos = []
            
            # Remove as entregas associadas
            Entrega.query.filter_by(equipe_id=equipe_id).delete()
            
            # Finalmente remove a equipe
            db.session.delete(equipe)
            db.session.commit()
            
            flash('Equipe excluída com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao excluir equipe: {str(e)}', 'error')
    else:
        flash('Equipe não encontrada.', 'error')

    return redirect(url_for('gerenciar_equipes'))

@app.route('/avaliar/<int:entrega_id>', methods=['GET', 'POST'])
@login_required
def avaliar_entrega(entrega_id):
    if current_user.role != 'professor':
        flash('Apenas professores podem avaliar entregas.', 'error')
        return redirect(url_for('index'))
    
    entrega = Entrega.query.get_or_404(entrega_id)
    
    if request.method == 'POST':
        nota = float(request.form.get('nota'))
        feedback = request.form.get('feedback', '')
        
        # Atualiza a entrega com nota e feedback
        entrega.nota = nota
        entrega.feedback = feedback
        db.session.commit()
        
        flash('Avaliação registrada com sucesso!', 'success')
        return redirect(url_for('gerenciar_entregas', trabalho_id=entrega.trabalho_id))
    
    return render_template('avaliar_entrega.html', entrega=entrega)

@app.route('/atribuir_trabalho', methods=['POST'])
@login_required
def atribuir_trabalho():
    if current_user.role != 'professor':
        flash('Apenas professores podem atribuir trabalhos', 'error')
        return redirect(url_for('index'))
    
    trabalho_id = request.form.get('trabalho_id')
    equipe_id = request.form.get('equipe_id')
    
    if not trabalho_id or not equipe_id:
        flash('Selecione um trabalho e uma equipe', 'error')
        return redirect(url_for('listar_trabalhos'))
    
    trabalho = Trabalho.query.get(trabalho_id)
    equipe = Equipe.query.get(equipe_id)
    
    if trabalho and equipe:
        if trabalho not in equipe.trabalhos:
            equipe.trabalhos.append(trabalho)
            db.session.commit()
            flash(f'Trabalho "{trabalho.titulo}" atribuído à equipe "{equipe.nome}"!', 'success')
        else:
            flash('Esta equipe já possui este trabalho', 'info')
    else:
        flash('Trabalho ou equipe não encontrados', 'error')
    
    return redirect(url_for('gerenciar_trabalhos'))
@socketio.on('connect')
def handle_connect():
    print('Cliente conectado:', request.sid)

@socketio.on('start_game')
def handle_start_game(data):
    difficulty = data.get('difficulty', 1)
    
    # Adicione esta rota para fornecer frases aleatórias
@app.route('/get_random_phrase/<int:difficulty>')
@login_required
def get_random_phrase(difficulty):
    frase = FraseDigitação.query.filter_by(nivel_dificuldade=difficulty).order_by(func.random()).first()
    if frase:
        return jsonify({
            'texto': frase.texto,
            'dificuldade': frase.nivel_dificuldade
        })
    return jsonify({'texto': 'Digite esta frase padrão quando não há frases no banco.', 'dificuldade': 1})

# Modifique o socketio.on('get_phrase') para:
@socketio.on('get_phrase')
def handle_get_phrase(data):
    difficulty = data.get('difficulty', 1)
    level = data.get('level', 1)
    
    # Buscar frases no banco com a dificuldade selecionada
    frase = FraseDigitação.query.filter_by(nivel_dificuldade=difficulty).order_by(func.random()).first()
    
    if not frase:
        # Frases padrão de fallback
        frases_padrao = [
            "A prática leva à perfeição na digitação.",
            "Digitar rápido e sem erros é essencial hoje em dia.",
            "A velocidade de digitação melhora com exercícios diários.",
            "Foque na precisão primeiro, depois na velocidade.",
            "Mantenha os dedos na posição correta para digitar melhor."
        ]
        frase_texto = random.choice(frases_padrao)
    else:
        frase_texto = frase.texto
    
    socketio.emit('new_phrase', {'phrase': frase_texto}, room=request.sid)
@socketio.on('submit_text')
def handle_submit_text(data):
    frase_original = data['original']
    texto_digitado = data['text']
    tempo_decorrido = data['time']
    dificuldade = data.get('difficulty', 1)
    
    # Calcular precisão
    corretos = 0
    for i in range(min(len(frase_original), len(texto_digitado))):
        if frase_original[i] == texto_digitado[i]:
            corretos += 1
    
    precisao = (corretos / len(frase_original)) * 100 if frase_original else 100
    
    # Calcular WPM (palavras por minuto)
    palavras = len(texto_digitado.split())
    wpm = (palavras / tempo_decorrido) * 60 if tempo_decorrido > 0 else 0
    
    # Salvar desempenho
    if current_user.is_authenticated:
        novo_desempenho = Desempenho(
            user_id=current_user.id,
            wpm=wpm,
            accuracy=precisao,
            difficulty=dificuldade
        )
        db.session.add(novo_desempenho)
        db.session.commit()
    
    socketio.emit('game_result', {
        'wpm': wpm,
        'accuracy': precisao
    }, room=request.sid)
# Rotas para gerenciamento de equipes
@app.route('/equipes', methods=['GET', 'POST'])
@login_required
def gerenciar_equipes():
    if current_user.role != 'professor':
        flash('Apenas professores podem gerenciar equipes.', 'error')
        return redirect(url_for('index'))
    
    # Garantir que todos os alunos tenham registro na tabela Aluno
    alunos_users = User.query.filter_by(role='aluno').all()
    for user in alunos_users:
        if not Aluno.query.filter_by(user_id=user.id).first():
            novo_aluno = Aluno(user_id=user.id, ativo=True)
            db.session.add(novo_aluno)
    db.session.commit()
    
    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'alternar_status':
            aluno_id = request.form.get('aluno_id')
            aluno = Aluno.query.filter_by(user_id=aluno_id).first()
            if aluno:
                aluno.ativo = not aluno.ativo
                db.session.commit()
                flash(f'Status do aluno atualizado com sucesso!', 'success')
                return redirect(url_for('gerenciar_equipes'))
        
        elif acao == 'sortear':
            num_equipes = int(request.form.get('num_equipes', 0))
            num_membros = int(request.form.get('num_membros', 0))
            
            if num_equipes <= 0 or num_membros <= 0:
                flash('Número de equipes e membros por equipe deve ser maior que zero.', 'error')
                return redirect(url_for('gerenciar_equipes'))
            
            # Obter alunos ativos
            alunos_ativos = User.query.join(Aluno).filter(
                User.role == 'aluno',
                Aluno.ativo == True
            ).all()
            
            if not alunos_ativos:
                flash('Nenhum aluno ativo para sortear.', 'error')
                return redirect(url_for('gerenciar_equipes'))
            
            # Verificar se o sorteio é possível
            total_alunos = len(alunos_ativos)
            total_vagas = num_equipes * num_membros
            
            if total_alunos < total_vagas:
                flash(f'Não há alunos suficientes. {total_alunos} alunos ativos para {total_vagas} vagas.', 'error')
                return redirect(url_for('gerenciar_equipes'))
            
            # Embaralhar alunos
            random.shuffle(alunos_ativos)
            
            # Criar equipes
            for i in range(num_equipes):
                equipe = Equipe(nome=f'Equipe {i+1}')
                db.session.add(equipe)
                db.session.flush()  # Para obter o ID da equipe
                
                # Adicionar membros à equipe
                inicio = i * num_membros
                fim = inicio + num_membros
                for aluno in alunos_ativos[inicio:fim]:
                    equipe.membros.append(aluno)
            
            db.session.commit()
            flash(f'{num_equipes} equipes sorteadas com sucesso!', 'success')
            return redirect(url_for('gerenciar_equipes'))
        
        elif acao == 'limpar_equipes':
            # Limpar todas as equipes
            db.session.execute(equipe_membros.delete())
            Equipe.query.delete()
            db.session.commit()
            flash('Todas as equipes foram removidas.', 'success')
            return redirect(url_for('gerenciar_equipes'))
    
    # Obter lista de alunos com seus status
    alunos_com_status = db.session.query(User, Aluno)\
        .join(Aluno, User.id == Aluno.user_id)\
        .filter(User.role == 'aluno')\
        .all()
    
    equipes = Equipe.query.all()
    
    return render_template('equipes.html', 
                         alunos=alunos_com_status, 
                         equipes=equipes)

@app.route('/trabalhos', methods=['GET', 'POST'])
@login_required
def gerenciar_trabalhos():
    if current_user.role != 'professor':
        flash('Apenas professores podem gerenciar trabalhos.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        
        if not titulo or not descricao:
            flash('Preencha todos os campos obrigatórios.', 'error')
        else:
            novo_trabalho = Trabalho(
                titulo=titulo,
                descricao=descricao,
                professor_id=current_user.id
            )
            db.session.add(novo_trabalho)
            db.session.commit()
            flash('Trabalho adicionado com sucesso!', 'success')
    
    # Obter todos os trabalhos
    trabalhos = Trabalho.query.filter_by(professor_id=current_user.id).all()
    
    # Obter equipes sem trabalhos atribuídos
    equipes_sem_trabalho = Equipe.query.filter(~Equipe.trabalhos.any()).all()
    
    # Obter equipes com trabalhos atribuídos (com informações de trabalhos)
    equipes_com_trabalho = db.session.query(Equipe, Trabalho)\
        .join(equipe_trabalho, Equipe.id == equipe_trabalho.c.equipe_id)\
        .join(Trabalho, Trabalho.id == equipe_trabalho.c.trabalho_id)\
        .filter(Trabalho.professor_id == current_user.id)\
        .all()
    
    # Obter alunos sem trabalhos
    alunos_sem_trabalho = User.query.filter(
        User.role == 'aluno',
        ~User.equipes.any(Equipe.trabalhos.any())
    ).all()
    
    return render_template('trabalhos.html',
                         trabalhos=trabalhos,
                         equipes_sem_trabalho=equipes_sem_trabalho,
                         equipes_com_trabalho=equipes_com_trabalho,
                         alunos_sem_trabalho=alunos_sem_trabalho)

# Adicione após as rotas existentes de trabalhos

@app.route('/trabalhos/atribuir_aluno', methods=['POST'])
@login_required
def atribuir_trabalho_aluno():
    if current_user.role != 'professor':
        flash('Apenas professores podem atribuir trabalhos.', 'error')
        return redirect(url_for('index'))

    trabalho_id = request.form.get('trabalho_id')
    aluno_id = request.form.get('aluno_id')
    
    if not trabalho_id or not aluno_id:
        flash('Dados incompletos.', 'error')
        return redirect(url_for('listar_trabalhos'))

    trabalho = Trabalho.query.get(trabalho_id)
    aluno = User.query.get(aluno_id)
    
    if not trabalho or not aluno:
        flash('Trabalho ou aluno não encontrado.', 'error')
        return redirect(url_for('listar_trabalhos'))

    # Verifica se o aluno já tem equipe para este trabalho
    equipe_existente = None
    for equipe in aluno.equipes:
        if trabalho in equipe.trabalhos:
            equipe_existente = equipe
            break
    
    if equipe_existente:
        flash(f'O aluno já está na equipe {equipe_existente.nome} que tem este trabalho.', 'warning')
    else:
        # Cria equipe individual para o aluno
        nova_equipe = Equipe(
            nome=f"Individual - {aluno.username}",
            data_criacao=datetime.now(cuiaba_tz)
        )
        nova_equipe.membros.append(aluno)
        nova_equipe.trabalhos.append(trabalho)
        db.session.add(nova_equipe)
        db.session.commit()
        flash(f'Trabalho atribuído com sucesso para {aluno.username}!', 'success')
    
    return redirect(url_for('gerenciar_trabalhos'))

@app.route('/trabalhos/remover_atribuicao/<int:trabalho_id>/<int:equipe_id>', methods=['POST'])
@login_required
def remover_atribuicao(trabalho_id, equipe_id):
    if current_user.role != 'professor':
        flash('Apenas professores podem remover atribuições.', 'error')
        return redirect(url_for('index'))
    
    trabalho = Trabalho.query.get_or_404(trabalho_id)
    equipe = Equipe.query.get_or_404(equipe_id)
    
    if trabalho in equipe.trabalhos:
        equipe.trabalhos.remove(trabalho)
        db.session.commit()
        flash('Atribuição removida com sucesso!', 'success')
    else:
        flash('Esta equipe não tinha este trabalho atribuído.', 'info')
    
    return redirect(url_for('gerenciar_trabalhos'))

@app.route('/trabalhos/remover_atribuicao_aluno/<int:trabalho_id>/<int:aluno_id>', methods=['POST'])
@login_required
def remover_atribuicao_aluno(trabalho_id, aluno_id):
    if current_user.role != 'professor':
        flash('Apenas professores podem remover atribuições.', 'error')
        return redirect(url_for('index'))
    
    trabalho = Trabalho.query.get(trabalho_id)
    aluno = User.query.get(aluno_id)
    
    # Encontre a equipe individual do aluno para este trabalho
    equipe = Equipe.query.join(equipe_membros).filter(
        equipe_membros.c.user_id == aluno_id,
        Equipe.trabalhos.any(id=trabalho_id)
    ).first()
    
    if equipe and trabalho in equipe.trabalhos:
        equipe.trabalhos.remove(trabalho)
        db.session.commit()
        flash('Atribuição removida com sucesso!', 'success')
    else:
        flash('Este aluno não tinha este trabalho atribuído.', 'info')
    
    return redirect(url_for('listar_trabalhos'))

@app.route('/trabalhos/<int:trabalho_id>/entregas')
@login_required
def gerenciar_entregas(trabalho_id):
    trabalho = Trabalho.query.get_or_404(trabalho_id)
    
    if current_user.role == 'professor':
        # Para professores: mostrar todas as entregas do trabalho
        entregas = Entrega.query.filter_by(trabalho_id=trabalho_id).all()
        equipes = Equipe.query.join(equipe_trabalho).filter(
            equipe_trabalho.c.trabalho_id == trabalho_id
        ).all()
        
        return render_template('entregas_professor.html',
                            trabalho=trabalho,
                            equipes=equipes,
                            entregas=entregas)
    else:
        # Para alunos: redirecionar para sua entrega
        equipe = Equipe.query.join(equipe_membros).filter(
            equipe_membros.c.user_id == current_user.id,
            Equipe.trabalhos.any(id=trabalho_id)
        ).first()
        
        if not equipe:
            flash('Você não está em uma equipe para este trabalho.', 'error')
            return redirect(url_for('index'))
            
        return redirect(url_for('entregas_aluno', trabalho_id=trabalho_id))
    
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Criar usuário professor automaticamente se não existir
        professor = User.query.filter_by(username='wabney_santos').first()
        if not professor:
            hashed_password = generate_password_hash('000000')
            new_professor = User(
                username='professor', 
                password=hashed_password, 
                role='professor'
            )
            db.session.add(new_professor)
            db.session.commit()
            print("Usuário professor criado automaticamente")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)