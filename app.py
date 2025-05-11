from flask import Flask, render_template, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import time
import os
from extensions import login_manager
from werkzeug.utils import secure_filename
from PIL import Image
from forms import *
from models import *
from flask_caching import Cache
from datetime import datetime
import time

app = Flask(__name__)
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
login_manager.login_view = 'login'
db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('profile'))
        else:
            flash('Login failed. Check your credentials.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/profile')
@login_required
def profile():
    daily_stats = db.session.query(
        db.func.strftime('%Y-%m-%d', ReadingProgress.date).label('reading_date'),
        db.func.sum(ReadingProgress.pages_read).label('total_pages')
    ).filter(
        ReadingProgress.user_id == current_user.id
    ).group_by(
        db.func.strftime('%Y-%m-%d', ReadingProgress.date)
    ).order_by(
        db.func.strftime('%Y-%m-%d', ReadingProgress.date).desc()
    ).limit(30).all()

    chart_data = {
        'dates': [stat.reading_date for stat in daily_stats],
        'pages': [stat.total_pages for stat in daily_stats]
    }

    stats = {
        'books_read': ReadingProgress.query.filter_by(user_id=current_user.id).count(),
        'total_pages': sum(chart_data['pages']) if chart_data['pages'] else 0,
        'reviews_count': Review.query.filter_by(user_id=current_user.id).count()
    }

    return render_template('profile.html', stats=stats, chart_data=chart_data)


@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    form = BookForm()
    if form.validate_on_submit():
        try:
            cover_filename = None
            if form.cover.data and form.cover.data.filename != '':
                if allowed_file(form.cover.data.filename):
                    timestamp = int(time.time())
                    filename = secure_filename(form.cover.data.filename)
                    cover_filename = f"{current_user.id}_{timestamp}_{filename}"
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], cover_filename)

                    img = Image.open(form.cover.data.stream)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.thumbnail((800, 800))
                    img.save(save_path, quality=85)
                else:
                    flash('Допустимы только JPG, PNG, JPEG, GIF', 'error')
                    return redirect(request.url)

            book = Book(
                title=form.title.data,
                author=form.author.data,
                total_pages=form.total_pages.data,
                cover=cover_filename,
                user_id=current_user.id,
                created_at=datetime.now()
            )

            db.session.add(book)
            db.session.commit()
            flash('Книга успешно добавлена!', 'success')
            return redirect(url_for('books_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')

    return render_template('add_book.html', form=form)


@app.route('/books')
def books_list():
    books = Book.query.all()
    return render_template('books_list.html', books=books)


@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    reviews = Review.query.filter_by(book_id=book.id).order_by(Review.created_at.desc()).all()
    return render_template('book_detail.html', book=book, reviews=reviews)


@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        books = Book.query.filter(
            (Book.title.ilike(f'%{query}%')) |
            (Book.author.ilike(f'%{query}%'))
        ).all()
    else:
        books = []
    return render_template('search.html', books=books, query=query)


@app.route('/book/<int:book_id>/add_review', methods=['GET', 'POST'])
@login_required
def add_review(book_id):
    book = Book.query.get_or_404(book_id)
    form = ReviewForm()

    if form.validate_on_submit():
        review = Review(
            text=form.text.data,
            rating=int(form.rating.data),
            user_id=current_user.id,
            book_id=book.id
        )

        db.session.add(review)
        db.session.commit()
        flash('Ваша рецензия опубликована!', 'success')
        return redirect(url_for('book_detail', book_id=book.id))

    return render_template('add_review.html', book=book, form=form)


@app.route('/stats')
@login_required
def reading_stats():
    progress_data = ReadingProgress.query.filter_by(user_id=current_user.id).order_by(ReadingProgress.date).all()

    if not progress_data:
        return render_template('reading_stats.html', no_data=True)

    chart_data = {
        'dates': [p.date.strftime('%Y-%m-%d') for p in progress_data],
        'pages': [p.pages_read for p in progress_data]
    }

    return render_template('reading_stats.html', chart_data=chart_data)


@app.route('/book/<int:book_id>/progress', methods=['GET', 'POST'])
@login_required
def reading_progress(book_id):
    book = Book.query.get_or_404(book_id)
    form = ReadingProgressForm()

    if form.validate_on_submit():
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=book.id,
            pages_read=form.pages_read.data,
            total_pages=book.total_pages
        )
        db.session.add(progress)
        db.session.commit()
        flash('Прогресс сохранен!', 'success')
        return redirect(url_for('book_detail', book_id=book.id))
    daily_stats = db.session.query(
        db.func.strftime('%Y-%m-%d', ReadingProgress.date).label('reading_date'),
        db.func.sum(ReadingProgress.pages_read).label('total_pages')
    ).filter(
        ReadingProgress.user_id == current_user.id,
        ReadingProgress.book_id == book.id
    ).group_by(
        db.func.strftime('%Y-%m-%d', ReadingProgress.date)
    ).order_by(
        db.func.strftime('%Y-%m-%d', ReadingProgress.date)
    ).all()

    chart_data = {
        'dates': [stat.reading_date for stat in daily_stats],
        'pages': [stat.total_pages for stat in daily_stats],
        'total_pages': book.total_pages
    }

    return render_template('reading_progress.html',
                           book=book,
                           form=form,
                           chart_data=chart_data)


@app.route('/api/books', methods=['POST'])
def api_add_book():
    data = request.get_json()

    new_book = Book(
        title=data['title'],
        author=data['author'],
        total_pages=data['total_pages'],
        user_id=data.get('user_id', 1)
    )
    db.session.add(new_book)
    db.session.commit()

    return jsonify({'message': 'Book created', 'id': new_book.id}), 201


@app.route('/api/books', methods=['GET'])
def api_get_books():
    books = Book.query.all()
    return jsonify([{
        'id': book.id,
        'title': book.title,
        'author': book.author,
        'cover_url': url_for('static', filename=f'uploads/{book.cover}', _external=True) if book.cover else None
    } for book in books])


@app.route('/api/books/<int:book_id>/cover', methods=['POST'])
def api_upload_cover(book_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = f"book_{book_id}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        book = Book.query.get(book_id)
        book.cover = filename
        db.session.commit()
        return jsonify({
            'message': 'File uploaded',
            'url': url_for('static', filename=f'uploads/{filename}', _external=True)
        })

    return jsonify({'error': 'Invalid file type'}), 400


@app.errorhandler(404)
def not_found_error(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error():
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
