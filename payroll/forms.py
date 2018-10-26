import json

import requests

from sentry_sdk import capture_message, configure_scope

from django import forms
from django.contrib.auth.models import User

from .models import UserZipcode


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

        userzipcode = UserZipcode.objects.create(user=user,
                                                 zipcode=self.cleaned_data['zipcode'])

        user.userzipcode = userzipcode

        user.save()

        self.add_to_salsa(user)

        return user

    def add_to_salsa(self, user):
        payload = {
            "header": {},
            "payload": {
                "activityId": "73cf9597-3992-4256-b0a2-fa893a65caff",
                "aid": "f3f7d6cd-d5a0-4814-938e-23a97a2ccad6",
                "cid": "",
                "contactMethods": {
                    "Email": {
                        "label": "Email",
                        "optedIn": True
                    }
                },
                "contentChannels": {
                    "38c6c0e0-862a-427d-8fd7-13ab6e2c9824": {
                        "label": "Advocacy",
                        "optedIn": True
                    },
                    "3ec33e32-e774-4f22-9904-e8d4e67ce636": {
                        "label": "Fundraising",
                        "optedIn": True
                    },
                    "af9c6537-7ad2-4d6f-8ecb-7b386dbaff11": {
                        "label": "General",
                        "optedIn": True
                    }
                },
                "data": {
                    "Address@Home@Zip": {
                        "label": "Zip Code",
                        "required": True,
                        "value": user.userzipcode.zipcode
                    },
                    "PersonCensus@FirstName": {
                        "label": "First Name",
                        "required": True,
                        "value": user.first_name
                    },
                    "PersonCensus@LastName": {
                        "label": "Last Name",
                        "required": True,
                        "value": user.last_name
                    },
                    "PersonContact@Email@Value": {
                        "label": "Email Address",
                        "required": True,
                        "value": user.email
                    },
                    "termsAndConditions": {}
                },
                "eid": "82a20ce0-6591-4a90-a77d-d73599ec9b43",
                "eType": "Template",
                "oid": "557dfa6a-8ce6-4e82-85c2-abd6c61f8767",
                "pid": "c1868391-9dcc-49bf-8eff-00c18d867bea",
                "salsaTrack": None,
                "userInteractionId": "8d04604b-a237-4873-990f-689d218312bd"
            }
        }

        salsa_url = 'https://org-557dfa6a-8ce6-4e82-85c2-abd6c61f8767.salsalabs.org/api/activity/submission/subscription'

        signup = requests.post(salsa_url,
                               data=json.dumps(payload),
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
