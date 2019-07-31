from urllib import request
from jose import jwt
from social_core.backends.auth0 import Auth0OAuth2
from social_core.exceptions import AuthFailed


class Auth0(Auth0OAuth2):
    """Auth0 OAuth authentication backend"""
    name = 'auth0'
    
    def auth_complete(self, *args, **kwargs):
        try:
            self.process_error(self.data)
        except AuthFailed as e:
            if 'verify your email' in str(e):
                return redirect('/?verify_email=true')

        return super().auth_complete(*args, **kwargs)

    def get_user_details(self, response):
        # Obtain JWT and the keys to validate the signature
        id_token = response.get('id_token')
        jwks = self.get_json(self.api_path('.well-known/jwks.json'))
        issuer = self.api_path()
        audience = self.setting('KEY')  # CLIENT_ID
        payload = jwt.decode(id_token,
                              jwks,
                              algorithms=['RS256'],
                              audience=audience,
                              issuer=issuer)

        return {'username': payload['nickname'],
                'email': payload['name'],
                'email_verified': payload.get('email_verified', False),
                'picture': payload['picture'],
                'user_id': payload['sub']}
