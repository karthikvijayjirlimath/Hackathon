from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DateField
from wtforms.validators import DataRequired, Email, ValidationError
from datetime import date

class ManualPatientForm(FlaskForm):
    name = StringField('Patient Name', validators=[DataRequired()])
    dob = DateField('Date of Birth', validators=[DataRequired()], format='%Y-%m-%d')
    insurance_policy_id = StringField('Insurance Policy ID', validators=[DataRequired()])
    email = StringField('Email ID', validators=[Email()])
    refund_bank_account_id = StringField('Refund Bank Account ID')
    submit = SubmitField('Register Patient')

    def validate_dob(self, dob):
        if dob.data > date.today():
            raise ValidationError('Date of Birth cannot be in the future.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')
