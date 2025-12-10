# RPG Game Login Backend API
from flask import Blueprint, jsonify, request, current_app
from contextlib import contextmanager
from flask_restful import Api, Resource
import requests
from model.rpg_user import RPGUser
from api.rpg_stories import *  # Story elements data management
import sqlite3
import os
from datetime import datetime

# Create Blueprint
rpg_api = Blueprint('rpg_api', __name__)
api = Api(rpg_api)

# ---------------------------------------------------------------------------
# API Overview / Frontend mapping
# ---------------------------------------------------------------------------
# This file implements the RPG-related backend used by two main frontend
# surfaces:
#
# 1) The in-game RPG frontend (SPA or pages that call these endpoints):
#    - `/rpg` (HTML test page provided by this blueprint)
#    - Endpoints under `/api/rpg/*` used by the game UI to register/login
#      users, save/load character sheets, quests, and key bindings.
#    - Typical front-end files: `static/js/...` (game client), or whichever
#      frontend calls `/api/rpg/*` routes.
#
# 2) The admin / dashboard pages (server-rendered templates):
#    - `templates/rpg_stats.html` — admin dashboard that inspects RPG users,
#      character sheets and quests. It calls the stats endpoints below to
#      present aggregated data.
#
# Route groups and their frontend targets:
# - `/api/rpg/data`         : RPG user list + registration  (game UI / admin)
# - `/api/rpg/login`        : Login for RPG users              (game UI)
# - `/api/rpg/character`    : Create character sheet           (game UI)
# - `/api/rpg/quest(s)`     : Create / list quests             (game UI)
# - `/api/rpg/keybindings`  : Save / load key bindings         (game UI)
# - `/api/rpg/story`        : Story element browsing (used by in-game story UI)
# - `/api/rpg_stats/*`      : RPC endpoints for aggregated stats (admin & client)
# - `/api/stats/*`          : Legacy endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------

# Helper function to get the correct database path
def get_rpg_db_path():
    """Get the absolute path to the RPG database"""
    import os
    from flask import current_app
    try:
        app_root = current_app.root_path
    except:
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(app_root, 'instance', 'rpg', 'rpg.db')

# Initialize RPG database with all tables
def init_rpg_db():
    """Initialize SQLite database for RPG game with character sheets and quests tables"""
    db_path = get_rpg_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create character_sheets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS character_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_github_id TEXT NOT NULL,
            name TEXT NOT NULL,
            motivation TEXT NOT NULL,
            fear TEXT NOT NULL,
            secret TEXT NOT NULL,
            game_mode TEXT NOT NULL,
            analysis TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create quests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_github_id TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT NOT NULL,
            objective TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            reward TEXT NOT NULL,
            game_mode TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Create key_bindings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS key_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_github_id TEXT NOT NULL,
            game_mode TEXT NOT NULL,

            -- Core movement & interaction
            move_up_key TEXT NOT NULL,
            move_left_key TEXT NOT NULL,
            move_down_key TEXT NOT NULL,
            move_right_key TEXT NOT NULL,
            interact_key TEXT NOT NULL,
            jump_key TEXT NOT NULL,
            sprint_key TEXT,

            -- Universal extras
            secondary_interact_key TEXT,
            quick_action_key TEXT,
            inventory_key TEXT,
            map_key TEXT,
            pause_key TEXT,
            quick_menu_key TEXT,
            screenshot_key TEXT,

            -- Cozy extras
            tool1_key TEXT,
            tool2_key TEXT,
            tool3_key TEXT,
            tool4_key TEXT,
            tool5_key TEXT,
            emote_wheel_key TEXT,
            craft_menu_key TEXT,
            cozy_zoom_key TEXT,
            chill_action_key TEXT,
            gardening_key TEXT,
            backpack_key TEXT,
            decor_mode_key TEXT,
            cozy_slow_walk_key TEXT,
            cozy_grid_toggle_key TEXT,
            cozy_inspect_key TEXT,
            pet_whistle_key TEXT,

            -- Action combat
            primary_attack_key TEXT,
            heavy_attack_key TEXT,
            ability1_key TEXT,
            ability2_key TEXT,
            ability3_key TEXT,
            ability4_key TEXT,
            ultimate_key TEXT,
            dodge_key TEXT,
            crouch_key TEXT,
            grenade_key TEXT,
            reload_key TEXT,
            execute_key TEXT,
            melee_key TEXT,
            weapon_swap_key TEXT,
            mark_target_key TEXT,
            focus_state_key TEXT,
            lock_on_key TEXT,
            tactical_wheel_key TEXT,
            taunt_key TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


    
    conn.commit()
    conn.close()

# Call this when the module loads
init_rpg_db()

# --- API Resource: RPG User Registration and Retrieval ---
# Frontend: called by the game UI to register new RPG users and by admin
# dashboards to list users. Endpoint: `/api/rpg/data`.
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

# --- API Resource: RPG User Login ---
# Frontend: game login flow. Endpoint: `/api/rpg/login`.
class RPGLoginAPI(Resource):
    def post(self):
        """Login an RPG user"""
        login_data = request.get_json()
        
        # Validate input
        if not login_data:
            return {"message": "No data provided"}, 400
        
        github_id = login_data.get('GitHubID')
        password = login_data.get('Password')
        
        if not github_id or not password:
            return {"message": "GitHubID and Password are required"}, 400
        
        # Find user in database by GitHub ID and verify password
        user = RPGUser.find_by_github_id_and_password(github_id, password)
        
        if user:
            return {
                "message": "Login successful",
                "user": user.read()
            }, 200
        else:
            return {"message": "Invalid credentials"}, 401

# --- API Resource: Character Creation ---
# Frontend: character creation UI in the game. Endpoint: `/api/rpg/character`.
class CharacterAPI(Resource):
    def post(self):
        """Create a character sheet from form data with AI-generated analysis"""
        try:
            data = request.get_json()
            
            # CRITICAL DEBUG LOGGING
            print("\n" + "="*80)
            print("🔥 CHARACTER CREATION REQUEST RECEIVED")
            print("="*80)
            print(f"📦 Full request data: {data}")
            print(f"🔑 Data keys: {list(data.keys()) if data else 'NO DATA'}")
            print(f"👤 userGithubId value: '{data.get('userGithubId', 'NOT PROVIDED')}'")
            print("="*80 + "\n")
            
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
            
            # Get user GitHub ID if provided (for saving to database)
            user_github_id = data.get('userGithubId', '').strip()
            
            print(f"\n🔍 ATTEMPTING TO SAVE CHARACTER:")
            print(f"   User GitHub ID: '{user_github_id}'")
            print(f"   Character Name: '{name}'")
            
            # Save to database if user is logged in
            character_id = None
            if user_github_id:
                print(f"   ✅ User ID provided - will save to database")
                try:
                    db_path = get_rpg_db_path()
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO character_sheets (user_github_id, name, motivation, fear, secret, game_mode, analysis)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (user_github_id, name, motivation, fear, secret, game_mode, analysis))
                    
                    character_id = cursor.lastrowid
                    conn.commit()
                    conn.close()
                    print(f"   💾 ✅ Character saved to database with ID: {character_id}\n")
                except Exception as db_error:
                    print(f"   ❌ Failed to save character to database: {db_error}\n")
            else:
                print(f"   ⚠️  NO USER ID - Character will NOT be saved to database!\n")
                print(f"   ⚠️  Frontend must send 'userGithubId' in the request body.\n")
            
            # Create character sheet response
            character_sheet = {
                'id': character_id,
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
    
    def get(self):
        """Get all character sheets for a specific user"""
        try:
            # Get user_github_id from query parameters
            user_github_id = request.args.get('userGithubId', '').strip()
            
            if not user_github_id:
                return {'message': 'User GitHub ID is required'}, 400
            
            db_path = get_rpg_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Only get characters for this specific user
            cursor.execute('''
                SELECT * FROM character_sheets 
                WHERE user_github_id = ? 
                ORDER BY created_at DESC
            ''', (user_github_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            characters = []
            for row in rows:
                characters.append({
                    'id': row['id'],
                    'name': row['name'],
                    'motivation': row['motivation'],
                    'fear': row['fear'],
                    'secret': row['secret'],
                    'gameMode': row['game_mode'],
                    'analysis': row['analysis'],
                    'createdAt': row['created_at']
                })
            
            return {'characters': characters}, 200
            
        except Exception as e:
            return {'message': f'Error retrieving characters: {str(e)}'}, 500
    
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

# --- API Resource for Quest Creation and Retrieval ---
class QuestAPI(Resource):
    """Quest endpoints

    Frontend: quest creation/listing in the game UI.
    Endpoints: `/api/rpg/quest` and `/api/rpg/quests`.
    """
    def post(self):
        """Create a new quest and add to quest log"""
        try:
            data = request.get_json()
            
            print(f"📝 Quest creation request received: {data}")
            
            # Extract quest data
            title = data.get('title', '').strip()
            location = data.get('location', '').strip()
            objective = data.get('objective', '').strip()
            difficulty = data.get('difficulty', '').strip()
            reward = data.get('reward', '').strip()
            game_mode = data.get('gameMode', 'action')
            user_github_id = data.get('userGithubId', '').strip()  # Get user ID from frontend
            
            print(f"✅ Parsed data - User: {user_github_id}, Title: {title}")
            
            # Validate required fields
            if not all([title, location, objective, difficulty, reward, user_github_id]):
                missing = []
                if not title: missing.append('title')
                if not location: missing.append('location')
                if not objective: missing.append('objective')
                if not difficulty: missing.append('difficulty')
                if not reward: missing.append('reward')
                if not user_github_id: missing.append('userGithubId')
                print(f"❌ Missing fields: {missing}")
                return {'message': f'Missing required fields: {", ".join(missing)}'}, 400
            
            # Save to database with user association
            db_path = get_rpg_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO quests (user_github_id, title, location, objective, difficulty, reward, game_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_github_id, title, location, objective, difficulty, reward, game_mode))
            
            quest_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            print(f"✨ Quest created successfully with ID: {quest_id}")
            
            # Return the quest data
            quest = {
                'id': quest_id,
                'title': title,
                'location': location,
                'objective': objective,
                'difficulty': difficulty,
                'reward': reward,
                'gameMode': game_mode
            }
            
            return quest, 201
            
        except Exception as e:
            print(f"💥 Error creating quest: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'message': f'Error creating quest: {str(e)}'}, 500
    
    def get(self):
        """Get all quests for a specific user"""
        try:
            # Get user_github_id from query parameters
            user_github_id = request.args.get('userGithubId', '').strip()
            
            if not user_github_id:
                return {'message': 'User GitHub ID is required'}, 400
            
            db_path = get_rpg_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Only get quests for this specific user
            cursor.execute('''
                SELECT * FROM quests 
                WHERE user_github_id = ? 
                ORDER BY created_at DESC
            ''', (user_github_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            quests = []
            for row in rows:
                quests.append({
                    'id': row['id'],
                    'title': row['title'],
                    'location': row['location'],
                    'objective': row['objective'],
                    'difficulty': row['difficulty'],
                    'reward': row['reward'],
                    'gameMode': row['game_mode']
                })
            
            return {'quests': quests}, 200
            
        except Exception as e:
            return {'message': f'Error retrieving quests: {str(e)}'}, 500# --- API Resource for Key Binding Creation and Retrieval ---
class KeyBindingAPI(Resource):
    """Key bindings management

    Frontend: allows the game client to save and load user key bindings.
    Endpoint: `/api/rpg/keybindings`.
    """
    def post(self):
        """Save key bindings for a user and game mode"""
        try:
            data = request.get_json()

            user_github_id = data.get('userGithubId', '').strip()
            game_mode = data.get('gameMode', 'action').strip() or 'action'

            # Core movement & interaction
            move_up_key = data.get('moveUpKey', '').strip()
            move_left_key = data.get('moveLeftKey', '').strip()
            move_down_key = data.get('moveDownKey', '').strip()
            move_right_key = data.get('moveRightKey', '').strip()
            interact_key = data.get('interactKey', '').strip()
            jump_key = data.get('jumpKey', '').strip()
            sprint_key = data.get('sprintKey', '').strip()  # optional

            # Universal extras
            secondary_interact_key = data.get('secondaryInteractKey', '').strip()
            quick_action_key = data.get('quickActionKey', '').strip()
            inventory_key = data.get('inventoryKey', '').strip()
            map_key = data.get('mapKey', '').strip()
            pause_key = data.get('pauseKey', '').strip()
            quick_menu_key = data.get('quickMenuKey', '').strip()
            screenshot_key = data.get('screenshotKey', '').strip()

            # Cozy extras
            tool1_key = data.get('tool1Key', '').strip()
            tool2_key = data.get('tool2Key', '').strip()
            tool3_key = data.get('tool3Key', '').strip()
            tool4_key = data.get('tool4Key', '').strip()
            tool5_key = data.get('tool5Key', '').strip()
            emote_wheel_key = data.get('emoteWheelKey', '').strip()
            craft_menu_key = data.get('craftMenuKey', '').strip()
            cozy_zoom_key = data.get('cozyZoomKey', '').strip()
            chill_action_key = data.get('chillActionKey', '').strip()
            gardening_key = data.get('gardeningKey', '').strip()
            backpack_key = data.get('backpackKey', '').strip()
            decor_mode_key = data.get('decorModeKey', '').strip()
            cozy_slow_walk_key = data.get('cozySlowWalkKey', '').strip()
            cozy_grid_toggle_key = data.get('cozyGridToggleKey', '').strip()
            cozy_inspect_key = data.get('cozyInspectKey', '').strip()
            pet_whistle_key = data.get('petWhistleKey', '').strip()

            # Action combat
            primary_attack_key = data.get('primaryAttackKey', '').strip()
            heavy_attack_key = data.get('heavyAttackKey', '').strip()
            ability1_key = data.get('ability1Key', '').strip()
            ability2_key = data.get('ability2Key', '').strip()
            ability3_key = data.get('ability3Key', '').strip()
            ability4_key = data.get('ability4Key', '').strip()
            ultimate_key = data.get('ultimateKey', '').strip()
            dodge_key = data.get('dodgeKey', '').strip()
            crouch_key = data.get('crouchKey', '').strip()
            grenade_key = data.get('grenadeKey', '').strip()
            reload_key = data.get('reloadKey', '').strip()
            execute_key = data.get('executeKey', '').strip()
            melee_key = data.get('meleeKey', '').strip()
            weapon_swap_key = data.get('weaponSwapKey', '').strip()
            mark_target_key = data.get('markTargetKey', '').strip()
            focus_state_key = data.get('focusStateKey', '').strip()
            lock_on_key = data.get('lockOnKey', '').strip()
            tactical_wheel_key = data.get('tacticalWheelKey', '').strip()
            taunt_key = data.get('tauntKey', '').strip()

            # Validate required fields
            missing = []
            if not user_github_id: missing.append('userGithubId')
            if not move_up_key: missing.append('moveUpKey')
            if not move_left_key: missing.append('moveLeftKey')
            if not move_down_key: missing.append('moveDownKey')
            if not move_right_key: missing.append('moveRightKey')
            if not interact_key: missing.append('interactKey')
            if game_mode != 'cozy' and not jump_key:
                missing.append('jumpKey')

            if missing:
                return {'message': f'Missing required fields: {", ".join(missing)}'}, 400

            db_path = get_rpg_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO key_bindings (
                    user_github_id,
                    game_mode,
                    move_up_key,
                    move_left_key,
                    move_down_key,
                    move_right_key,
                    interact_key,
                    jump_key,
                    sprint_key,
                    secondary_interact_key,
                    quick_action_key,
                    inventory_key,
                    map_key,
                    pause_key,
                    quick_menu_key,
                    screenshot_key,
                    tool1_key,
                    tool2_key,
                    tool3_key,
                    tool4_key,
                    tool5_key,
                    emote_wheel_key,
                    craft_menu_key,
                    cozy_zoom_key,
                    chill_action_key,
                    gardening_key,
                    backpack_key,
                    decor_mode_key,
                    cozy_slow_walk_key,
                    cozy_grid_toggle_key,
                    cozy_inspect_key,
                    pet_whistle_key,
                    primary_attack_key,
                    heavy_attack_key,
                    ability1_key,
                    ability2_key,
                    ability3_key,
                    ability4_key,
                    ultimate_key,
                    dodge_key,
                    crouch_key,
                    grenade_key,
                    reload_key,
                    execute_key,
                    melee_key,
                    weapon_swap_key,
                    mark_target_key,
                    focus_state_key,
                    lock_on_key,
                    tactical_wheel_key,
                    taunt_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_github_id,
                game_mode,
                move_up_key,
                move_left_key,
                move_down_key,
                move_right_key,
                interact_key,
                jump_key,
                sprint_key if sprint_key else None,
                secondary_interact_key or None,
                quick_action_key or None,
                inventory_key or None,
                map_key or None,
                pause_key or None,
                quick_menu_key or None,
                screenshot_key or None,
                tool1_key or None,
                tool2_key or None,
                tool3_key or None,
                tool4_key or None,
                tool5_key or None,
                emote_wheel_key or None,
                craft_menu_key or None,
                cozy_zoom_key or None,
                chill_action_key or None,
                gardening_key or None,
                backpack_key or None,
                decor_mode_key or None,
                cozy_slow_walk_key or None,
                cozy_grid_toggle_key or None,
                cozy_inspect_key or None,
                pet_whistle_key or None,
                primary_attack_key or None,
                heavy_attack_key or None,
                ability1_key or None,
                ability2_key or None,
                ability3_key or None,
                ability4_key or None,
                ultimate_key or None,
                dodge_key or None,
                crouch_key or None,
                grenade_key or None,
                reload_key or None,
                execute_key or None,
                melee_key or None,
                weapon_swap_key or None,
                mark_target_key or None,
                focus_state_key or None,
                lock_on_key or None,
                tactical_wheel_key or None,
                taunt_key or None
            ))

            binding_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return {
                'id': binding_id,
                'userGithubId': user_github_id,
                'gameMode': game_mode,
                'moveUpKey': move_up_key,
                'moveLeftKey': move_left_key,
                'moveDownKey': move_down_key,
                'moveRightKey': move_right_key,
                'interactKey': interact_key,
                'jumpKey': jump_key,
                'sprintKey': sprint_key,

                'secondaryInteractKey': secondary_interact_key,
                'quickActionKey': quick_action_key,
                'inventoryKey': inventory_key,
                'mapKey': map_key,
                'pauseKey': pause_key,
                'quickMenuKey': quick_menu_key,
                'screenshotKey': screenshot_key,

                'tool1Key': tool1_key,
                'tool2Key': tool2_key,
                'tool3Key': tool3_key,
                'tool4Key': tool4_key,
                'tool5Key': tool5_key,
                'emoteWheelKey': emote_wheel_key,
                'craftMenuKey': craft_menu_key,
                'cozyZoomKey': cozy_zoom_key,
                'chillActionKey': chill_action_key,
                'gardeningKey': gardening_key,
                'backpackKey': backpack_key,
                'decorModeKey': decor_mode_key,
                'cozySlowWalkKey': cozy_slow_walk_key,
                'cozyGridToggleKey': cozy_grid_toggle_key,
                'cozyInspectKey': cozy_inspect_key,
                'petWhistleKey': pet_whistle_key,

                'primaryAttackKey': primary_attack_key,
                'heavyAttackKey': heavy_attack_key,
                'ability1Key': ability1_key,
                'ability2Key': ability2_key,
                'ability3Key': ability3_key,
                'ability4Key': ability4_key,
                'ultimateKey': ultimate_key,
                'dodgeKey': dodge_key,
                'crouchKey': crouch_key,
                'grenadeKey': grenade_key,
                'reloadKey': reload_key,
                'executeKey': execute_key,
                'meleeKey': melee_key,
                'weaponSwapKey': weapon_swap_key,
                'markTargetKey': mark_target_key,
                'focusStateKey': focus_state_key,
                'lockOnKey': lock_on_key,
                'tacticalWheelKey': tactical_wheel_key,
                'tauntKey': taunt_key
            }, 201

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'message': f'Error saving key bindings: {str(e)}'}, 500


    def get(self):
        """Get the most recent key bindings for a specific user (and optional game mode)"""
        try:
            user_github_id = request.args.get('userGithubId', '').strip()
            game_mode = request.args.get('gameMode', '').strip()

            if not user_github_id:
                return {'message': 'User GitHub ID is required'}, 400

            db_path = get_rpg_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if game_mode:
                cursor.execute('''
                    SELECT * FROM key_bindings
                    WHERE user_github_id = ? AND game_mode = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (user_github_id, game_mode))
            else:
                cursor.execute('''
                    SELECT * FROM key_bindings
                    WHERE user_github_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (user_github_id,))

            row = cursor.fetchone()
            conn.close()

            if not row:
                return {'message': 'No key bindings found for this user'}, 404

            binding = {
                'id': row['id'],
                'userGithubId': row['user_github_id'],
                'gameMode': row['game_mode'],

                'moveUpKey': row['move_up_key'],
                'moveLeftKey': row['move_left_key'],
                'moveDownKey': row['move_down_key'],
                'moveRightKey': row['move_right_key'],
                'interactKey': row['interact_key'],
                'jumpKey': row['jump_key'],
                'sprintKey': row['sprint_key'],

                'secondaryInteractKey': row['secondary_interact_key'],
                'quickActionKey': row['quick_action_key'],
                'inventoryKey': row['inventory_key'],
                'mapKey': row['map_key'],
                'pauseKey': row['pause_key'],
                'quickMenuKey': row['quick_menu_key'],
                'screenshotKey': row['screenshot_key'],

                'tool1Key': row['tool1_key'],
                'tool2Key': row['tool2_key'],
                'tool3Key': row['tool3_key'],
                'tool4Key': row['tool4_key'],
                'tool5Key': row['tool5_key'],
                'emoteWheelKey': row['emote_wheel_key'],
                'craftMenuKey': row['craft_menu_key'],
                'cozyZoomKey': row['cozy_zoom_key'],
                'chillActionKey': row['chill_action_key'],
                'gardeningKey': row['gardening_key'],
                'backpackKey': row['backpack_key'],
                'decorModeKey': row['decor_mode_key'],
                'cozySlowWalkKey': row['cozy_slow_walk_key'],
                'cozyGridToggleKey': row['cozy_grid_toggle_key'],
                'cozyInspectKey': row['cozy_inspect_key'],
                'petWhistleKey': row['pet_whistle_key'],

                'primaryAttackKey': row['primary_attack_key'],
                'heavyAttackKey': row['heavy_attack_key'],
                'ability1Key': row['ability1_key'],
                'ability2Key': row['ability2_key'],
                'ability3Key': row['ability3_key'],
                'ability4Key': row['ability4_key'],
                'ultimateKey': row['ultimate_key'],
                'dodgeKey': row['dodge_key'],
                'crouchKey': row['crouch_key'],
                'grenadeKey': row['grenade_key'],
                'reloadKey': row['reload_key'],
                'executeKey': row['execute_key'],
                'meleeKey': row['melee_key'],
                'weaponSwapKey': row['weapon_swap_key'],
                'markTargetKey': row['mark_target_key'],
                'focusStateKey': row['focus_state_key'],
                'lockOnKey': row['lock_on_key'],
                'tacticalWheelKey': row['tactical_wheel_key'],
                'tauntKey': row['taunt_key'],
                'createdAt': row['created_at']
            }

            return {'binding': binding}, 200

        except Exception as e:
            return {'message': f'Error retrieving key bindings: {str(e)}'}, 500



# ============================================================================
# STORY ELEMENTS API RESOURCES
# ============================================================================
# These endpoints handle story element data (plot hooks, NPCs, twists, etc.)
# and voting (love/skip counts) similar to the jokes system

class StoryElementsAPI(Resource):
    """Story elements browsing

    Frontend: in-game story UI that shows story elements for players.
    Endpoint: `/api/rpg/story`.
    """
    def get(self):
        return jsonify(getStoryElements())

class StoryElementAPI(Resource):
    """Get a specific story element by ID"""
    def get(self, id):
        return jsonify(getStoryElement(id))

class StoryLoveAPI(Resource):
    """Increment love count for a story element"""
    def put(self, id):
        addStoryLove(id)
        return jsonify(getStoryElement(id))

class StorySkipAPI(Resource):
    """Increment skip count for a story element"""
    def put(self, id):
        addStorySkip(id)
        return jsonify(getStoryElement(id))

# ============================================================================
# REGISTER API ENDPOINTS
# ============================================================================

# RPG User and Authentication endpoints
api.add_resource(RPGDataAPI, '/api/rpg/data')
api.add_resource(RPGLoginAPI, '/api/rpg/login')

# Character and Quest endpoints
api.add_resource(CharacterAPI, '/api/rpg/character')
api.add_resource(QuestAPI, '/api/rpg/quest', '/api/rpg/quests')  # Support both singular and plural
api.add_resource(KeyBindingAPI, '/api/rpg/keybindings')

# Story Elements endpoints
api.add_resource(StoryElementsAPI, '/api/rpg/story', '/api/rpg/story/')
api.add_resource(StoryElementAPI, '/api/rpg/story/<int:id>', '/api/rpg/story/<int:id>/')
api.add_resource(StoryLoveAPI, '/api/rpg/story/love/<int:id>', '/api/rpg/story/love/<int:id>/')
api.add_resource(StorySkipAPI, '/api/rpg/story/skip/<int:id>', '/api/rpg/story/skip/<int:id>/')

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

# --- RPG Statistics (kept below) ---
DATABASE = os.path.join('instance', 'rpg', 'rpg_statistics.db')

# Ensure directory exists
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

# Database connection management
@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Initialize stats DB
def init_rpg_stats():
    """Initialize RPG statistics database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL UNIQUE,
                count INTEGER NOT NULL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        cursor.execute('SELECT COUNT(*) FROM statistics')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO statistics (mode, count) VALUES (?, ?)', ('chill', 0))
            cursor.execute('INSERT INTO statistics (mode, count) VALUES (?, ?)', ('action', 0))
            print('✓ RPG Statistics database initialized')
        conn.commit()


# Helper to get statistics
def get_statistics():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT mode, count FROM statistics')
        stats_rows = cursor.fetchall()
        stats = {'chill': 0, 'action': 0, 'total': 0}
        for row in stats_rows:
            mode = row['mode']
            count = row['count']
            stats[mode] = count
            stats['total'] += count

        cursor.execute('''
            SELECT user_id, mode, timestamp 
            FROM history 
            ORDER BY id DESC 
            LIMIT 100
        ''')
        history_rows = cursor.fetchall()

        stats['history'] = [
            {
                'userId': row['user_id'],
                'mode': row['mode'],
                'timestamp': row['timestamp']
            }
            for row in history_rows
        ]

        return stats


# Routes (kept same paths as original rpg_stats_api)
@rpg_api.route('/api/rpg_stats/stats', methods=['GET'])
def get_stats():
    """GET /api/rpg_stats/stats - return statistics"""
    try:
        stats = get_statistics()
        print(f'📊 Returning stats: chill={stats["chill"]}, action={stats["action"]}, total={stats["total"]}')
        return jsonify(stats)
    except Exception as e:
        print(f'❌ Error getting stats: {e}')
        return jsonify({'error': str(e)}), 500


@rpg_api.route('/api/rpg_stats/record', methods=['GET'])
def record_selection():
    """GET /api/rpg_stats/record?mode=chill&userId=xxx - record a selection"""
    try:
        mode = request.args.get('mode')
        user_id = request.args.get('userId', 'anonymous')
        print(f'📝 Recording: mode={mode}, userId={user_id}')
        if mode not in ['chill', 'action']:
            return jsonify({'error': 'Invalid mode'}), 400

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE statistics 
                SET count = count + 1 
                WHERE mode = ?
            ''', (mode,))
            timestamp = datetime.utcnow().isoformat()
            cursor.execute('''
                INSERT INTO history (user_id, mode, timestamp)
                VALUES (?, ?, ?)
            ''', (user_id, mode, timestamp))
            conn.commit()
            print(f'✓ Successfully recorded {mode} selection')

        stats = get_statistics()
        return jsonify(stats)

    except Exception as e:
        print(f'❌ Error recording selection: {e}')
        return jsonify({'error': str(e)}), 500


@rpg_api.route('/api/rpg_stats/reset', methods=['GET', 'POST'])
def reset_stats():
    """GET/POST /api/rpg_stats/reset - reset statistics"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE statistics SET count = 0')
            cursor.execute('DELETE FROM history')
            conn.commit()
            print('✓ Statistics reset successfully')

        stats = get_statistics()
        return jsonify(stats)

    except Exception as e:
        print(f'❌ Error resetting stats: {e}')
        return jsonify({'error': str(e)}), 500


@rpg_api.route('/api/rpg_stats/health', methods=['GET'])
def health():
    """GET /api/rpg_stats/health - health check"""
    return jsonify({
        'status': 'healthy',
        'database': DATABASE,
        'message': 'RPG Statistics API is running'
    })


# Initialize the stats DB on module load
# --- Legacy `/api/stats` endpoints moved here (kept organized) ---

@rpg_api.route('/api/stats', methods=['GET'])
def get_stats_legacy():
    """GET /api/stats - return statistics (legacy route)"""
    try:
        stats = get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@rpg_api.route('/api/stats/record', methods=['GET', 'POST'])
def record_selection_legacy():
    """Record a selection via GET or POST (legacy route)"""
    try:
        if request.method == 'GET':
            mode = request.args.get('mode')
            user_id = request.args.get('userId', 'anonymous')
        else:
            data = request.get_json() or {}
            mode = data.get('mode')
            user_id = data.get('userId', 'anonymous')

        if mode not in ['chill', 'action']:
            return jsonify({'error': 'Invalid mode'}), 400

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE statistics
                SET count = count + 1
                WHERE mode = ?
            ''', (mode,))
            timestamp = datetime.utcnow().isoformat()
            cursor.execute('''
                INSERT INTO history (user_id, mode, timestamp)
                VALUES (?, ?, ?)
            ''', (user_id, mode, timestamp))
            conn.commit()

        stats = get_statistics()
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@rpg_api.route('/api/stats/reset', methods=['GET', 'POST'])
def reset_stats_legacy():
    """Reset statistics (legacy route)"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE statistics SET count = 0')
            cursor.execute('DELETE FROM history')
            conn.commit()

        stats = get_statistics()
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@rpg_api.route('/api/stats/health', methods=['GET'])
def stats_health_legacy():
    """Legacy health check for /api/stats"""
    return jsonify({'status': 'healthy', 'database': DATABASE})


# Initialize the stats DB on module load
init_rpg_stats()
