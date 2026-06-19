# Adsparkx AI: Developer API & Integration Troubleshooting Guide

This guide is designed to help developers configure, troubleshoot, and optimize integrations with the Adsparkx AI developer endpoints, as well as resolve client-side browser loading issues.

---

## Part 1: Authentication & Bearer Tokens
All API requests must authenticate using a Bearer Token transmitted in the standard HTTP `Authorization` header.

### Header Construction
Your requests must include the header structured exactly as follows:
```http
Authorization: Bearer YOUR_DEVELOPER_API_KEY
```

### Token Lifecycle & Security Checklist
*   **Rotation**: We recommend rotating keys every 90 days. Generate a secondary key in the security panel, switch traffic, and safely delete the old key to prevent downtime.
*   **Leakage Prevention**: Never commit tokens to public repositories. Use environment variables.
*   **Authentication Errors (401 Unauthorized)**: Verify that the `Authorization` header is spelled correctly, there is a space after `Bearer`, and the token status is marked as 'Active' in the Developer Console.

---

## Part 2: Browser Cookie & Cache Clearing Guide
If the Adsparkx console UI is rendering incorrectly, buttons are unresponsive, or you are experiencing login loops, clearing your browser's local cache and cookies will resolve the issue.

### Google Chrome (Desktop)
1.  Click the three vertical dots icon in the top-right corner of the window.
2.  Navigate to **Delete Browsing Data** (or press `Ctrl+Shift+Del` on Windows / `Cmd+Shift+Del` on macOS).
3.  Set the time range to **All Time**.
4.  Check the boxes next to **Cookies and other site data** and **Cached images and files**.
5.  Click the **Delete data** button.
6.  Restart your browser and log back into `console.adsparkx.ai`.

### Apple Safari (macOS)
1.  Click **Safari** in the top menu bar and select **Settings** (or **Preferences**).
2.  Navigate to the **Privacy** tab.
3.  Click the **Manage Website Data** button.
4.  Type `adsparkx.ai` in the search box, select our domain, and click **Remove**.
5.  Navigate to the **Advanced** tab and check **Show features for web developers**.
6.  Close settings, click **Develop** in the top menu bar, and click **Empty Caches**.

### Microsoft Edge
1.  Click the three horizontal dots icon in the top-right corner.
2.  Go to **Settings** > **Privacy, search, and services**.
3.  Scroll down to the **Clear browsing data** section and click **Choose what to clear**.
4.  Set the time range to **All time**, check **Cookies and other site data** and **Cached images and files**, and click **Clear now**.

### Mozilla Firefox
1.  Click the menu button (three horizontal lines) in the top-right corner.
2.  Select **Settings** > **Privacy & Security**.
3.  Scroll down to **Cookies and Site Data** and click **Clear Data...**
4.  Check the boxes for **Cookies and Site Data** and **Cached Web Content**, then click **Clear**.

---

## Part 3: HTTP Error Status Codes Reference
If your queries fail, check the HTTP response code:

| Code | Error Name | Common Cause | Resolution |
| :--- | :--- | :--- | :--- |
| **400** | Bad Request | Invalid JSON structure or missing parameters. | Check payload schema and parameters. |
| **401** | Unauthorized | Missing, expired, or malformed API token. | Verify bearer header spelling and key state. |
| **403** | Forbidden | Insufficient permissions for resource. | Upgrade plan to access premium endpoints. |
| **404** | Not Found | Target endpoint or resource does not exist. | Verify path spelling and API version prefix. |
| **429** | Too Many Requests | Rate limit exceeded. | Implement exponential backoff in client. |
| **500** | Internal Error | Unexpected server exception. | Contact support with the `X-Request-ID`. |

---

## Part 4: Connection Timeouts & SSL Resolution
If your systems fail to connect to `api.adsparkx.ai`:
1.  **Port Verification**: Ensure outbound HTTPS traffic is allowed on port 443.
2.  **DNS Checks**: Run `nslookup api.adsparkx.ai` to verify DNS resolution. If it fails, switch to public DNS (e.g. `8.8.8.8`).
3.  **SSL Certificate Handshake Errors**: If you get a certificate verification failure, your root CA bundle may be outdated.
    *   *Ubuntu/Debian*: Run `sudo apt-get install --reinstall ca-certificates && sudo update-ca-certificates`.
    *   *Windows/Python*: Ensure the package `certifi` is installed and updated. Use `verify=certifi.where()` in requests.

---

## Part 5: Database Integrations & Connection Pooling
When syncing data with Adsparkx systems, maintain connection limits to avoid database exhaustion:
*   **Max Pool Size**: Limit database pool size to 15 concurrent connections per application node.
*   **Timeouts**: Set idle timeout to 300 seconds, and connection timeout to 10 seconds.
*   **SSL Mode**: PostgreSQL connection strings should specify `?sslmode=require`. For MySQL, use `?ssl-mode=REQUIRED`.

---

## Part 6: Webhooks & Signature Verification
Webhooks deliver real-time event notifications via HTTP POST payloads.

### Webhook Signatures
To verify webhook signatures and prevent spoofing, check the `X-Adsparkx-Signature` header:
```python
import hmac
import hashlib

def verify_webhook(payload_body: bytes, signature_header: str, secret: str) -> bool:
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)
```

### Retry Schedule
If your webhook endpoint returns a non-2xx status, our system will retry sending the payload using exponential backoff up to 5 times (retries occur at 5 mins, 15 mins, 1 hr, 4 hrs, and 12 hrs). Endpoints failing 3 consecutive deliveries are disabled.
