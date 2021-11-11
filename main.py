from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

from flask_marshmallow import Marshmallow
from marshmallow import fields
from marshmallow.validate import Length, Range
from sqlalchemy.sql.expression import null, true
from sqlalchemy.sql.functions import user

from models import *
from uuid import uuid4

DATABASE_URI = 'mysql://root:password@localhost/ap_4'

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db = SQLAlchemy(app)
    ma = Marshmallow(app)
    bcrypt = Bcrypt(app)

    class UserSchema(ma.Schema):
        phone = fields.Str(validate=Length(equal=12), required=True)
        password = fields.Str(validate=Length(min=6, max=32), required=True)
        firstName = fields.Str(validate=Length(min=3, max=32), required=True)
        lastName = fields.Str(validate=Length(min=3, max=32), required=True)
        age = fields.Int(strict=True, validate=[Range(min=18, error="Age must be greater or equal to 18")], required=True)
        monthlyEarnings = fields.Int(required=True)
        occupation = fields.Str(validate=Length(max=32), required=True)

    class UserDisplaySchema(ma.Schema):
        class Meta:
            fields = ("phone", "firstName", "lastName", "age", "monthlyEarnings", "occupation")

    class UserLoginSchema(ma.Schema):
        phone = fields.Str(validate=Length(equal=12), required=True)
        password = fields.Str(validate=Length(min=6, max=32), required=True)

    class UserApiKeySchema(ma.Schema):
        api_key = fields.Str(validate=Length(equal=32), required=True)
        
    class LoanSchema(ma.Schema):
        amount = fields.Int(strict=True, validate=[Range(min=1, error="Amount must be greater or equal to 1")], required=True)
        isPaid = fields.Bool(required=True)
        createdDate = fields.Int(required=True, validate=[Range(min=1)])
        months = fields.Int(strict=True, validate=[Range(min=1)], required=True)

    class LoanDisplaySchema(ma.Schema):
        class Meta:
            fields = ("loanId", "amount", "isPaid", "createdDate", "months", "userId", "payments")

    class PaymentSchema(ma.Schema):
        amount = fields.Int(strict=True, validate=[Range(min=1, error="Amount must be greater or equal to 1")], required=True)
        paidDate = fields.Int(required=True)

    class PaymentDisplaySchema(ma.Schema):
        class Meta:
            fields = ("paymentId", "amount", "paidDate", "loanId")

    user_schema = UserSchema()
    user_display_schema = UserDisplaySchema()
    user_login_schema = UserLoginSchema()
    user_apikey_schema = UserApiKeySchema()
    loan_shema = LoanSchema()
    loan_display_schema = LoanDisplaySchema()
    payment_schema = PaymentSchema()
    payments_display_schema = PaymentDisplaySchema(many=True)

    @app.route("/user", methods=["POST"])
    def create_user():
        try:
            data = user_schema.load(request.get_json())
            if not data['phone'].isdecimal(): return jsonify({"message": "Invalid parameters"}), 400

            #user with this phone already exists
            if db.session.query(User).filter_by(phone=data['phone']).first() is not None:
                return jsonify({"message": "User with this phone already exists"}), 409

            data['password'] = bytes(bcrypt.generate_password_hash(data['password']).decode('utf-8'), 'utf-8')
            data['api_key'] = uuid4().hex

            user = User(**data)
            db.session.add(user)
            db.session.commit()
            return jsonify(userId=user.userId), 201
        except:
            return jsonify({"message": "Invalid parameters"}), 400


    @app.route("/user/login", methods=["GET"])
    def user_login():
        try:
            data = user_login_schema.load(request.get_json())
            if not data['phone'].isdecimal(): return jsonify({"message": "Invalid parameters"}), 400

            user: User = db.session.query(User).filter_by(phone=data['phone']).first()
            if user is None:
                return jsonify({"message": "User not found"}), 404
            if not bcrypt.check_password_hash(user.password, data['password']):
                return jsonify({"message": "Incorrect user credentials"}), 401
            return jsonify(userId=user.userId, api_key=user.api_key), 200
        except: 
            return jsonify({"message": "Invalid parameters"}), 400


    @app.route("/user/logout", methods=["GET"])
    def logout():
        try:
            data = user_apikey_schema.load(request.values)

            user = db.session.query(User).filter_by(api_key=data['api_key']).first()
            if user is None:
                return jsonify({"message": "Not found"}), 404
            #generating new api_key
            user.api_key = uuid4().hex
            db.session.commit()
            return jsonify({"message": "Success"}), 200
        except:
            return jsonify({"message": "Invalid parameters"}), 400


    @app.route("/user/<userId>", methods=["GET", "DELETE"])
    def get_user(userId):
        try:
            uid = int(userId)
        except ValueError:
            return jsonify({"message": "Invalid parameters"}), 400

        user = db.session.query(User).filter_by(userId=uid).first()
        if user is None:
            return jsonify({"message": "User not found"}), 404

        if request.method == "GET":
            result = user_display_schema.dump(user)
            return jsonify(result), 200

        elif request.method == "DELETE":
            try:
                data = user_apikey_schema.load(request.values)
                user = db.session.query(User).filter_by(userId=uid, api_key=data['api_key']).first()
                if user is None:
                    return jsonify({"message": "Incorrect user credentials"}), 401
                db.session.delete(user)
                db.session.commit()
                return jsonify({"message": "Success"}), 200
            except:
                return jsonify({"message": "Invalid parameters"}), 400


    @app.route("/loan", methods=["POST"])
    def loan_post():
        try:
            data = loan_shema.load(request.get_json())
            key = user_apikey_schema.load(request.values)['api_key']

            user = db.session.query(User).filter_by(api_key=key).first()
            if user is None:
                return jsonify({"message": "Incorrect user credentials"}), 401
            
            from datetime import datetime
            d = datetime.fromtimestamp(data['createdDate'])
            data['createdDate'] = str(d.year) + '-' + str(d.month) + '-' + str(d.day)
            data['userId'] = user.userId
            
            loan = Loan(**data)
            db.session.add(loan)
            db.session.commit()
            return jsonify({"loanId": loan.loanId}), 200
        except:
            return jsonify({"message": "Invalid parameters"}), 400


    @app.route("/loan/<loanId>", methods=["GET"])
    def get_loan(loanId):
        try:
            try:
                id = int(loanId)
            except ValueError:
                return jsonify({"message": "Invalid parameters"}), 400

            loan = db.session.query(Loan).filter_by(loanId=id).first()
            if loan is None:
                return jsonify({"message": "Loan not found"}), 404

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
    def pay_loan(loanId):
        try:
            try:
                id = int(loanId)
            except ValueError:
                return jsonify({"message": "Invalid parameters"}), 400

            data = payment_schema.load(request.get_json())
            key = user_apikey_schema.load(request.values)['api_key']

            loan = db.session.query(Loan).filter_by(loanId=id).first()
            if loan is None:
                return jsonify({"message": "Loan not found"}), 404

            if loan.isPaid:
                return jsonify({"message": "Invalid parameters - Loan is paid"}), 400

            user = db.session.query(User).filter_by(api_key=key).first()
            if user is None:
                return jsonify({"message": "User not found"}), 404

            if user.userId != loan.userId:
                return jsonify({"message": "No permissions"}), 401
            
            from datetime import datetime
            d = datetime.fromtimestamp(data['paidDate'])
            data['paidDate'] = str(d.year) + '-' + str(d.month) + '-' + str(d.day)
            data['loanId'] = id

            payment = Payment(**data)
            db.session.add(payment)
            db.session.commit()

            #checking if paid
            payments = db.session.query(Payment).filter_by(loanId=id).all()
            payments_dict = payments_display_schema.dump(payments)
            sum = 0
            for p in payments_dict: 
                sum += p['amount']

            if sum >= loan.amount:
                loan.isPaid = True
                db.session.commit()
            ##########

            return jsonify({"paymentId": payment.paymentId}), 200
        except:
            return jsonify({"message": "Invalid parameters"}), 400

    @app.route("/pay/<loanId>", methods=["GET"])
    def get_payment(loanId):
        try:
            try:
                id = int(loanId)
            except ValueError:
                return jsonify({"message": "Invalid parameters"}), 400

            payment = db.session.query(Payment).filter_by(loanId=id).all()
            if payment is None:
                return jsonify({"message": "Payments not found"}), 404

            print(payment)
            result = payments_display_schema.dump(payment)
            return jsonify(result), 200
        except:
            return jsonify({"message": "Invalid parameters"}), 400


    @app.route('/createAccount', methods=["POST"])
    def create_account():
        reg_data = user_schema.load(request.get_json())

        reg_data.password = bcrypt.generate_password_hash(reg_data.password)
        usr = User(**reg_data.load, token=uuid4())
        db.session.add(usr)
        db.session.commit()

        return jsonify(fname=usr.fname, lname=usr.lname, username=usr.username, atype=usr.atype, token=usr.token), 200



    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)