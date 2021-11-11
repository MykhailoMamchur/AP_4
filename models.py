import datetime

from sqlalchemy import create_engine, Column, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql.sqltypes import DECIMAL, INTEGER, DATE, VARCHAR, BOOLEAN, BINARY

#from PWD import PWD

Base = declarative_base()

#DB_URI = f"mysql://admin:{PWD}@localhost/ap_4?charset=utf8mb4"
DB_URI = "mysql://root:password@localhost/ap_4"


class Payment(Base):
    __tablename__ = "Payment"
    paymentId = Column(INTEGER, primary_key=True)
    amount = Column(INTEGER, nullable=False)
    paidDate = Column(VARCHAR(255), nullable=False)
    loanId = Column(INTEGER, ForeignKey("Loan.loanId", ondelete="CASCADE"), nullable=False)
    loan = relationship("Loan", back_populates="payments")

    def __init__(self, amount, paidDate, loanId):
        self.amount = amount
        self.paidDate = paidDate
        self.loanId = loanId


class Loan(Base):
    __tablename__ = "Loan"
    loanId = Column(INTEGER, primary_key=True)
    amount = Column(INTEGER, nullable=False)
    isPaid = Column(BOOLEAN, nullable=False)
    createdDate = Column(VARCHAR(255), nullable=False)
    months = Column(INTEGER, nullable=False)
    payments = relationship("Payment", back_populates="loan")
    userId = Column(INTEGER, ForeignKey("User.userId", ondelete="CASCADE"), nullable=False)
    user = relationship("User", back_populates="loans")

    def __init__(self, amount, isPaid, createdDate, months, userId):
        self.amount = amount
        self.isPaid = isPaid
        self.createdDate = createdDate
        self.months = months
        self.userId = userId

    def __repr__(self):
        return f"Left: {self.amount - sum(payment.amount for payment in self.payments)}"


class User(Base):
    __tablename__ = "User"
    userId = Column(INTEGER, primary_key=True)
    loans = relationship(Loan, back_populates="user")
    phone = Column(VARCHAR(255), nullable=False, unique=True)
    password = Column(BINARY(60), nullable=False)
    firstName = Column(VARCHAR(255), nullable=False)
    lastName = Column(VARCHAR(255), nullable=False)
    age = Column(INTEGER, nullable=False)
    monthlyEarnings = Column(INTEGER, nullable=False)
    occupation = Column(VARCHAR(255), nullable=False)
    api_key = Column(VARCHAR(32), nullable=False, unique=True)

    def __init__(self, phone, password, firstName, lastName, age, monthlyEarnings, occupation, api_key):
        self.phone = phone
        self.password = password
        self.firstName = firstName
        self.lastName = lastName
        self.age = age
        self.monthlyEarnings = monthlyEarnings
        self.occupation = occupation
        self.api_key = api_key

    def __repr__(self):
        return f"{self.firstName} {self.lastName} {self.loans}"


if __name__ == '__main__':

    engine = create_engine(DB_URI, echo=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine, )
    Session = sessionmaker(bind=engine)

    with Session() as session:
        users = []
        loans = []
        for i in range(1):
            usr = User("+3823424242", "pwd", "Петро", "Шпак", 42, 56, "job")
            session.add(usr)
            users.append(usr)
        session.commit()

        print(session.query(User).all()[0])

        for usr in users:
            loan1 = Loan(100, 0, datetime.datetime.now().ctime(), 3, usr.userId)
            loan2 = Loan(100, 0, datetime.datetime.now().ctime(), 3, usr.userId)
            session.add(loan1)
            session.add(loan2)

            loans.append(loan1)
            loans.append(loan2)

        session.commit()

        print(session.query(User).all()[0])

        for loan in loans:
            payment1 = Payment(50, datetime.datetime.now().ctime(), loan.loanId)
            payment2 = Payment(50, datetime.datetime.now().ctime(), loan.loanId)
            session.add(payment1)
            session.add(payment2)

        session.commit()

        print(session.query(User).all()[0])
