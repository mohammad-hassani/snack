import json
from datetime import timedelta
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from chat.models import Invitation, Membership, Workspace


class FrontendApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.token = self.client.get('/api/session/').json()['csrfToken']

    def post(self, path, data=None, method='post', **headers):
        return getattr(self.client, method)(path, json.dumps(data or {}), content_type='application/json', HTTP_X_CSRFTOKEN=self.token, **headers)

    def signup(self):
        response = self.post('/api/auth/signup/', {'email': 'new@example.com', 'first_name': 'مینا', 'password1': 'A-long-test-password-123', 'password2': 'A-long-test-password-123'})
        self.assertEqual(response.status_code, 201, response.content)
        self.token = response.json()['csrfToken']
        return User.objects.get(username='new@example.com')

    def test_session_authentication_csrf_and_workspace_creation(self):
        self.assertIsNone(self.client.get('/api/session/').json()['user'])
        self.assertEqual(self.client.get('/api/workspaces/').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login/', {}).status_code, 403)
        user = self.signup()
        session = self.client.get('/api/session/')
        self.assertEqual(session.json()['user']['id'], user.pk)
        self.assertIn('no-store', session['Cache-Control'])
        self.assertEqual(self.post('/api/workspaces/', {'name': 'تیم طراحی'}).status_code, 201)
        workspace = Workspace.objects.get()
        self.assertEqual(workspace.channels.count(), 2)
        self.assertEqual(workspace.memberships.get().role, 'admin')
        self.assertEqual(len(self.client.get('/api/workspaces/').json()['workspaces']), 1)
        self.assertEqual(self.post('/api/workspaces/', {'name': ' '}).status_code, 400)
        self.assertEqual(self.post('/api/workspaces/', {'name': 12}).status_code, 400)
        self.assertEqual(self.post('/api/auth/logout/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/workspaces/{workspace.pk}/').status_code, 401)
        self.token = self.client.get('/api/session/').json()['csrfToken']
        login = self.post('/api/auth/login/', {'username': 'NEW@EXAMPLE.COM', 'password': 'A-long-test-password-123'})
        self.assertEqual(login.status_code, 200)
        self.token = login.json()['csrfToken']
        self.assertEqual(self.client.get(f'/api/workspaces/{workspace.pk}/').status_code, 200)
        self.assertEqual(self.post('/api/auth/login/', {'username': user.email, 'password': 'wrong'}).status_code, 400)

    def test_validation_methods_and_json_errors(self):
        self.assertEqual(self.client.get('/api/auth/signup/').status_code, 405)
        for body in ('[]', '{bad', '{"email": []}'):
            response = self.client.post('/api/auth/signup/', body, content_type='application/json', HTTP_X_CSRFTOKEN=self.token)
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.json())
        self.signup()
        self.assertEqual(self.post('/api/auth/signup/', {'email': 'new@example.com'}).status_code, 400)
        response = self.client.get('/api/channels/999/messages/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('error', response.json())
        workspace = self.post('/api/workspaces/', {'name': 'Test'}).json()['id']
        response = self.post(f'/api/workspaces/{workspace}/channels/', {}, method='put')
        self.assertEqual(response.status_code, 405)
        self.assertIn('error', response.json())
        self.assertEqual(self.post('/api/auth/logout/', HTTP_ORIGIN='https://evil.example').status_code, 403)
        self.assertIsNotNone(self.client.get('/api/session/').json()['user'])

    def test_workspace_list_does_not_expose_other_teams(self):
        self.signup()
        other = User.objects.create_user('other@example.com')
        workspace = Workspace.objects.create(name='Hidden', slug='hidden')
        Membership.objects.create(workspace=workspace, user=other)
        self.assertEqual(self.client.get('/api/workspaces/').json()['workspaces'], [])
        self.assertEqual(self.client.get(f'/api/workspaces/{workspace.pk}/').status_code, 403)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', FRONTEND_URL='https://chat.example.com')
    def test_invitation_identity_expiry_acceptance_and_frontend_link(self):
        user = self.signup()
        workspace = self.post('/api/workspaces/', {'name': 'Studio'}).json()['id']
        response = self.post(f'/api/workspaces/{workspace}/invites/', {'email': user.email})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['url'].startswith('https://chat.example.com/invite/'))
        invite = Invitation.objects.get()
        url = f'/api/invites/{invite.token}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.post(url).status_code, 200)
        self.assertEqual(self.post(url).status_code, 400)
        invite.accepted_at = None
        invite.email = 'wrong@example.com'
        invite.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        invite.email = user.email
        invite.created_at = timezone.now() - timedelta(days=8)
        invite.save()
        self.assertEqual(self.client.get(url).status_code, 400)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', FRONTEND_URL='https://chat.example.com')
    def test_password_reset_token_validation_and_single_use(self):
        user = self.signup()
        self.assertEqual(self.post('/api/auth/password-reset/', {'email': user.email}).status_code, 200)
        self.assertIn('https://chat.example.com/accounts/reset/', mail.outbox[0].body)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        url = f'/api/auth/reset/{uid}/{token}/'
        self.assertEqual(self.post(url, {'new_password1': 'short', 'new_password2': 'short'}).status_code, 400)
        payload = {'new_password1': 'Replacement-test-password-123', 'new_password2': 'Replacement-test-password-123'}
        self.assertEqual(self.post(url, payload).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(payload['new_password1']))
        self.assertEqual(self.post(url, payload).status_code, 400)
        self.assertEqual(self.post('/api/auth/reset/invalid/invalid/', payload).status_code, 400)
        # Django invalidates existing authenticated sessions after a password change.
        self.assertIsNone(self.client.get('/api/session/').json()['user'])
        self.token = self.client.get('/api/session/').json()['csrfToken']
        self.assertEqual(self.post('/api/auth/password-reset/', {'email': 'unknown@example.com'}).status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_login_accepts_non_email_username(self):
        user = User.objects.create_user(username='admin', password='admin')
        response = self.post('/api/auth/login/', {'username': 'admin', 'password': 'admin'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/session/').json()['user']['id'], user.pk)
