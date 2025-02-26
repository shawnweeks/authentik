"""Test Users API"""
from json import loads

from django.urls.base import reverse
from rest_framework.test import APITestCase

from authentik.core.models import User
from authentik.core.tests.utils import create_test_admin_user, create_test_flow, create_test_tenant
from authentik.flows.models import FlowDesignation
from authentik.lib.config import CONFIG
from authentik.lib.generators import generate_id, generate_key
from authentik.stages.email.models import EmailStage
from authentik.tenants.models import Tenant


class TestUsersAPI(APITestCase):
    """Test Users API"""

    def setUp(self) -> None:
        self.admin = create_test_admin_user()
        self.user = User.objects.create(username="test-user")

    def test_metrics(self):
        """Test user's metrics"""
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("authentik_api:user-metrics", kwargs={"pk": self.user.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_metrics_denied(self):
        """Test user's metrics (non-superuser)"""
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("authentik_api:user-metrics", kwargs={"pk": self.user.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_recovery_no_flow(self):
        """Test user recovery link (no recovery flow set)"""
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("authentik_api:user-recovery", kwargs={"pk": self.user.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_set_password(self):
        """Test Direct password set"""
        self.client.force_login(self.admin)
        new_pw = generate_key()
        response = self.client.post(
            reverse("authentik_api:user-set-password", kwargs={"pk": self.admin.pk}),
            data={"password": new_pw},
        )
        self.assertEqual(response.status_code, 204)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(new_pw))

    def test_recovery(self):
        """Test user recovery link (no recovery flow set)"""
        flow = create_test_flow(FlowDesignation.RECOVERY)
        tenant: Tenant = create_test_tenant()
        tenant.flow_recovery = flow
        tenant.save()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("authentik_api:user-recovery", kwargs={"pk": self.user.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_recovery_email_no_flow(self):
        """Test user recovery link (no recovery flow set)"""
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("authentik_api:user-recovery-email", kwargs={"pk": self.user.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.user.email = "foo@bar.baz"
        self.user.save()
        response = self.client.get(
            reverse("authentik_api:user-recovery-email", kwargs={"pk": self.user.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_recovery_email_no_stage(self):
        """Test user recovery link (no email stage)"""
        self.user.email = "foo@bar.baz"
        self.user.save()
        flow = create_test_flow(designation=FlowDesignation.RECOVERY)
        tenant: Tenant = create_test_tenant()
        tenant.flow_recovery = flow
        tenant.save()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("authentik_api:user-recovery-email", kwargs={"pk": self.user.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_recovery_email(self):
        """Test user recovery link"""
        self.user.email = "foo@bar.baz"
        self.user.save()
        flow = create_test_flow(FlowDesignation.RECOVERY)
        tenant: Tenant = create_test_tenant()
        tenant.flow_recovery = flow
        tenant.save()

        stage = EmailStage.objects.create(name="email")

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse(
                "authentik_api:user-recovery-email",
                kwargs={"pk": self.user.pk},
            )
            + f"?email_stage={stage.pk}"
        )
        self.assertEqual(response.status_code, 204)

    def test_service_account(self):
        """Service account creation"""
        self.client.force_login(self.admin)
        response = self.client.post(reverse("authentik_api:user-service-account"))
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("authentik_api:user-service-account"),
            data={
                "name": "test-sa",
                "create_group": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="test-sa").exists())

    def test_service_account_invalid(self):
        """Service account creation (twice with same name, expect error)"""
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("authentik_api:user-service-account"),
            data={
                "name": "test-sa",
                "create_group": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="test-sa").exists())
        response = self.client.post(
            reverse("authentik_api:user-service-account"),
            data={
                "name": "test-sa",
                "create_group": True,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_paths(self):
        """Test path"""
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("authentik_api:user-paths"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content.decode(), {"paths": ["users"]})

    def test_path_valid(self):
        """Test path"""
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("authentik_api:user-list"),
            data={"name": generate_id(), "username": generate_id(), "groups": [], "path": "foo"},
        )
        self.assertEqual(response.status_code, 201)

    def test_path_invalid(self):
        """Test path (invalid)"""
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("authentik_api:user-list"),
            data={"name": generate_id(), "username": generate_id(), "groups": [], "path": "/foo"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content.decode(), {"path": ["No leading or trailing slashes allowed."]}
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("authentik_api:user-list"),
            data={"name": generate_id(), "username": generate_id(), "groups": [], "path": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content.decode(), {"path": ["This field may not be blank."]})

        response = self.client.post(
            reverse("authentik_api:user-list"),
            data={"name": generate_id(), "username": generate_id(), "groups": [], "path": "foo/"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content.decode(), {"path": ["No leading or trailing slashes allowed."]}
        )

        response = self.client.post(
            reverse("authentik_api:user-list"),
            data={
                "name": generate_id(),
                "username": generate_id(),
                "groups": [],
                "path": "fos//o",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content.decode(), {"path": ["No empty segments in user path allowed."]}
        )

    def test_me(self):
        """Test user's me endpoint"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("authentik_api:user-me"))
        self.assertEqual(response.status_code, 200)

    @CONFIG.patch("avatars", "none")
    def test_avatars_none(self):
        """Test avatars none"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("authentik_api:user-me"))
        self.assertEqual(response.status_code, 200)
        body = loads(response.content.decode())
        self.assertEqual(body["user"]["avatar"], "/static/dist/assets/images/user_default.png")

    @CONFIG.patch("avatars", "gravatar")
    def test_avatars_gravatar(self):
        """Test avatars gravatar"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("authentik_api:user-me"))
        self.assertEqual(response.status_code, 200)
        body = loads(response.content.decode())
        self.assertIn("gravatar", body["user"]["avatar"])

    @CONFIG.patch("avatars", "foo-%(username)s")
    def test_avatars_custom(self):
        """Test avatars custom"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("authentik_api:user-me"))
        self.assertEqual(response.status_code, 200)
        body = loads(response.content.decode())
        self.assertEqual(body["user"]["avatar"], f"foo-{self.admin.username}")

    @CONFIG.patch("avatars", "attributes.foo.avatar")
    def test_avatars_attributes(self):
        """Test avatars attributes"""
        self.admin.attributes = {"foo": {"avatar": "bar"}}
        self.admin.save()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("authentik_api:user-me"))
        self.assertEqual(response.status_code, 200)
        body = loads(response.content.decode())
        self.assertEqual(body["user"]["avatar"], "bar")
