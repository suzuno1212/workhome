from flask import Flask, render_template, request, session, jsonify, url_for, redirect, current_app
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_session_captcha import FlaskSessionCaptcha
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import datetime
import pymysql
import time  # この行を追加
from sqlalchemy.sql import func
from functools import wraps

# PyMySQLをMySQLdbとして使用するための設定
pymysql.install_as_MySQLdb()

# Flaskアプリケーションの初期化
app = Flask(__name__)
load_dotenv('workhome.env')  # workhome.envファイルから環境変数を読み込む
wsgi_app = app.wsgi_app

# データベースへの接続
def test_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            auth_plugin='mysql_native_password'  # この行を追加
        )
        if connection.is_connected():
            connection.close()
            return True
    except Error as e:
        print(f"Error: {e}")
        return False
    return False

# アプリケーションの設定
app.config.update({
    'SECRET_KEY': os.urandom(24),
    'SESSION_TYPE': 'sqlalchemy',
    'SQLALCHEMY_DATABASE_URI': f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}?charset=utf8mb4",
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'PERMANENT_SESSION_LIFETIME': datetime.timedelta(minutes=30),
    'SESSION_PERMANENT': True,
    'SESSION_REFRESH_EACH_REQUEST': True,
    'CAPTCHA_ENABLE': True,
    'CAPTCHA_LENGTH': 5,
    'CAPTCHA_WIDTH': 160,
    'CAPTCHA_HEIGHT': 60,
    # メール設定を追加
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': 'suzuno01212@gmail.com',
    'MAIL_PASSWORD': os.getenv('MAIL_PASSWORD'),
    'MAIL_DEFAULT_SENDER': 'suzuno01212@gmail.com',
    'SECURITY_PASSWORD_SALT': os.getenv('SECURITY_PASSWORD_SALT', os.urandom(24).hex())
})

# データベースの初期化
db = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db

# テーブルモデルの定義
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    registered_on = db.Column(db.DateTime, nullable=False)
    confirmed = db.Column(db.Boolean, nullable=True, default=False)
    confirmed_on = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # リレーションシップ
    consultations = db.relationship('Consultation', backref='user', lazy=True)
    consultation_responses = db.relationship('ConsultationResponse', backref='user', lazy=True)

class Inquiry(db.Model):
    __tablename__ = 'inquiries'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=func.now())
    status = db.Column(
        db.Enum('未対応', '対応中', '対応済み'),
        nullable=False,
        default='未対応'
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    response_notes = db.Column(db.Text, nullable=True)
    email_response = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=func.now())
    updated_by = db.Column(db.String(100), nullable=True)
    inquiry_type_care = db.Column(db.Boolean, nullable=False, default=False)
    inquiry_type_facility = db.Column(db.Boolean, nullable=False, default=False)
    inquiry_type_cost = db.Column(db.Boolean, nullable=False, default=False)
    inquiry_type_other = db.Column(db.Boolean, nullable=False, default=False)

# 相談モデルの定義
class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_paths = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=func.now())
    status = db.Column(db.Enum('未回答', '回答済み', '対応中'), nullable=False, default='未回答')
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # リレーションシップ
    responses = db.relationship('ConsultationResponse', backref='consultation', lazy=True,
                              cascade='all, delete-orphan')

# 回答モデルの定義
class ConsultationResponse(db.Model):
    __tablename__ = 'consultation_responses'
    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', onupdate='CASCADE', ondelete='SET NULL'), nullable=True)
    response_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())
    is_active = db.Column(db.Boolean, nullable=False, default=True)

# セッションの初期化
Session(app)

# CAPTCHAの初期化
captcha = FlaskSessionCaptcha(app)

# メールの初期化
mail = Mail(app)

# アップロードフォルダの設定
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ここにトークン生成と確認の関数を追加
def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
        return email
    except:
        return False

def create_user(email, password):
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = connection.cursor()
        
        query = """
        INSERT INTO users (email, password, registered_on, confirmed, is_active)
        VALUES (%s, %s, %s, %s, %s)
        """
        values = (email, password, datetime.datetime.now(), False, True)
        
        cursor.execute(query, values)
        connection.commit()
        return True
        
    except Error as e:
        print(f"Error: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_user_by_id(user_id):
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = connection.cursor(dictionary=True)  # 結果を辞書形式で取得
        
        query = "SELECT * FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        
        return user
        
    except Error as e:
        print(f"Error: {e}")
        return None
        
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('member_home'))
    return render_template('index.html', active_page='home')

@app.route('/inquiry', methods=['GET', 'POST'])
def inquiry():
    error = None
    form_data = {
        'name': '',
        'email': '',
        'phone': '',
        'message': '',
        'inquiry_type_care': False,
        'inquiry_type_facility': False,
        'inquiry_type_cost': False,
        'inquiry_type_other': False
    }

    if request.method == 'POST':
        form_data = {
            'name': request.form.get('name', ''),
            'email': request.form.get('email', ''),
            'phone': request.form.get('phone', ''),
            'message': request.form.get('message', ''),
            'inquiry_type_care': request.form.get('inquiry_type_care') == 'true',
            'inquiry_type_facility': request.form.get('inquiry_type_facility') == 'true',
            'inquiry_type_cost': request.form.get('inquiry_type_cost') == 'true',
            'inquiry_type_other': request.form.get('inquiry_type_other') == 'true'
        }

        try:
            if captcha.validate():
                connection = mysql.connector.connect(
                    host=os.getenv('DB_HOST'),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'),
                    database=os.getenv('DB_NAME')
                )
                cursor = connection.cursor()
                
                query = """
                INSERT INTO inquiries (
                    name, email, phone, message, status, is_active, created_at,
                    inquiry_type_care, inquiry_type_facility, inquiry_type_cost, inquiry_type_other
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)
                """
                values = (
                    form_data['name'],
                    form_data['email'],
                    form_data['phone'],
                    form_data['message'],
                    '未対応',
                    True,
                    form_data['inquiry_type_care'],
                    form_data['inquiry_type_facility'],
                    form_data['inquiry_type_cost'],
                    form_data['inquiry_type_other']
                )
                
                cursor.execute(query, values)
                connection.commit()
                return render_template('inquiry_success.html')
            else:
                error = "画像認証が正しくありません"
                captcha.generate()
        except Exception as e:
            app.logger.error(f"Error in inquiry submission: {str(e)}")
            error = "お問い合わせの送信に失敗しました"
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()

    # GET requestの場合やエラー時
    if request.method == 'GET':
        captcha.generate()

    return render_template('inquiry.html', 
                         error=error, 
                         form_data=form_data, 
                         active_page='inquiry')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if captcha.validate():
            email = request.form['email']
            password = request.form['password']
            
            try:
                connection = mysql.connector.connect(
                    host=os.getenv('DB_HOST'),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'),
                    database=os.getenv('DB_NAME')
                )
                cursor = connection.cursor(dictionary=True)
                
                # ユーザー検索
                query = "SELECT * FROM users WHERE email = %s"
                cursor.execute(query, (email,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password'], password):
                    if user['confirmed']:  # メール確認済みの場合のみログイン許可
                        session['user_id'] = user['id']
                        session['email'] = user['email']
                        return redirect(url_for('member_home'))
                    else:
                        error = "メールアドレスの確認が完了していません"
                else:
                    error = "メールアドレスまたはパスワードが正しくありません"
                    
            except Error as e:
                print(f"Error: {e}")
                error = "ログイン処理中にエラーが発生しました"
            finally:
                if 'connection' in locals() and connection.is_connected():
                    cursor.close()
                    connection.close()
        else:
            error = "画像認証が正しくありません"
            
    return render_template('login.html', error=error, active_page='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        if captcha.validate():
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            if password != confirm_password:
                error = "パスワードが一致しません"
            else:
                # メールアドレスの重複チェック
                connection = mysql.connector.connect(
                    host=os.getenv('DB_HOST'),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'),
                    database=os.getenv('DB_NAME')
                )
                cursor = connection.cursor()
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                existing_user = cursor.fetchone()
                cursor.close()
                connection.close()

                if existing_user:
                    error = "このメールアドレスは既に登録されています"
                else:
                    # ユーザー登録
                    hashed_password = generate_password_hash(password)
                    if create_user(email, hashed_password):
                        # 確認トークンの生成と送信
                        token = generate_confirmation_token(email)
                        confirm_url = url_for('confirm_email', token=token, _external=True)
                        html = render_template('email/confirm.html', confirm_url=confirm_url)
                        
                        msg = Message(
                            "メールアドレスの確認",
                            recipients=[email],
                            html=html
                        )
                        mail.send(msg)
                        return render_template('register_success.html')
                    else:
                        error = "登録に失敗しました"
        else:
            error = "画像認証が正しくありません"
    
    return render_template('register.html', error=error, active_page='register')

# ログイン要求デコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ログイン後のホームページ
@app.route('/member/home')
@login_required
def member_home():
    user = get_user_by_id(session['user_id'])
    return render_template('index_member.html', user=user, active_page='home')

# ログアウト
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

# 会員情報ページ
@app.route('/member/profile')
@login_required
def profile():
    user = get_user_by_id(session['user_id'])
    return render_template('profile.html', user=user, active_page='profile')

# 相談ページのルート
@app.route('/member/consultation')
@login_required
def consultation():
    # 相談履歴を取得（新しい順）
    consultations = Consultation.query.filter_by(
        user_id=session['user_id'],
        is_active=True
    ).order_by(Consultation.created_at.desc()).all()
    
    return render_template('consultation.html', 
                         consultations=consultations,
                         active_page='consultation')

# 新規相談の投稿
@app.route('/member/consultation/submit', methods=['POST'])
@login_required
def submit_consultation():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'ユーザー情報が見つかりません'
            }), 401

        content = request.form.get('content')
        if not content:
            return jsonify({
                'status': 'error',
                'message': '相談内容を入力してください'
            }), 400

        files = request.files.getlist('images')
        saved_paths = []

        # 画像の保存処理
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    new_filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    file.save(file_path)
                    saved_paths.append(f"uploads/{new_filename}")
                except Exception as e:
                    print(f"Error saving file: {str(e)}")
                    continue

        # 相談データを保存
        new_consultation = Consultation(
            user_id=user_id,
            content=content,
            image_paths=','.join(saved_paths) if saved_paths else None,
            status='未回答'
        )

        db.session.add(new_consultation)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': '相談を受け付けました'
        })

    except Exception as e:
        print(f"Error in submit_consultation: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': '相談の送信に失敗しました'
        }), 500

@app.route('/confirm/<token>')
def confirm_email(token):
    email = confirm_token(token)
    if not email:
        return render_template('confirm_error.html')
    
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = connection.cursor()
        
        # ユーザーの確認状態を更新
        update_query = """
        UPDATE users 
        SET confirmed = TRUE, confirmed_on = %s 
        WHERE email = %s AND confirmed = FALSE
        """
        cursor.execute(update_query, (datetime.datetime.now(), email))
        connection.commit()
        
        if cursor.rowcount > 0:
            return render_template('confirm_success.html')
        else:
            return render_template('already_confirmed.html')
            
    except Error as e:
        print(f"Error: {e}")
        return render_template('confirm_error.html')
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/refresh-captcha')
def refresh_captcha():
    try:
        # セッションをクリア
        session.pop('captcha', None)
        
        # 新しいCAPTCHAを生成
        captcha_html = captcha.generate()
        
        # セッションを確実に保存
        session.modified = True
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'captcha_html': captcha_html,
            'timestamp': datetime.datetime.now().timestamp()
        })
    except Exception as e:
        app.logger.error(f'CAPTCHA refresh error: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

"""
@app.route('/refresh-captcha')
def refresh_captcha():
    try:
        # セッションをクリア
        session.pop('captcha', None)
        
        # 新しいCAPTCHAを生成
        captcha_html = captcha.generate()
        
        # セッションを確実に保存
        session.modified = True
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'captcha_html': captcha_html,
            'timestamp': datetime.datetime.now().timestamp()
        })
    except Exception as e:
        app.logger.error(f'CAPTCHA refresh error: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
"""

if __name__ == '__main__':
    HOST = os.environ.get('SERVER_HOST', 'localhost')
    try:
        PORT = int(os.environ.get('SERVER_PORT', '5555'))
    except ValueError:
        PORT = 5555
    app.run(HOST, PORT, debug=True)