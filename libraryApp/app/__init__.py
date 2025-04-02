from flask import Flask
import os
import sqlite3

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'library.db')
app.config['SECRET_KEY'] = os.urandom(24)

from app import routes