from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager

from flask_marshmallow import Marshmallow
from marshmallow import fields, ValidationError
from marshmallow.validate import Length, Range

from models import *

DATABASE_URI = 'mysql://root:password@localhost/ap_4'


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'some-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_TOKEN_LOCATION'] = ['headers', 'query_string']

    jwt = JWTManager(app)
    db = SQLAlchemy(app)
    ma = Marshmallow(app)
    bcrypt = Bcrypt(app)

    class UserSchema(ma.Schema):
        phone = fields.Str(validate=Length(equal=12), required=True)
        password = fields.Str(validate=Length(min=6, max=32), required=True)
        firstName = fields.Str(validate=Length(min=3, max=32), required=True)
        lastName = fields.Str(validate=Length(min=3, max=32), required=True)
        age = fields.Int(strict=True, validate=[Range(min=18, error="Age must be greater or equal to 18")],
                         required=True)
        monthlyEarnings = fields.Int(required=True)
        occupation = fields.Str(validate=Length(max=32), required=True)
        isAdmin = fields.Bool(required=True)

    class UserDisplaySchema(ma.Schema):
        class Meta:
            fields = ("phone", "firstName", "lastName", "age", "monthlyEarnings", "occupation")

    class LoanSchema(ma.Schema):
        amount = fields.Int(strict=True, validate=[Range(min=1, error="Amount must be greater or equal to 1")],
                            required=True)
        isPaid = fields.Bool(required=True)
        createdDate = fields.Int(required=True, validate=[Range(min=1)])
        months = fields.Int(strict=True, validate=[Range(min=1)], required=True)

    class LoanDisplaySchema(ma.Schema):
        class Meta:
            fields = ("loanId", "amount", "isPaid", "createdDate", "months", "userId", "payments")

    class PaymentSchema(ma.Schema):
        amount = fields.Int(strict=True, validate=[Range(min=1, error="Amount must be greater or equal to 1")],
                            required=True)
        paidDate = fields.Int(required=True)

    class PaymentDisplaySchema(ma.Schema):
        class Meta:
            fields = ("paymentId", "amount", "paidDate", "loanId")

    user_schema = UserSchema()
    user_display_schema = UserDisplaySchema()
    loan_schema = LoanSchema()
    loan_display_schema = LoanDisplaySchema()
    payment_schema = PaymentSchema()
    payments_display_schema = PaymentDisplaySchema(many=True)

    @app.route("/user", methods=["POST"])
    def create_user():
        try:
            data = user_schema.load(request.get_json())
            if not data['phone'].isdecimal(): return jsonify({"message": "Invalid parameters"}), 400

            # user with this phone already exists
            if db.session.query(User).filter_by(phone=data['phone']).first() is not None:
                return jsonify({"message": "User with this phone already exists"}), 409

            data['password'] = bytes(bcrypt.generate_password_hash(data['password']).decode('utf-8'), 'utf-8')
            data['api_key'] = create_access_token(identity=data['phone'], expires_delta=datetime.timedelta(minutes=30))

            user = User(**data)
            db.session.add(user)
            db.session.commit()
            return jsonify(userId=user.userId), 201
        except ValidationError as e:
            print(e)
            return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/user/login", methods=["GET"])
    def user_login():
        try:
            auth = request.authorization
            if not auth or not auth.username or not auth.password:
                return jsonify({"message": "Invalid parameters"}), 400

            user: User = db.session.query(User).filter_by(phone=auth.username).first()
            if user is None:
                return jsonify({"message": "User not found"}), 404
            if not bcrypt.check_password_hash(user.password, auth.password):
                return jsonify({"message": "Incorrect user credentials"}), 401
            user.api_key = create_access_token(identity=auth.username, expires_delta=datetime.timedelta(minutes=30))
            db.session.commit()
            return jsonify(userId=user.userId, api_key=user.api_key), 200
        except Exception as e:
            print(e)
            return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/user/logout", methods=["GET"])
    @jwt_required()
    def logout():
        current_user_identity = get_jwt_identity()
        current_user = db.session.query(User).filter_by(phone=current_user_identity).first()
        try:
            if current_user is None:
                return jsonify({"message": "Not found"}), 404

            current_user.api_key = ''
            db.session.commit()
            return jsonify({"message": "Success"}), 200
        except:
            return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/user/<userId>", methods=["GET", "DELETE"])
    @jwt_required()
    def get_user(userId):
        current_user_identity = get_jwt_identity()
        current_user = db.session.query(User).filter_by(phone=current_user_identity).first()
        try:
            uid = int(userId)
        except ValueError:
            return jsonify({"message": "Invalid parameters"}), 400

        user = db.session.query(User).filter_by(userId=uid).first()
        if user is None:
            return jsonify({"message": "User not found"}), 404

        if request.method == "GET":
            if user.userId != current_user.userId and not current_user.isAdmin:
                return jsonify({"message": "Forbidden!"}), 403
            result = user_display_schema.dump(user)
            return jsonify(result), 200

        elif request.method == "DELETE":
            try:
                if current_user is None:
                    return jsonify({"message": "Incorrect user credentials"}), 401
                if user.userId != current_user.userId and not current_user.isAdmin:
                    return jsonify({"message": "Forbidden!"}), 403
                db.session.delete(user)
                db.session.commit()
                return jsonify({"message": "Success"}), 200
            except:
                return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/loan", methods=["POST"])
    @jwt_required()
    def loan_post():
        current_user_identity = get_jwt_identity()
        current_user = db.session.query(User).filter_by(phone=current_user_identity).first()
        try:
            data = loan_schema.load(request.get_json())

            if current_user is None:
                return jsonify({"message": "Incorrect user credentials"}), 401

            from datetime import datetime
            d = datetime.fromtimestamp(data['createdDate'])
            data['createdDate'] = str(d.year) + '-' + str(d.month) + '-' + str(d.day)
            data['userId'] = current_user.userId

            loan = Loan(**data)
            db.session.add(loan)
            db.session.commit()
            return jsonify({"loanId": loan.loanId}), 200
        except:
            return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/loan/<loanId>", methods=["GET"])
    @jwt_required()
    def get_loan(loanId):
        current_user_identity = get_jwt_identity()
        current_user = db.session.query(User).filter_by(phone=current_user_identity).first()
        try:
            try:
                id = int(loanId)
            except ValueError:
                return jsonify({"message": "Invalid parameters"}), 400

            loan = db.session.query(Loan).filter_by(loanId=id).first()
            if loan is None:
                return jsonify({"message": "Loan not found"}), 404
            if loan.userId != current_user.userId and not current_user.isAdmin:
                return jsonify({"message": "Forbidden!"}), 403

            payments = db.session.query(Payment).filter_by(loanId=id).all()
            payments_dict = payments_display_schema.dump(payments)

            result = loan_display_schema.dump(loan)
            temp = []
            for p in payments_dict:
                temp.append(p['paymentId'])

            result['payments'] = temp

            return jsonify(result), 200
        except:
            return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/pay/<loanId>", methods=["POST"])
    @jwt_required()
    def pay_loan(loanId):
        current_user_identity = get_jwt_identity()
        current_user = db.session.query(User).filter_by(phone=current_user_identity).first()
        try:
            try:
                id = int(loanId)
            except ValueError:
                return jsonify({"message": "Invalid parameters"}), 400

            data = payment_schema.load(request.get_json())

            loan = db.session.query(Loan).filter_by(loanId=id).first()
            if loan is None:
                return jsonify({"message": "Loan not found"}), 404

            if loan.isPaid:
                return jsonify({"message": "Invalid parameters - Loan is paid"}), 400

            if current_user is None:
                return jsonify({"message": "User not found"}), 404

            if current_user.userId != loan.userId:
                return jsonify({"message": "No permissions"}), 401

            from datetime import datetime
            d = datetime.fromtimestamp(data['paidDate'])
            data['paidDate'] = str(d.year) + '-' + str(d.month) + '-' + str(d.day)
            data['loanId'] = id

            payment = Payment(**data)
            db.session.add(payment)
            db.session.commit()

            # checking if paid
            payments = db.session.query(Payment).filter_by(loanId=id).all()
            payments_dict = payments_display_schema.dump(payments)
            sm = 0
            for p in payments_dict:
                sm += p['amount']

            if sm >= loan.amount:
                loan.isPaid = True
                db.session.commit()
            ##########

            return jsonify({"paymentId": payment.paymentId}), 200
        except Exception as e:
            print(e)
            return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/pay/<loanId>", methods=["GET"])
    @jwt_required()
    def get_payment(loanId):
        current_user_identity = get_jwt_identity()
        current_user = db.session.query(User).filter_by(phone=current_user_identity).first()
        try:
            try:
                id = int(loanId)
            except ValueError:
                return jsonify({"message": "Invalid parameters"}), 400

            payment = db.session.query(Payment).filter_by(loanId=id).all()
            if payment is None:
                return jsonify({"message": "Payments not found"}), 404
            loan = db.session.query(Loan).filter_by(loanId=payment[0].loanId).first()
            if loan.userId != current_user.userId and not current_user.isAdmin:
                return jsonify({"message": "Forbidden!"}), 403

            print(payment)
            result = payments_display_schema.dump(payment)
            return jsonify(result), 200
        except Exception as e:
            print(e)
            return jsonify({"message": "Invalid parameters"}), 400

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
