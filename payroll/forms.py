import requests

from sentry_sdk import capture_message, configure_scope

from django import forms
from django.contrib.auth.models import User
from django.conf import settings

from .models import UserZipCode


class SignupForm(forms.Form):
    email = forms.EmailField(label='Email')
    password = forms.CharField(label='Password')
    first_name = forms.CharField(label='First name')
    last_name = forms.CharField(label='Last name')
    zipcode = forms.CharField(label='Zip code')

    def clean_email(self):
        email = self.cleaned_data['email']

        existing_user = User.objects.filter(username=email).first()

        if existing_user:
            raise forms.ValidationError('The email address "{}" is already in use'.format(email))

        return email

    def make_user(self):

        user = User.objects.create_user(self.cleaned_data['email'],
                                        self.cleaned_data['email'],
                                        self.cleaned_data['password'])

        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        userzipcode = UserZipCode.objects.create(user=user,
                                                 zipcode=self.cleaned_data['zipcode'])

        user.userzipcode = userzipcode

        user.save()

        self.add_to_salsa(user)

        return user

    def add_to_salsa(self, user):

        params = {
            'zipcode': user.userzipcode.zipcode,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }

        payload = settings.SALSA_PAYLOAD % params

        signup = requests.post(settings.SALSA_URL,
                               data=payload,
                               headers={'content-type':
                                        'application/json; charset=utf-8'})

        if signup.status_code > 200 or signup.json().get('errors'):
            with configure_scope() as scope:
                scope.user = {
                    'id': user.id,
                    'email': user.email
                }
                scope.set_extra(signup.json())
                capture_message('Salsa returned an error while capturing email "{}"'.format(user.email))
