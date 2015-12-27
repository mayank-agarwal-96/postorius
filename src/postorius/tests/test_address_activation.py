from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.urlresolvers import reverse
from django.core import mail
from django.test.client import Client, RequestFactory
from django.test.utils import override_settings
from django.test import TestCase
from mock import patch, call

from postorius.forms import AddressActivationForm
from postorius.models import AddressConfirmationProfile
from postorius import views
from postorius.views.user import address_activation_link


class TestAddressActivationForm(TestCase):
    """
    Test the activation form.
    """

    def test_valid_email_is_valid(self):
        data = {
            'email': 'les@example.org',
            'user_email': 'me@example.org',
        }
        form = AddressActivationForm(data)
        self.assertTrue(form.is_valid())

    def test_identical_emails_are_invalid(self):
        data = {
            'email': 'les@example.org',
            'user_email': 'les@example.org',
        }
        form = AddressActivationForm(data)
        self.assertFalse(form.is_valid())

    def test_invalid_email_is_not_valid(self):
        data = {
            'email': 'les@example',
            'user_email': 'me@example.org',
        }
        form = AddressActivationForm(data)
        self.assertFalse(form.is_valid())


class TestAddressConfirmationProfile(TestCase):
    """
    Test the confirmation of an email address activation (validating token,
    expiration, Mailman API calls etc.).
    """

    def setUp(self):
        # Create a user and profile.
        self.user = User.objects.create_user(
            username=u'ler_mm', email=u'ler@mailman.mostdesirable.org',
            password=u'pwd')
        self.profile = AddressConfirmationProfile.objects.create_profile(
            u'les@example.org', self.user)
        # Create a test request object
        self.request = RequestFactory().get('/')

    def tearDown(self):
        self.profile.delete()
        self.user.delete()
        mail.outbox = []

    def test_profile_creation(self):
        # Profile is created and has all necessary properties.
        self.assertEqual(self.profile.email, u'les@example.org')
        self.assertEqual(len(self.profile.activation_key), 40)
        self.assertTrue(type(self.profile.created), datetime)

    def test_no_duplicate_profiles(self):
        # Creating a new profile returns an existing record
        # (if one exists), instead of creating a new one.
        new_profile = AddressConfirmationProfile.objects.create_profile(
            u'les@example.org',
            User.objects.create(email=u'ler@mailman.mostdesirable.org'))
        self.assertEqual(self.profile, new_profile)

    def test_unicode_representation(self):
        # Correct unicode representation?
        self.assertEqual(unicode(self.profile),
                         'Address Confirmation Profile for les@example.org')

    def test_profile_not_expired_default_setting(self):
        # A profile created less then a day ago is not expired by default.
        delta = timedelta(hours=23)
        now = datetime.now()
        self.profile.created = now - delta
        self.assertFalse(self.profile.is_expired)

    def test_profile_is_expired_default_setting(self):
        # A profile older than 1 day is expired by default.
        delta = timedelta(days=1, hours=1)
        now = datetime.now()
        self.profile.created = now - delta
        self.assertTrue(self.profile.is_expired)

    @override_settings(
        EMAIL_CONFIRMATION_EXPIRATION_DELTA=timedelta(hours=5))
    def test_profile_not_expired(self):
        # A profile older than the timedelta set in the settings is
        # expired.
        delta = timedelta(hours=6)
        now = datetime.now()
        self.profile.created = now - delta
        self.assertTrue(self.profile.is_expired)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EMAIL_CONFIRMATION_FROM='mailman@mostdesirable.org')
    def test_confirmation_link(self):
        # The profile obj can send out a confirmation email.
        # set the activation key to a fixed string for testing
        self.profile.activation_key = \
            '6323fba0097781fdb887cfc37a1122ee7c8bb0b0'
        # Simulate a VirtualHost with a different name
        self.request.META["HTTP_HOST"] = "another-virtualhost"
        # Now send the email
        self.profile.send_confirmation_link(self.request)
        self.assertEqual(mail.outbox[0].to[0], u'les@example.org')
        self.assertEqual(mail.outbox[0].subject, u'Confirmation needed')
        self.assertIn(self.profile.activation_key, mail.outbox[0].body)
        self.assertIn("another-virtualhost", mail.outbox[0].body)


class TestAddressActivationLinkSuccess(TestCase):
    """
    This tests the activation link view if the key is valid and the profile is
    not expired.
    """

    def setUp(self):
        # Set up a profile with a predictable key
        self.user = User.objects.create_user(
            username='ler', email=u'ler@example.org',
            password='pwd')
        self.profile = AddressConfirmationProfile.objects.create_profile(
            u'les@example.org', self.user)
        self.profile.activation_key = \
            u'6323fba0097781fdb887cfc37a1122ee7c8bb0b0'
        self.profile.save()

    def tearDown(self):
        self.profile.delete()
        self.user.delete()

    @patch.object(views.user, '_add_address')
    def test_mailman(self, _add_address_mock):
        # An activation key pointing to a valid profile adds the address
        # to the user.
        request = RequestFactory().get(reverse(
            'address_activation_link', kwargs={
            'activation_key': '6323fba0097781fdb887cfc37a1122ee7c8bb0b0'}))
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        address_activation_link(
            request, '6323fba0097781fdb887cfc37a1122ee7c8bb0b0')
        expected_calls = [call(request, u'ler@example.org',
                         u'les@example.org')]
        self.assertEqual(_add_address_mock.mock_calls, expected_calls)
