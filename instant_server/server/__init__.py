from flask import Flask
from flask_login import LoginManager
from datetime import timedelta

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
app.secret_key = 'ahilfautunesecretkey'
app.permanent_session_lifetime = timedelta(seconds=600)

import urls
