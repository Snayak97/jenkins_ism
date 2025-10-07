from flask import Blueprint, request, jsonify, request
from app.services.userServices import UserService
from app.schemas.userSchema import UserResponseSchema,UserCreateSchema,UserUpdatePutSchema,UserUpdatePatchSchema
from app.utils.mailUtils import EmailService
from app.models.userModel import User,Role
from app.extension import db
from app.utils.permissionRequired import role_required
from app.database.redis_client import add_jwt_id_to_blocklist

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
)

from pydantic import ValidationError
user_bp = Blueprint("user", __name__, url_prefix="/api/v1/user")


@user_bp.route('/signup', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        try:
            user_data = UserCreateSchema(**data)
        except :
            return jsonify({"error":"validation_errors"}), 422

        if UserService.user_exists(user_data.email):
            return jsonify({"error": "User already exists Please Log in."}), 403  

        user = UserService.create_user(user_data)
        
        user_name = getattr(user, 'name', None) or getattr(user, 'user_name', None)

        email_result = EmailService.send_verification_email(user.email, user_name)
        user_response = UserResponseSchema.model_validate(user)
       

        return jsonify({
            "message": "User created. Please verify your email.",
            "user": user_response.model_dump(),
            "email_sent": email_result["success"],
            "email_error": email_result.get("message")
        }), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route('/verify-email/<token>')
def verify_email(token):
    try:
        email = EmailService.verify_token(token)
        if not email:
            return jsonify({"error": "Invalid or expired link"}), 400

        user = UserService.verify_user_email(email)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        if user.is_verified: 
            return jsonify({"error": "Email is already verified."}), 400
        
        user.is_verified = True
        user.is_active = True
        db.session.commit()

        EmailService.send_welcome_email(user.email, getattr(user, 'name', None) or getattr(user, 'user_name', None))
        return jsonify({"message": "Email verified successfully!"}), 200

    except:
        return jsonify({"error": "Internal server error"}), 500

@user_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    try:
        data = request.get_json()
        email = data.get('email')

        if not email:
            return jsonify({"error": "Email is required"}), 400

        user = UserService.verify_user_email(email)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if user.is_verified:
            return jsonify({"message": "Email already verified."}), 200

        email_result = EmailService.send_verification_email(user.email, getattr(user, 'name', None) or getattr(user, 'user_name', None))
        if email_result["success"]:
            return jsonify({"message": "Verification email resent!"}), 200
        else:
            return jsonify({"error": email_result["message"]}), 500

    except:
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route('/get_users', methods=['GET'])
def get_all_users():
    try:
        users = UserService.get_all_users()
        users_response = [UserResponseSchema.model_validate(user).model_dump() for user in users]
        return jsonify({"users": users_response}), 200
    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500
    
    
@user_bp.route('/get_user/<string:user_id>', methods=['GET'])
def get_a_users(user_id):
    try:
        user = UserService.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        users_response = UserResponseSchema.model_validate(user).model_dump()
        return jsonify({"users": users_response}), 200
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500



@user_bp.route('/delete_user/<string:user_id>', methods=['DELETE'])
@jwt_required()
@role_required(['super_admin'])
def delete_user(user_id):
    try:
        deleted = UserService.delete_user(user_id)
        if not deleted:
            return jsonify({"error": "User not found"}), 404
        add_jwt_id_to_blocklist(user_id)
        return jsonify({"message": "User deleted successfully"}), 200

    except:
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route('/update_user/<string:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        data = request.get_json()
        try:
            update_data = UserUpdatePutSchema(**data)
        except :
            return jsonify({"error":"validation_errors"}), 422

        user = UserService.update_user_put(user_id, update_data)
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"message": "User fully updated", "user": UserResponseSchema.model_validate(user).model_dump()}), 200
    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route('/update_user/<string:user_id>', methods=['PATCH'])
def update_user_patch(user_id):
    try:
        data = request.get_json()
        try:
            update_data = UserUpdatePatchSchema(**data)
        except:
            return jsonify({"error":"validation_errors"}), 422

        user = UserService.update_user_patch(user_id, update_data)
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"message": "User partially updated", "user": UserResponseSchema.model_validate(user).model_dump()}), 200
    except:
        return jsonify({"error": "Internal server error"}), 500
    


@user_bp.route('/delete-all-users', methods=['DELETE'])
def delete_all_users():
    try:
        users = User.query.all()
        num_deleted = len(users)

        for user in users:
            db.session.delete(user)

        db.session.commit()
        return {"message": f"Deleted {num_deleted} users successfully"}, 200

    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}, 500


@user_bp.route('/superadmin', methods=['POST'])
def create_superadmin():
    try:
        superadmin_role = Role.query.filter_by(role_name="super_admin").first()
        if not superadmin_role:
            return jsonify({"error": "Role 'super_admin' not found. Please seed roles first."}), 404

        existing = User.query.filter_by(email="superadmin@gmail.com").first()
        if existing:
            return jsonify({"message": "Superadmin already exists."}), 200

        user = User(
            user_name="SuperAdmin",
            email="superadmin@gmail.com",
            mobile_number="9999999999",
            is_verified=True,
            is_active=True,
            role_id=superadmin_role.role_id
        )
        user.set_password("Superadmin@111")

        db.session.add(user)
        db.session.commit()

        return jsonify({"message": "Superadmin created successfully."}), 201

    except Exception as e:
        print("Error creating superadmin:", e)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
