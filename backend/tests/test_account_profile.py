"""
Tests for the Account Profile & Appearance endpoints.
Deterministic — no DB or network calls required.
"""
import inspect
import os
import pathlib
import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
FRONTEND_DIR = ROOT.parent / "frontend"


# ---------------------------------------------------------------------------
# Migration SQL
# ---------------------------------------------------------------------------

class TestMigrationSQL:
    sql_path = SCRIPTS_DIR / "019_user_profile_appearance.sql"

    def test_migration_file_exists(self):
        assert self.sql_path.exists(), "019_user_profile_appearance.sql is missing"

    def test_creates_user_profiles_table(self):
        sql = self.sql_path.read_text()
        assert "CREATE TABLE" in sql.upper()
        assert "user_profiles" in sql

    def test_display_name_column(self):
        sql = self.sql_path.read_text()
        assert "display_name" in sql

    def test_avatar_url_column(self):
        sql = self.sql_path.read_text()
        assert "avatar_url" in sql

    def test_public_email_column(self):
        sql = self.sql_path.read_text()
        assert "public_email" in sql

    def test_theme_preference_column(self):
        sql = self.sql_path.read_text()
        assert "theme_preference" in sql

    def test_theme_check_constraint(self):
        sql = self.sql_path.read_text()
        assert "'light'" in sql
        assert "'dark'" in sql
        assert "'system'" in sql
        assert "CHECK" in sql.upper() or "check" in sql

    def test_rls_enabled(self):
        sql = self.sql_path.read_text()
        assert "ENABLE ROW LEVEL SECURITY" in sql.upper()

    def test_rls_select_policy(self):
        sql = self.sql_path.read_text()
        assert "user_profiles_select_own" in sql

    def test_rls_update_policy(self):
        sql = self.sql_path.read_text()
        assert "user_profiles_update_own" in sql

    def test_rls_insert_policy(self):
        sql = self.sql_path.read_text()
        assert "user_profiles_insert_own" in sql

    def test_service_role_bypass_policy(self):
        sql = self.sql_path.read_text()
        assert "service_role" in sql

    def test_updated_at_trigger(self):
        sql = self.sql_path.read_text()
        assert "updated_at" in sql
        assert "TRIGGER" in sql.upper()

    def test_default_theme_is_system(self):
        sql = self.sql_path.read_text()
        assert "DEFAULT 'system'" in sql or "default 'system'" in sql


# ---------------------------------------------------------------------------
# Endpoint module
# ---------------------------------------------------------------------------

class TestAccountModule:
    def test_account_module_importable(self):
        from app.api.endpoints import account
        assert hasattr(account, "router")

    def test_router_has_get_profile(self):
        from app.api.endpoints.account import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/account/profile" in paths

    def test_router_has_patch_profile(self):
        from app.api.endpoints.account import router
        methods = {}
        for r in router.routes:
            if hasattr(r, "methods") and hasattr(r, "path"):
                methods[r.path] = r.methods
        assert "PATCH" in methods.get("/account/profile", set())

    def test_router_has_patch_avatar(self):
        from app.api.endpoints.account import router
        methods = {}
        for r in router.routes:
            if hasattr(r, "methods") and hasattr(r, "path"):
                methods[r.path] = r.methods
        assert "PATCH" in methods.get("/account/avatar", set())


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestProfileModels:
    def test_profile_response_fields(self):
        from app.api.endpoints.account import ProfileResponse
        fields = set(ProfileResponse.model_fields.keys())
        expected = {"user_id", "email", "display_name", "public_email", "avatar_url", "theme_preference"}
        assert expected.issubset(fields)

    def test_profile_patch_accepts_display_name(self):
        from app.api.endpoints.account import ProfilePatchRequest
        obj = ProfilePatchRequest(display_name="Test Name")
        assert obj.display_name == "Test Name"

    def test_profile_patch_accepts_theme(self):
        from app.api.endpoints.account import ProfilePatchRequest
        obj = ProfilePatchRequest(theme_preference="dark")
        assert obj.theme_preference == "dark"

    def test_profile_patch_rejects_invalid_theme(self):
        from app.api.endpoints.account import ProfilePatchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ProfilePatchRequest(theme_preference="neon")

    def test_profile_patch_allows_light(self):
        from app.api.endpoints.account import ProfilePatchRequest
        obj = ProfilePatchRequest(theme_preference="light")
        assert obj.theme_preference == "light"

    def test_profile_patch_allows_system(self):
        from app.api.endpoints.account import ProfilePatchRequest
        obj = ProfilePatchRequest(theme_preference="system")
        assert obj.theme_preference == "system"

    def test_profile_patch_allows_none_theme(self):
        from app.api.endpoints.account import ProfilePatchRequest
        obj = ProfilePatchRequest(theme_preference=None)
        assert obj.theme_preference is None

    def test_profile_patch_accepts_public_email(self):
        from app.api.endpoints.account import ProfilePatchRequest
        obj = ProfilePatchRequest(public_email="pub@example.com")
        assert obj.public_email == "pub@example.com"

    def test_profile_response_default_theme(self):
        from app.api.endpoints.account import ProfileResponse
        obj = ProfileResponse(user_id="abc")
        assert obj.theme_preference == "system"


# ---------------------------------------------------------------------------
# Constants and config
# ---------------------------------------------------------------------------

class TestAccountConstants:
    def test_allowed_themes_set(self):
        from app.api.endpoints.account import ALLOWED_THEMES
        assert ALLOWED_THEMES == {"light", "dark", "system"}

    def test_avatar_max_bytes(self):
        from app.api.endpoints.account import AVATAR_MAX_BYTES
        assert AVATAR_MAX_BYTES == 2 * 1024 * 1024

    def test_avatar_content_types(self):
        from app.api.endpoints.account import AVATAR_CONTENT_TYPES
        assert "image/jpeg" in AVATAR_CONTENT_TYPES
        assert "image/png" in AVATAR_CONTENT_TYPES
        assert "image/webp" in AVATAR_CONTENT_TYPES

    def test_avatar_bucket_name(self):
        from app.api.endpoints.account import AVATAR_BUCKET
        assert AVATAR_BUCKET == "avatars"


# ---------------------------------------------------------------------------
# Main app integration
# ---------------------------------------------------------------------------

class TestMainAppIntegration:
    def test_main_imports_account(self):
        src = (ROOT / "app" / "main.py").read_text()
        assert "account" in src

    def test_main_registers_account_router(self):
        src = (ROOT / "app" / "main.py").read_text()
        assert "account_ep.router" in src

    def test_app_has_account_profile_route(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        matches = [p for p in paths if "account/profile" in p]
        assert len(matches) >= 1, f"No account/profile route found. Routes: {paths[:20]}"

    def test_app_has_account_avatar_route(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        matches = [p for p in paths if "account/avatar" in p]
        assert len(matches) >= 1


# ---------------------------------------------------------------------------
# Frontend integration (file-level checks)
# ---------------------------------------------------------------------------

class TestFrontendIntegration:
    def test_account_page_exists(self):
        page = FRONTEND_DIR / "app" / "settings" / "account" / "page.tsx"
        assert page.exists(), "settings/account/page.tsx missing"

    def test_api_ts_has_getAccountProfile(self):
        src = (FRONTEND_DIR / "lib" / "api.ts").read_text()
        assert "getAccountProfile" in src

    def test_api_ts_has_patchAccountProfile(self):
        src = (FRONTEND_DIR / "lib" / "api.ts").read_text()
        assert "patchAccountProfile" in src

    def test_api_ts_has_uploadAvatar(self):
        src = (FRONTEND_DIR / "lib" / "api.ts").read_text()
        assert "uploadAvatar" in src

    def test_api_ts_exports_AccountProfile_type(self):
        src = (FRONTEND_DIR / "lib" / "api.ts").read_text()
        assert "AccountProfile" in src

    def test_theme_provider_exists(self):
        path = FRONTEND_DIR / "components" / "ThemeProvider.tsx"
        assert path.exists(), "ThemeProvider.tsx missing"

    def test_theme_provider_exports_useTheme(self):
        src = (FRONTEND_DIR / "components" / "ThemeProvider.tsx").read_text()
        assert "useTheme" in src

    def test_layout_imports_theme_provider(self):
        src = (FRONTEND_DIR / "app" / "layout.tsx").read_text()
        assert "ThemeProvider" in src

    def test_dark_theme_tokens_exist(self):
        src = (FRONTEND_DIR / "styles" / "tokens.css").read_text()
        assert 'data-theme="dark"' in src

    def test_globals_has_dark_overrides(self):
        src = (FRONTEND_DIR / "app" / "globals.css").read_text()
        assert 'data-theme="dark"' in src

    def test_account_page_has_no_phase_references(self):
        src = (FRONTEND_DIR / "app" / "settings" / "account" / "page.tsx").read_text()
        lower = src.lower()
        assert "phase" not in lower, "Account page must not contain 'phase'"

    def test_theme_provider_has_no_phase_references(self):
        src = (FRONTEND_DIR / "components" / "ThemeProvider.tsx").read_text()
        lower = src.lower()
        assert "phase" not in lower


# ---------------------------------------------------------------------------
# Cleanup verification — no "phase" in new files
# ---------------------------------------------------------------------------

class TestNoPhaseLanguage:
    new_files = [
        ROOT / "scripts" / "019_user_profile_appearance.sql",
        ROOT / "app" / "api" / "endpoints" / "account.py",
        FRONTEND_DIR / "app" / "settings" / "account" / "page.tsx",
        FRONTEND_DIR / "components" / "ThemeProvider.tsx",
    ]

    @pytest.mark.parametrize("path", new_files, ids=lambda p: p.name)
    def test_file_has_no_phase_word(self, path):
        if path.exists():
            content = path.read_text().lower()
            assert "phase" not in content, f"{path.name} contains the word 'phase'"
