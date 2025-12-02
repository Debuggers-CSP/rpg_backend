# RPG Game Login Backend API
from flask import Blueprint, jsonify, request, current_app
from flask_restful import Api, Resource
import requests
from model.rpg_user import RPGUser

# Create Blueprint
rpg_api = Blueprint('rpg_api', __name__)
api = Api(rpg_api)

# --- API Resource for RPG User Registration and Retrieval ---
class RPGDataAPI(Resource):
    def get(self):
        """Get all RPG users"""
        users = RPGUser.query.all()
        return jsonify([user.read() for user in users])

    def post(self):
        """Register a new RPG user"""
        user_data = request.get_json()
        
        # Validate input
        if not user_data:
            return {"message": "No data provided"}, 400
        
        required_fields = ['FirstName', 'LastName', 'GitHubID', 'Password']
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                return {"message": f"{field} is required"}, 400
        
        # Check if user already exists
        existing_user = RPGUser.find_by_github_id(user_data['GitHubID'])
        if existing_user:
            return {"message": "User with this GitHub ID already exists"}, 409
        
        # Create new user
        new_user = RPGUser(
            first_name=user_data['FirstName'],
            last_name=user_data['LastName'],
            github_id=user_data['GitHubID'],
            password=user_data['Password']
        )
        
        created_user = new_user.create()
        if created_user is None:
            return {"message": "Failed to create user"}, 500
        
        return {
            "message": "User registered successfully",
            "user": created_user.read()
        }, 201

# --- API Resource for RPG User Login ---
class RPGLoginAPI(Resource):
    def post(self):
        """Login an RPG user"""
        login_data = request.get_json()
        
        # Validate input
        if not login_data:
            return {"message": "No data provided"}, 400
        
        first_name = login_data.get('FirstName')
        last_name = login_data.get('LastName')
        github_id = login_data.get('GitHubID')
        password = login_data.get('Password')
        
        if not first_name or not last_name or not github_id or not password:
            return {"message": "FirstName, LastName, GitHubID, and Password are required"}, 400
        
        # Find user in database and verify password
        user = RPGUser.find_by_credentials(first_name, last_name, github_id, password)
        
        if user:
            return {
                "message": "Login successful",
                "user": user.read()
            }, 200
        else:
            return {"message": "Invalid credentials"}, 401

# --- API Resource for Character Creation ---
class CharacterAPI(Resource):
    def post(self):
        """Create a character sheet from form data with AI-generated analysis"""
        try:
            data = request.get_json()
            
            # Extract form data
            name = data.get('name', '').strip()
            motivation = data.get('motivation', '').strip()
            fear = data.get('fear', '').strip()
            secret = data.get('secret', '').strip()
            game_mode = data.get('gameMode', 'action')
            
            # Validate required fields
            if not all([name, motivation, fear, secret]):
                return {'message': 'All fields are required'}, 400
            
            # Get Groq API key
            api_key = current_app.config.get('GROQ_API_KEY')
            
            # Log API key status for debugging
            current_app.logger.info(f"GROQ API Key configured: {bool(api_key)}")
            
            if not api_key:
                # Fallback to basic analysis if API key not configured
                current_app.logger.warning("GROQ_API_KEY not found, using basic analysis")
                print("⚠️ GROQ_API_KEY not found - using basic analysis")
                analysis = self._generate_basic_analysis(name, motivation, fear, secret, game_mode)
            else:
                # Generate AI-powered character analysis
                current_app.logger.info("Generating AI-powered character analysis with Groq")
                print(f"✅ GROQ_API_KEY found - generating AI analysis for {name}")
                analysis = self._generate_ai_analysis(name, motivation, fear, secret, game_mode, api_key)
                print(f"📝 AI Analysis generated: {analysis[:100]}...")
            
            # Create character sheet response
            character_sheet = {
                'name': name,
                'motivation': motivation,
                'fear': fear,
                'secret': secret,
                'gameMode': game_mode,
                'analysis': analysis
            }
            
            return character_sheet, 200
            
        except Exception as e:
            return {'message': f'Error creating character: {str(e)}'}, 500
    
    def _generate_ai_analysis(self, name, motivation, fear, secret, game_mode, api_key):
        """Generate character analysis using Groq AI"""
        try:
            # Create a prompt based on game mode
            if game_mode == 'cozy':
                prompt = f"""You are a creative RPG character analyst specializing in cozy, heartwarming games. 
Analyze this character for a cozy game setting where stories focus on relationships, personal growth, and community:

Character Name: {name}
Motivation: {motivation}
Fear: {fear}
Secret: {secret}

Write a warm, encouraging 3-4 sentence analysis that:
- Explains how their motivation connects them to community and personal growth
- Describes how their fear adds relatable vulnerability
- Shows how their secret creates intrigue without being too dark
- Suggests a positive character arc focused on connection and healing

Keep the tone gentle, optimistic, and focused on emotional growth."""
            else:
                prompt = f"""You are a creative RPG character analyst specializing in action-adventure games.
Analyze this character for an action-packed game setting with quests, challenges, and dramatic storytelling:

Character Name: {name}
Motivation: {motivation}
Fear: {fear}
Secret: {secret}

Write an exciting 3-4 sentence analysis that:
- Explains how their motivation drives them through dangerous quests
- Describes the internal conflict their fear creates
- Shows how their secret adds dramatic complexity
- Suggests how motivation and fear create tension in their character arc

Keep the tone dynamic, compelling, and focused on adventure and conflict."""

            # Call Groq API
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": "You are a creative RPG character analyst who writes engaging character analyses."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.8,
                    "max_tokens": 300
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content'].strip()
                print(f"✨ Success! Groq API returned: {analysis[:50]}...")
                return analysis
            else:
                # Fallback to basic analysis if API call fails
                current_app.logger.error(f"Groq API error: {response.status_code} - {response.text}")
                print(f"❌ Groq API error: {response.status_code}")
                return self._generate_basic_analysis(name, motivation, fear, secret, game_mode)
                
        except Exception as e:
            # Fallback to basic analysis on error
            current_app.logger.error(f"Error generating AI analysis: {e}")
            return self._generate_basic_analysis(name, motivation, fear, secret, game_mode)
    
    def _generate_basic_analysis(self, name, motivation, fear, secret, game_mode):
        """Fallback basic analysis if AI is unavailable"""
        if game_mode == 'cozy':
            return f"{name} has a gentle but determined spirit, with motivations that connect them to their community. Their fear represents vulnerability that makes them relatable and human, while their secret adds intrigue without overwhelming darkness. This character's journey will be one of personal growth and connection, where their motivation guides them to help others, their fear teaches them compassion, and their secret becomes something they learn to share and find acceptance for."
        else:
            return f"{name} is driven by a powerful motivation that will push them through the most dangerous quests. Their greatest fear creates internal conflict that adds depth to their journey, while their hidden secret provides opportunities for dramatic revelation. This character's motivation and fear are in tension, creating a compelling arc where they must face what they fear most to achieve what they desire."

# Register API endpoints
api.add_resource(RPGDataAPI, '/api/rpg/data')
api.add_resource(RPGLoginAPI, '/api/rpg/login')
api.add_resource(CharacterAPI, '/api/rpg/character')

# HTML endpoint for testing
@rpg_api.route('/rpg')
def rpg_home():
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
                <h3>GET /api/rpg/data</h3>
                <p>Retrieve all registered RPG users</p>
            </div>
            
            <div class="endpoint">
                <h3>POST /api/rpg/data</h3>
                <p>Register a new RPG user</p>
                <p><strong>Body:</strong></p>
                <code>
                    {
                        "FirstName": "string",
                        "LastName": "string",
                        "GitHubID": "string",
                        "Password": "string"
                    }
                </code>
            </div>
            
            <div class="endpoint">
                <h3>POST /api/rpg/login</h3>
                <p>Login an existing RPG user</p>
                <p><strong>Body:</strong></p>
                <code>
                    {
                        "FirstName": "string",
                        "LastName": "string",
                        "GitHubID": "string",
                        "Password": "string"
                    }
                </code>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content
