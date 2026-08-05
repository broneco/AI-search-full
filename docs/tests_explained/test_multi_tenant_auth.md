# Explaining `test_multi_tenant_auth.py`

This test suite validates lightweight database-backed authentication, multi-tenant organization data isolation (`TENANT_ID`), chat thread CRUD operations, and multi-turn conversational context.

---

## Technical Overview (High Level)

1. **Auto-seeded Demo Login Test (`test_auth_login_demo_user`)**:
   - Sends a `POST /api/auth/login` with credentials `user@dolphin.cz` / `password123`.
   - Validates that a valid JWT token (`access_token`) and user profile are returned.

2. **User Registration Test (`test_auth_register_new_user`)**:
   - Registers a new user account via `POST /api/auth/register` with role `Management`.
   - Asserts that security groups (`["User", "Management"]`) are assigned properly.

3. **Chat Thread CRUD Operations (`test_threads_crud_workflow`)**:
   - Creates a new chat thread (`POST /api/threads`), lists user threads (`GET /api/threads`), renames thread title (`PATCH /api/threads/{thread_id}`), and deletes the thread (`DELETE /api/threads/{thread_id}`).

4. **Multi-Tenant User Isolation (`test_multi_tenant_user_isolation`)**:
   - Creates a user under a different `tenant_id` (`"other_tenant"`).
   - Verifies that attempting to authenticate against tenant `"dolphin"` fails with `401 Unauthorized`.
