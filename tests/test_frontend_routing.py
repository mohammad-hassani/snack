from django.test import TestCase, override_settings


@override_settings(FRONTEND_URL='https://snack.example.com')
class FrontendRoutingTests(TestCase):
    def test_old_pages_preserve_path_and_query_at_frontend(self):
        for path in ('/?workspace=2', '/accounts/login/?next=%2Finvite%2Ftoken%2F', '/accounts/signup/', '/accounts/reset/id/token/', '/invite/token/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertRedirects(response, 'https://snack.example.com' + path, fetch_redirect_response=False)
        self.assertEqual(self.client.head('/')['Location'], 'https://snack.example.com/')

    def test_api_health_and_admin_stay_on_django(self):
        self.assertEqual(self.client.get('/api/session/').status_code, 200)
        self.assertEqual(self.client.get('/api/workspaces/').status_code, 401)
        self.assertEqual(self.client.get('/health/').status_code, 200)
        self.assertTrue(self.client.get('/admin/')['Location'].startswith('/admin/login/'))

    @override_settings(FRONTEND_URL='')
    def test_templates_still_work_without_a_frontend(self):
        self.assertContains(self.client.get('/accounts/login/'), 'اسنک')
