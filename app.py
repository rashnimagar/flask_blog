from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
import pymysql
import json
import os
import math
from werkzeug.utils import secure_filename
from datetime import datetime

pymysql.install_as_MySQLdb()

#loading the config file
with open('templates/config.json', 'r') as c:
    params = json.load(c)['params']

params['local_server'] = True
app = Flask(__name__)
app.config['SECRET_KEY'] = params.get('secret_key') 
#file upload path
app.config['UPLOAD_FOLDER'] = params.get('file_upload_path')

app.config.update(
    SECRET_KEY = params.get('secret_key'),
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = params['gmail_user'],
    MAIL_PASSWORD = params['gmail_password'],
    MAIL_DEFAULT_SENDER = params['gmail_user']
)
mail = Mail(app)

#connecting to the database
if params['local_server']:
    app.config['SQLALCHEMY_DATABASE_URI'] = params['local_uri']
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = params['pro_uri']

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#creating a model for posts
class Posts(db.Model):
    pid = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    slug = db.Column(db.String(25), nullable=False)
    posted_by = db.Column(db.String(20), nullable=False)
    file_upload = db.Column(db.String(100), nullable=True)
    date = db.Column(db.Date, default=datetime.utcnow)

#creating a model for the contact form
class Contacts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone_no = db.Column(db.String(12), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    msg = db.Column(db.String(500), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)


#creating all the db, table and columns
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    posts = Posts.query.filter_by().all()
    last = math.ceil(len(posts)/int(params['no_of_posts'])) if len(posts) > 0 else 1

    page = request.args.get('page')
    #pagination logic
    if not str(page).isnumeric():
        page = 1
    page = int(page)

    #clamp page between 1 and last
    if page <1:
        page = 1
    elif page > last:
        page = last

    posts = posts[(page-1)*int(params['no_of_posts']): (page-1)*int(params['no_of_posts']) + int(params['no_of_posts'])]

    if len(posts) == 0:
        prev = "#"
        next = "#"
    else:
        #page 1 xa vani
        if page==1:
            prev = "#"
            next = "/?page=" + str(page+1)
        #last page xa vani
        elif page==last:
            prev = '/?page=' + str(page-1)
            next = "#"
        else:
            prev = "/?page=" + str(page-1)
            next = "/?page=" + str(page+1)

    #posts = Posts.query.filter_by().all()[0: params['no_of_posts']]
    return render_template('index.html', params=params, posts=posts, prev=prev, next=next)

#login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    #checking if user is already there
    if 'user' in session and session['user'] == params['admin_user']:
        return redirect('/dashboard')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == params['admin_user'] and password == params['admin_password']:
            #set session variable for user
            session['user'] = username
            flash('Logged in successfully!', 'success')
            return redirect('/dashboard')
        else:
            flash('Invalid credentials. Please try again.', 'danger')
        
    return render_template('login.html', params=params)

@app.route('/logout')
def logout():
    #remove user from session
    if 'user' in session:
        session.pop('user', None)
        flash('Logged out successfully!', 'success')
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    # Check if user is logged in
    if 'user' in session and session['user'] == params['admin_user']:
        posts = Posts.query.all()
        return render_template('dashboard.html', params=params, posts=posts)
    else:
        return redirect('/login')

@app.route('/about')
def about():
    return render_template('about.html', params=params)

@app.route('/post/<string:slug>', methods=['GET'])
def post_route(slug):
    post = Posts.query.filter_by(slug=slug).first()
    return render_template('post.html', post=post, params=params)

@app.route('/edit/<string:pid>', methods=['GET', 'POST'])
def edit(pid):
    # Check if user is logged in
    if 'user' not in session or session['user'] != params['admin_user']:
        return redirect('/login')

    if request.method == 'POST':
        slug = request.form.get('slug').strip().lower()
        title = request.form.get('title').strip()
        content = request.form.get('content').strip()
        posted_by = request.form.get('posted_by').strip()
        date = datetime.now().date()
        file_upload = request.files.get('file_upload')
        if file_upload and file_upload.filename != "":
            filename = secure_filename(file_upload.filename)
            file_upload.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))


        if pid == '0':
            # Add new post
            post = Posts(slug=slug, title=title, content=content, posted_by=posted_by, file_upload=file_upload.filename, date=date)
            db.session.add(post)
            db.session.commit()
            flash('Post added successfully!', 'success')
            return redirect('/dashboard')

        else:
            # Edit existing post
            post = Posts.query.filter_by(pid=pid).first()
            if not post:
                flash('Post not found!', 'danger')
                return redirect('/dashboard')  # redirect if invalid pid

            post.slug = slug
            post.title = title
            post.content = content
            post.posted_by = posted_by
            post.file_upload = file_upload.filename
            post.date = date
            db.session.commit()
            flash('Post updated successfully!', 'success')
            return redirect('/dashboard')

    # GET request - fetch post to populate form
    if pid == '0':
        post = None  # new post, empty form
    else:
        post = Posts.query.filter_by(pid=pid).first()
        if not post:
            flash('Post not found!', 'danger')
            return redirect('/dashboard')

    return render_template('edit.html', params=params, post=post, pid=pid)

@app.route('/delete/<string:pid>', methods=['GET', 'POST'])
def delete(pid):
    #check if user is logged in
    if 'user' in session and session['user'] == params['admin_user']:
        post = Posts.query.filter_by(pid=pid).first()
        if post:
            db.session.delete(post)
            db.session.commit()
            flash('Post deleted successfully!', 'success')

    return redirect('/dashboard')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        #get from form data
        name = request.form.get('name').strip()
        email = request.form.get('email').strip()
        phone = request.form.get('phone').strip()
        message = request.form.get('message').strip()

        #check if any field is empty
        if not name or not email or not phone or not message:
            flash("Please fill out all fields before submitting.", "warning")
            return render_template('contact.html', params=params)
        
        #save to db
        entry = Contacts(name=name, phone_no=phone, email=email, msg=message, date=datetime.now().date())
        db.session.add(entry)
        db.session.commit()
        #sending mail
        try:
            mail.send_message(
                subject=f"Contact from Rashni's Blog by {name}",
                sender = params['gmail_user'],
                recipients = [params['gmail_user']],
                body = f"Name: {name}\nEmail: {email}\nPhone: {phone}\n\nMessage:\n{message}"
            )
            flash("Message sent successfully!")
        except Exception as e:
            flash("Failed to send message. Please try again later.")
    return render_template('contact.html', params=params)

if __name__ == '__main__':
    app.run(debug=True)