from flask import Blueprint, request, jsonify
from app.services.authServices import AuthService
from app.services.userServices import UserService
from app.utils.permissionRequired import role_required
from app.schemas.userSchema import UserLoginSchema,UserResponseSchema,ChangePasswordSchema,ForgotPasswordRequest,ResetPasswordRequest
from app.extension import db

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    create_access_token,
    create_refresh_token,
    get_jwt,
)
from app.database.redis_client import add_jwt_id_to_blocklist


auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.route('/login', methods=['POST'])
def login_user():
    try:
        data = request.get_json()
        try:
            login_data = UserLoginSchema(**data)
        except :
            return jsonify({"error":"validation_errors"}), 422
   

        if not UserService.user_exists(login_data.email):
            return jsonify({"error": "User does not exists"}), 404  

        user, tokens = AuthService.user_login(login_data)
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401
        
        if not user.is_active:
            return jsonify({"error": "User account is inactive. Please contact support."}), 403
        if not user.is_verified:
            return jsonify({"error": "Please verify your email before logging in."}), 403
        
        user.update_last_active()
        db.session.commit() 
        
        role_name = user.role.role_name if user.role else "unknown"
        login_type = {
            "super_admin": "Super Admin ",
            "client_admin": "Client Admin ",
            "manager": "Manager",
            "employee": "Employee",
            "normal_user": "Normal User "
        }.get(role_name, "Unknown Role ")
        

        user_response = UserResponseSchema.model_validate(user)
        user_data = user_response.model_dump()


        user_data["role_name"] = user.role.role_name if user.role else None
        user_data["department_name"] = user.department.department_name if user.department else None
        return jsonify({
            "message": f"{login_type} Logged in successfully!",
            "user": user_data,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "force_reset_password": user.must_reset_password or False
        }), 200

    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500
    

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout_user():
    try:
        jwt_payload = get_jwt()
        jti = jwt_payload.get("jti")

        if not jti:
            return jsonify({"error": "Invalid token"}), 400

        add_jwt_id_to_blocklist(jti)

        return jsonify({"message": "Successfully logged out"}), 200

    except Exception as e:
   
        return jsonify({"error": "Internal server error"}), 500
    

@auth_bp.post("/refresh_access_token")
@jwt_required(refresh=True)
def refresh_access():
    try:
        identity = get_jwt_identity()
        jwt_payload = get_jwt()
        refresh_jti = jwt_payload["jti"]

  
        add_jwt_id_to_blocklist(refresh_jti)

        new_access_token = create_access_token(identity=identity)
        new_refresh_token = create_refresh_token(identity=identity)

        return jsonify({
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "message": "Access token refreshed successfully"
        }), 200

    except:
        return jsonify({"error": "Token refresh failed"}), 500


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def user_profile():
    user_id = get_jwt_identity()  # Get user identifier stored in the token
    # Now do something with user_id, e.g. fetch user data from DB
    return jsonify({"message": f"Hello user {user_id}, you are logged in!"}), 200


@auth_bp.route('/change_password', methods=['POST'])
@jwt_required()
def password_change():
    try:
        data = request.get_json()

        try:
            change_data = ChangePasswordSchema(**data)
            
        except:
            return jsonify({"error":"validation_errors"}), 422

        
        if change_data.new_password != change_data.confirm_password:
            return jsonify({"error": "Passwords do not match"}), 400
        
        if change_data.old_password == change_data.new_password:
            return jsonify({"error": "New password must be different from old password"}), 400
    
        user_id = get_jwt_identity()

 
        success, message = AuthService.change_user_password(
            user_id=user_id,
            old_password=change_data.old_password,
            new_password=change_data.new_password
        )
       

        if not success:
            return jsonify({"error": message}), 400

        return jsonify({"message": message}), 200

    except:
        return jsonify({"error": "Internal Server Error"}), 500
    

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        try:
            request_data = ForgotPasswordRequest(**data)
        except:
            return jsonify({"error":"validation_errors"}), 422
   

        response = AuthService.handle_forgot_password(request_data.email)
        if "error" in response:
            return jsonify(response), 400
        
        return jsonify(response), 200

    except :
        return jsonify({"error": "Internal server error"}), 500
    

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        data = request.get_json()
        try:
            request_data = ResetPasswordRequest(**data)
        except:
             return jsonify({"error":"validation_errors"}), 422

        response = AuthService.handle_reset_password(request_data.token, request_data.new_password)

        if "error" in response:
            return jsonify(response), 400

        return jsonify(response), 200

    except:
        return jsonify({"error": "Internal server error"}), 500
    




@auth_bp.route('/deactivate_user/<string:user_id>', methods=['POST'])
@jwt_required()
@role_required(['super_admin','client_admin'])
def deactivate_user_route(user_id):
    try:
        user = UserService.get_user_by_id(user_id)

        if not user:
            return jsonify({"error": "User not found"}), 404
        if not user.is_active:
            return jsonify({"error": "User already Deactivated"}), 400

        if AuthService.deactivate_user(user):
            add_jwt_id_to_blocklist(user_id)
            return jsonify({"message": "User deactivated successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500
    

@auth_bp.route('/activate_user/<string:user_id>', methods=['POST'])
@jwt_required()
@role_required(['super_admin','client_admin'])
def activate_user_route(user_id):
    try:
        user = UserService.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        if user.is_active:
            return jsonify({"error": "User already activated"}), 400

        if AuthService.activate_user(user):
            return jsonify({"message": "User activated successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500



@auth_bp.route('/all_clients_and_normal_users', methods=['GET'])
@jwt_required()
@role_required(['super_admin'])
def all_clients_and_normal_users():
    try:
        data = UserService.get_all_clients_with_users_and_normal_users()
        return jsonify({
            "status": "success",
            "data": data
        }), 200
    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500
    

@auth_bp.route('/all_clientsadmin_and_normal_users', methods=['GET'])
@jwt_required()
@role_required(['super_admin'])
def all_clients_admin_and_normal_users():
    try:
        data = UserService.get_all_clientadmins_and_normal_users()
        return jsonify({
            "status": "success",
            "data": data
        }), 200
    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500