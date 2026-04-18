from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from database import cek_login

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data:
        return jsonify({'sukses': False, 'pesan': 'Body kosong'}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'sukses': False, 'pesan': 'Username/password kosong'}), 400

    user = cek_login(username, password)

    if not user:
        return jsonify({'sukses': False, 'pesan': 'Username atau password salah'}), 401

    # ✅ Pakai JWT bawaan Flask
    token = create_access_token(identity=str(user['id']))

    return jsonify({
        'sukses': True,
        'token': token,
        'username': user['username'],
        'role': user.get('role', 'operator')
    }), 200