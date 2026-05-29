# Test Explanation: `test_health.py`

This test suite verifies the basic connectivity, routing, and operational status of the FastAPI backend application. It ensures that the application boots up correctly and responds to basic diagnostic checks.

---

## Individual Tests

### Test 1: `test_health_check_endpoints`

* **High-Level Purpose:**
  We verify that the API's diagnostic health check endpoints respond correctly and report a status of `"healthy"`. This acts as the primary heartbeat check for container orchestrators (e.g. Azure Container Apps) to determine if the container is operational and ready to receive traffic.
* **Low-Level Technical Details:**
  * Uses the **`TestClient`** from the `fastapi.testclient` package, which runs an in-memory ASGI loop over our FastAPI `app` instance without opening actual network ports.
  * Triggers a synchronous `GET` request to both `/health` and its prefixed duplicate `/api/health`.
  * Asserts that the HTTP response code is exactly `200 OK`.
  * Decodes the JSON response body and asserts that:
    * `status` is exactly `"healthy"`.
    * `environment` matches the active `APP_ENV` configuration.
    * `app_name` matches the active `APP_NAME` configuration.
    * A `"version"` key is present in the payload.
  * Asserts that the `/api/health` response JSON matches the `/health` response JSON exactly.

---

### Test 2: `test_root_endpoint`

* **High-Level Purpose:**
  We verify that the root URL (`/`) responds to HTTP queries and provides a welcoming landing message guiding developers or clients to the health check documentation route.
* **Low-Level Technical Details:**
  * Performs a synchronous `GET` request to `/` using the `TestClient`.
  * Asserts that the response status code is exactly `200 OK`.
  * Decodes the JSON response body and validates:
    * The `"message"` key contains the word `"Welcome"`.
    * The `"health_check"` key points exactly to the `/health` path.
