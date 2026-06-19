import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from src.config import Config
from src.logger import setup_logger

logger = setup_logger("generate_kb")

# Define highly detailed content for the standard three files matching PDF test scenarios
DOCUMENTS = {
    # 1. API Troubleshooting (Markdown) - Detailed Integration, Auth, SSL, Database, Webhooks, and Cookie Clearing
    "api_troubleshooting.md": """# Adsparkx AI: Developer API & Integration Troubleshooting Guide

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
""",

    # 2. Billing Policy (Text) - Billing cycle, Upgrades, Invoice retrieval, Refunds, GDPR & SLAs
    "billing_policy.txt": """Adsparkx AI Platform Billing Policies, Data Residency, and Service SLAs

This document governs billing structures, payment terms, subscription conditions, data privacy compliance, and service level agreements.

=========================================
SECTION 1: BILLING CYCLE & SYSTEM CHARGES
=========================================
1.1 Recurring Billing Cycles
All subscription tiers (Growth, Developer, Enterprise) are billed in advance. Payment occurs on a recurring monthly cycle starting from the day of subscription. Annual packages are billed upfront with a 15% discount and renew automatically on the anniversary date.

1.2 Plan Upgrades & Downgrades
* Upgrade: Mid-cycle upgrades are prorated. Unused credit from your current tier is deducted from the new tier price, and a new monthly cycle starts immediately.
* Downgrade: Downgrades take effect at the end of the current billing cycle. No partial refunds are issued for mid-month downgrades.

1.3 Accepted Payments
Major credit cards (Visa, MasterCard, American Express) are processed securely via Stripe. Enterprise customers can be invoiced on Net-30 terms subject to credit approval.

=========================================
SECTION 2: INVOICES & TAX DOCUMENTATION
=========================================
2.1 Downloading Invoices
Automated invoices are emailed monthly. You can manually retrieve historic invoices by logging into console.adsparkx.ai, navigating to User Profile -> Billing Settings, and downloading PDFs under "Invoicing History".

2.2 Invoice Forwarding Automation
You can configure a primary billing contact under Billing Settings -> Contact Emails. If configured, invoice duplicates are forwarded to that address (e.g. billing@company.com) automatically.

=========================================
SECTION 3: REFUND & CANCELLATION POLICY
=========================================
3.1 The 14-Day Refund Guarantee
Growth subscriptions are eligible for a full refund if requested within 14 calendar days of the initial registration. 

3.2 Disqualification Criteria
Refunds are rejected if:
* API usage exceeds 2,000 credit tokens during the initial 14-day window.
* The account has been suspended due to terms of service violations (e.g. key sharing, scraping).
Once a refund is approved, Stripe processes the credit to your card within 5 to 10 business days.

=========================================
SECTION 4: GDPR COMPLIANCE & DATA RESIDENCY
=========================================
4.1 Data Residency Options
European customer data is processed and stored on cloud servers located in Frankfurt, Germany (EU-West). US customer datasets are hosted in Northern Virginia (US-East). Enterprise accounts can request database migrations by emailing migration-support@adsparkx.ai.

4.2 Encryption Standards
All customer files and transaction logs are encrypted in transit using TLS 1.3 and at rest on persistent volumes using AES-256 standards.

4.3 GDPR Right to Erasure (Account Deletion)
Upon permanent account deletion requests, active developer API keys are instantly revoked. All customer records are permanently purged from database backups after a 30-day grace period, except billing archives which are kept for 7 years to comply with financial audits.

=========================================
SECTION 5: SERVICE LEVEL AGREEMENT (SLA)
=========================================
5.1 Uptime Commitments
We guarantee 99.9% uptime for Growth accounts and 99.99% uptime for Enterprise accounts. Uptime calculations exclude Sunday maintenance windows (02:00 to 04:00 UTC).

5.2 Support Response Times
* Growth: Response within 24 hours.
* Enterprise: Response within 1 hour for Critical outages, and 4 hours for standard tickets.
If uptime drops below the SLA, users can claim invoice credits (10% to 50% depending on downtime) by emailing claims@adsparkx.ai.
"""
}

def generate_pdf(filepath: Path):
    """Generates the password_reset_guide.pdf document using ReportLab."""
    logger.info(f"Generating PDF guide at {filepath}")
    
    doc = SimpleDocTemplate(str(filepath), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=8
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )
    
    # PDF Contents - Detailed Password Reset, MFA, and SSO Single Sign-On
    story.append(Paragraph("Adsparkx AI Platform: Password Reset, MFA & SSO Configurations", title_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("This document outlines the official guidelines for managing account credentials, configuring Multi-Factor Authentication (MFA), and setting up Enterprise Single Sign-On (SSO).", body_style))
    
    story.append(Paragraph("1. Password Recovery Flow", h2_style))
    story.append(Paragraph("If you have lost your credentials or are locked out of your account, follow these steps to reset your password:", body_style))
    story.append(Paragraph("• Step 1: Navigate to the login portal at <b>https://console.adsparkx.ai/login</b> and click the 'Forgot Password' link.", body_style))
    story.append(Paragraph("• Step 2: Enter your primary registered email address. Ensure it matches the email used during subscription registration.", body_style))
    story.append(Paragraph("• Step 3: An automated secure verification token will be sent to your email. This token remains valid for precisely 15 minutes.", body_style))
    story.append(Paragraph("• Step 4: Click the link inside the email or enter the 6-digit verification code on the recovery page.", body_style))
    story.append(Paragraph("• Step 5: Specify your new password. Passwords must be at least 12 characters and contain uppercase, lowercase, numbers, and symbols.", body_style))
    
    story.append(Paragraph("2. Multi-Factor Authentication (MFA) Setup", h2_style))
    story.append(Paragraph("To protect your developer endpoints and billing data, we require MFA configuration:", body_style))
    story.append(Paragraph("• Step A: Go to Account Settings -> Security Console -> Multi-Factor Authentication.", body_style))
    story.append(Paragraph("• Step B: Click 'Enable MFA'. A unique QR code and backup recovery key will be generated.", body_style))
    story.append(Paragraph("• Step C: Scan the QR code using an authenticator application (e.g., Google Authenticator, Authy, or Microsoft Authenticator).", body_style))
    story.append(Paragraph("• Step D: Input the 6-digit TOTP code displayed in your authenticator app to complete activation.", body_style))
    story.append(Paragraph("• Step E: Securely print or store the 16-character backup recovery key in a physical safe. These recovery keys bypass MFA if your device is lost.", body_style))
    
    story.append(Paragraph("3. Enterprise Single Sign-On (SSO) Integration", h2_style))
    story.append(Paragraph("Enterprise clients can configure Identity Providers (IdPs) like Okta or Azure AD using SAML 2.0 or OIDC:", body_style))
    story.append(Paragraph("• Point your Identity Provider's Assertion Consumer Service (ACS) URL to <b>https://auth.adsparkx.ai/saml/acs</b>.", body_style))
    story.append(Paragraph("• Set the Audience URI / Entity ID to <b>https://auth.adsparkx.ai/saml/metadata</b>.", body_style))
    story.append(Paragraph("• Upload your IdP XML metadata document in the Adsparkx security console under SSO Settings.", body_style))
    story.append(Paragraph("• If authentication fails, ensure the SAML assertion signs both the response and the assertion element, and attributes are set in lowercase.", body_style))
    
    story.append(Paragraph("4. Troubleshooting Account Lockouts", h2_style))
    story.append(Paragraph("If you lose your authenticator device and have misplaced your backup recovery key, you must contact our Enterprise Support team at <b>security@adsparkx.ai</b>. For compliance and data security reasons, manual account recovery requires identity verification, which can take up to 24-48 business hours to complete.", body_style))
    
    doc.build(story)
    logger.info("PDF generation complete.")

def main():
    data_dir = Config.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Target data directory: {data_dir}")
    
    # Clean the directory first: delete any existing files
    for item in data_dir.iterdir():
        if item.is_file():
            logger.info(f"Removing old KB file: {item.name}")
            item.unlink()
            
    # Ingest only the standard three files
    for filename, content in DOCUMENTS.items():
        filepath = data_dir / filename
        logger.info(f"Writing {filename} to {filepath}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
            
    pdf_path = data_dir / "password_reset_guide.pdf"
    generate_pdf(pdf_path)
    
    logger.info("All support knowledge base documents generated successfully.")
    print("Success: Generated only the 3 primary support knowledge base documents with highly detailed content.")

if __name__ == "__main__":
    main()
