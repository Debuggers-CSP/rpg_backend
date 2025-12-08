from __init__ import db
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

class RPGUser(db.Model):
    """
    RPG User Model
    
    The RPG User table stores user credentials for the RPG game
    """
    __bind_key__ = 'rpg' 
    __tablename__ = 'rpg_users'

    # Define the User schema with "vars" from object
    id = db.Column(db.Integer, primary_key=True)
    _first_name = db.Column(db.String(255), nullable=False)
    _last_name = db.Column(db.String(255), nullable=False)
    _github_id = db.Column(db.String(255), unique=True, nullable=False)
    _password = db.Column(db.String(255), nullable=False)
    
    def __init__(self, first_name, last_name, github_id, password="password123"):
        """
        Constructor for RPGUser object
        """
        self._first_name = first_name
        self._last_name = last_name
        self._github_id = github_id
        self._password = generate_password_hash(password)

    @property
    def first_name(self):
        return self._first_name
    
    @first_name.setter
    def first_name(self, value):
        self._first_name = value
    
    @property
    def last_name(self):
        return self._last_name
    
    @last_name.setter
    def last_name(self, value):
        self._last_name = value
    
    @property
    def github_id(self):
        return self._github_id
    
    @github_id.setter
    def github_id(self, value):
        self._github_id = value
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, value):
        self._password = generate_password_hash(value)
    
    def is_password(self, password):
        """
        Check if the provided password matches the stored password hash
        
        Args:
            password: Plain text password to check
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return check_password_hash(self._password, password)

    def create(self):
        """
        Creates a new RPG user in the database
        
        Returns:
            self if successful, None if user already exists
        """
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except IntegrityError:
            db.session.rollback()
            return None

    def read(self):
        """
        Converts RPGUser object to dictionary
        
        Returns:
            dict: Dictionary representation of the user
        """
        return {
            "id": self.id,
            "FirstName": self.first_name,
            "LastName": self.last_name,
            "GitHubID": self.github_id
        }
    
    @staticmethod
    def find_by_credentials(first_name, last_name, github_id, password):
        """
        Find a user by their credentials including password verification
        
        Args:
            first_name: User's first name
            last_name: User's last name
            github_id: User's GitHub ID
            password: Plain text password to verify
            
        Returns:
            RPGUser object if found and password matches, None otherwise
        """
        user = RPGUser.query.filter_by(
            _first_name=first_name,
            _last_name=last_name,
            _github_id=github_id
        ).first()
        
        if user and user.is_password(password):
            return user
        return None
    
    @staticmethod
    def find_by_github_id(github_id):
        """
        Find a user by their GitHub ID
        
        Args:
            github_id: User's GitHub ID
            
        Returns:
            RPGUser object if found, None otherwise
        """
        return RPGUser.query.filter_by(_github_id=github_id).first()


def initRPGUsers():
    """
    Initialize the RPG Users table with default users
    """
    # Create tables if they don't exist
    with current_app.app_context():
        engine = db.get_engine(bind='rpg')
        RPGUser.metadata.create_all(engine)
    
    # Check if users already exist
    if RPGUser.query.count() == 0:
        # Create default users
        default_users = [
            RPGUser(first_name="John", last_name="Doe", github_id="johndoe", password="password123"),
            RPGUser(first_name="Jane", last_name="Smith", github_id="janesmith", password="password456")
        ]
        
        for user in default_users:
            try:
                user.create()
                print(f"RPG User created: {user.first_name} {user.last_name}")
            except Exception as e:
                print(f"Error creating RPG user: {e}")
                db.session.rollback()
