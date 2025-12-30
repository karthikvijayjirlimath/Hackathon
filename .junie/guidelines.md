# Python Web Application Security & Production Guidelines

These guidelines are designed to ensure that Junie develops and maintains Python web applications (Flask, Django, FastAPI, etc.) that are production-ready, secure, and resilient.

### 1. Security Best Practices

*   **Secret Management:**
    - Never hardcode secrets (API keys, database URLs, secret keys).
    - Use environment variables (`os.environ`) or `.env` files (via `python-dotenv`).
    - Use a strong, randomly generated `SECRET_KEY` in production.
*   **Input Validation & Sanitization:**
    - Always use `werkzeug.utils.secure_filename` for file uploads.
    - Validate all user inputs against expected formats (e.g., using `pydantic`, `marshmallow`, or form libraries).
    - Prevent SQL Injection by using ORMs (SQLAlchemy, Django ORM) or parameterized queries.
*   **Cross-Site Request Forgery (CSRF):**
    - Enable CSRF protection for all forms (e.g., `Flask-WTF` for Flask).
*   **Security Headers:**
    - Use libraries like `Flask-Talisman` or `Secure` to set security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options).
*   **Dependency Management:**
    - Pin dependency versions in `requirements.txt` or `pyproject.toml`.
    - Regularly check for vulnerabilities using `safety` or `pip-audit`.
*   **Data Protection:**
    - Encrypt sensitive data at rest and in transit (HTTPS).
    - Minimize PII (Personally Identifiable Information) storage.

### 2. Production Readiness

*   **Disable Debug Mode:**
    - Never run with `debug=True` in production. It exposes sensitive stack traces.
*   **WSGI/ASGI Server:**
    - Use a production-grade server like `gunicorn`, `uWSGI` (WSGI), or `uvicorn`, `hypercorn` (ASGI).
*   **Logging:**
    - Implement structured logging. Avoid logging sensitive data.
    - Log errors to a file or a centralized logging service.
*   **Error Handling:**
    - Use custom error pages (404, 500) to avoid leaking system information.
    - Implement graceful degradation.

### 3. Code Quality & Maintenance

*   **Type Hinting:** Use Python type hints for better maintainability and error detection.
*   **Testing:**
    - Write unit tests for business logic.
    - Write integration tests for API endpoints.
    - Ensure tests cover security-critical paths (authentication, authorization, file processing).
*   **Structure:**
    - Follow a modular project structure (e.g., Blueprints in Flask).
    - Separate configuration from application logic.

### 4. Deployment & Cloud (Azure)

*   **Azure App Service:**
    - Use **Managed Identities** to authenticate to Azure services (Key Vault, Storage, Databases) without storing credentials in code or environment variables.
    - Configure **Application Settings** in the Azure Portal for environment-specific variables.
    - Enable **HTTPS Only** and set the minimum TLS version to 1.2.
*   **Secret Management (Azure Key Vault):**
    - Store sensitive application secrets (API keys, connection strings) in **Azure Key Vault**.
    - Use the `azure-identity` and `azure-keyvault-secrets` libraries to fetch secrets at runtime.
*   **Data Storage (Azure Blob Storage & Databases):**
    - Use **Azure Blob Storage** for persistent file storage instead of the local file system.
    - Enable **Soft Delete** and **Versioning** for Blobs to prevent accidental data loss.
    - Use **Private Endpoints** for Azure SQL or Cosmos DB to restrict access to the virtual network.
*   **Monitoring & Logging (Azure Monitor):**
    - Integrate **Azure Application Insights** for distributed tracing, performance monitoring, and error logging.
    - Configure **Diagnostic Settings** to send logs to a Log Analytics workspace.
*   **Containerization (Azure Container Registry & Web App for Containers):**
    - Store Docker images in a private **Azure Container Registry (ACR)**.
    - Use **Web App for Containers** for deploying containerized applications.

### 5. Deployment Process

*   **Containerization:** Use Docker to ensure environment consistency.
    - Use non-root users inside containers.
    - Use multi-stage builds to keep image sizes small and secure.
*   **CI/CD:** Automate security scans and tests in the deployment pipeline.
