# RPG Game Login Backend
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_restful import Api, Resource

app = Flask(__name__)
CORS(app, supports_credentials=True, origins='*')

api = Api(app)

# --- Model class for User Data with CRUD naming ---
class UserModel:
    def __init__(self):
        self.users = [
            {
                "id": 1,
                "FirstName": "John",
                "LastName": "Doe",
                "GitHubID": "johndoe"
            },
            {
                "id": 2,
                "FirstName": "Jane",
                "LastName": "Smith",
                "GitHubID": "janesmith"
            }
        ]
        self.next_id = 3

    def read(self):
        """Get all users"""
        return self.users

    def create(self, user_data):
        """Create a new user"""
        # Check if user already exists
        for user in self.users:
            if user['GitHubID'] == user_data.get('GitHubID'):
                return None  # User already exists
        
        # Add new user with auto-incrementing ID
        new_user = {
            "id": self.next_id,
            "FirstName": user_data.get('FirstName'),
            "LastName": user_data.get('LastName'),
            "GitHubID": user_data.get('GitHubID')
        }
        self.users.append(new_user)
        self.next_id += 1
        return new_user

    def find_user(self, first_name, last_name, github_id):
        """Find a user by credentials"""
        for user in self.users:
            if (user['FirstName'] == first_name and 
                user['LastName'] == last_name and 
                user['GitHubID'] == github_id):
                return user
        return None

# Instantiate the model
user_model = UserModel()

# --- API Resource for User Registration and Retrieval ---
class DataAPI(Resource):
    def get(self):
        """Get all users"""
        return jsonify(user_model.read())

    def post(self):
        """Register a new user"""
        user_data = request.get_json()
        
        # Validate input
        if not user_data:
            return {"message": "No data provided"}, 400
        
        required_fields = ['FirstName', 'LastName', 'GitHubID']
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                return {"message": f"{field} is required"}, 400
        
        # Try to create user
        new_user = user_model.create(user_data)
        
        if new_user is None:
            return {"message": "User with this GitHub ID already exists"}, 409
        
        return {
            "message": "User registered successfully",
            "user": new_user
        }, 201

# --- API Resource for User Login ---
class LoginAPI(Resource):
    def post(self):
        """Login a user"""
        login_data = request.get_json()
        
        # Validate input
        if not login_data:
            return {"message": "No data provided"}, 400
        
        first_name = login_data.get('FirstName')
        last_name = login_data.get('LastName')
        github_id = login_data.get('GitHubID')
        
        if not first_name or not last_name or not github_id:
            return {"message": "FirstName, LastName, and GitHubID are required"}, 400
        
        # Find user
        user = user_model.find_user(first_name, last_name, github_id)
        
        if user:
            return {
                "message": "Login successful",
                "user": user
            }, 200
        else:
            return {"message": "Invalid credentials"}, 401

# Register API endpoints
api.add_resource(DataAPI, '/api/data')
api.add_resource(LoginAPI, '/api/login')

# HTML endpoint for testing
@app.route('/')
def home():
    html_content = """
    <html>
    <head>
        <title>RPG Game Backend</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #333; }
            .endpoint {
                background: #f8f8f8;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid #4CAF50;
            }
            code {
                background: #e8e8e8;
                padding: 2px 6px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎮 RPG Game Backend API</h1>
            <p>Flask server is running successfully!</p>
            
            <h2>Available Endpoints:</h2>
            
            <div class="endpoint">
                <h3>GET /api/data</h3>
                <p>Retrieve all registered users</p>
            </div>
            
            <div class="endpoint">
                <h3>POST /api/data</h3>
                <p>Register a new user</p>
                <p><strong>Body:</strong></p>
                <code>
                    {
                        "FirstName": "string",
                        "LastName": "string",
                        "GitHubID": "string"
                    }
                </code>
            </div>
            
            <div class="endpoint">
                <h3>POST /api/login</h3>
                <p>Login an existing user</p>
                <p><strong>Body:</strong></p>
                <code>
                    {
                        "FirstName": "string",
                        "LastName": "string",
                        "GitHubID": "string"
                    }
                </code>
            </div>
            
            <p style="margin-top: 30px;">
                <strong>Server URL:</strong> <code>http://localhost:5001</code>
            </p>
        </div>
    </body>
    </html>
    """
    return html_content

if __name__ == '__main__':
    print("🎮 RPG Game Backend Starting...")
    print("📡 Server running on http://localhost:5001")
    print("📋 Available endpoints:")
    print("   - GET  /api/data  (Get all users)")
    print("   - POST /api/data  (Register user)")
    print("   - POST /api/login (Login user)")
    app.run(port=5001, debug=True)
