from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = 'login_page'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def init_auth(app):
    login_manager.init_app(app)