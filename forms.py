from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, NumberRange
from wtforms.validators import ValidationError
from models import *
from flask import request
from flask_wtf.file import FileField, FileAllowed


class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=4, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])


class BookForm(FlaskForm):
    title = StringField('Название книги', validators=[DataRequired()])
    author = StringField('Автор', validators=[DataRequired()])
    total_pages = IntegerField('Количество страниц', validators=[
        DataRequired(),
        NumberRange(min=1, message="Должно быть не менее 1 страницы")
    ])
    cover = FileField('Обложка книги (необязательно)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Только изображения!')
    ])
    submit = SubmitField('Добавить книгу')


class ReviewForm(FlaskForm):
    text = TextAreaField('Текст рецензии', validators=[
        DataRequired(),
        Length(min=10, max=10000, message="Рецензия должна быть от 10 до 10000 символов")
    ], render_kw={"rows": 5})

    rating = SelectField('Оценка', choices=[
        (1, '1 - Ужасно'),
        (2, '2 - Плохо'),
        (3, '3 - Нормально'),
        (4, '4 - Хорошо'),
        (5, '5 - Отлично')
    ], validators=[DataRequired()])

    submit = SubmitField('Опубликовать')


class ReadingProgressForm(FlaskForm):
    pages_read = IntegerField('Прочитано страниц', validators=[
        DataRequired(),
        NumberRange(min=1, message="Должно быть положительное число")
    ])
    submit = SubmitField('Сохранить')

    def validate_pages_read(self, field):
        book = Book.query.get(request.view_args.get('book_id'))
        if book and field.data > book.total_pages:
            raise ValidationError(f"Нельзя прочитать больше {book.total_pages} страниц")
