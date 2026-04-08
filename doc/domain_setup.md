# Custom Domain Setup Guide (API Gateway + Cognito)

This document details how our custom domains are configured for our multistack setup.

---

## Overview

We use custom subdomains instead of raw API Gateway URLS for cleaner and easier access.

Right now we have a certificate for *.erglytics.com, so anything one level above erglytics is covered (does not cover things like stack.one.erglytics.com).

Each stack should have its own subdomain. As of right now, we CANNOT have the same subdomain apply to multiple stacks.

---

## Domain Structure

*Add as you create subdomains for new stacks*

| Environment | Domain |
|---|---|
| Main Version (0-6-2) | `app.erglytics.com` |
| Dev Stack | `dev.erglytics.com` |
| User testing / UAT | `uat.erglytics.com` |
| Authentication (Cognito)| `auth.erglytics.com` |

---

## Certificate Setup (ACM)

All subdomains are covered with the wildcard (*.erglytics) certificate.

This certificate is created in **AWS Certificate Manager (ACM)** and validated through DNS records in GoDaddy (reach out to me if you need the login information).

This allows reuse across multiple stacks without creating a new certificate each time. 

---

## Custom Domain Setup

For each environment:

### 1. Create Custom Domain

Go to:

```text
API Gateway → Custom domain names
```

Create:

```text
dev.erglytics.com
```

or other environment-specific domain.

Use:

- **Regional**
- **API mappings only**
- wildcard certificate (`*.erglytics.com`)
- TLS 1.2 or newer

---

### 2. DNS Setup (GoDaddy)

Each custom domain needs a CNAME record.

Go to **GoDaddy** *Domain* Settings and navigate to *DNS Records*.

Add a new record, and do it in the following fashion:

for `dev.erglytics.com` you would do

```text
Type: CNAME
Name: dev
Value: (API Gateway domain name)
```

The `API Gateway domain name` is found on *Endpoint configuration* in the subdomain's details.

Now you must wait on the *Custom Domain Names* page until the *Domain Status* is **Available**.

---

### 3. Add API Mapping

Each domain can have **exactly one root mapping** based on our current implementation.

On the *Custom Domain* details page for the subdomain you're configuring, navigate to the bottom of the page and select **Configure API mappings**.

Add a new mapping in the following style: 

```text
Domain: dev.erglytics.com
API: erglytics-dev
Stage: Prod
Path: (leave blank)
```

IMPORTANT:
Only one blank-path mapping is allowed per domain.

---

### 4. Cognito Configuration

Update the app client callback + sign-out URLs.

Example:

```text
https://dev.erglytics.com/auth/callback
https://dev.erglytics.com/signin
```

---

### 5. Deployment

During deployment, update `AppBaseUrl` to match the stack domain.

Example:

```text
AppBaseUrl=https://dev.erglytics.com
```

Also, it is the default, but ensure that `CognitoHostedUiDomain`is set to `auth.erglytics.com` during deployment too. This makes sure that the stack is using the custom domain for the Cognito login/signup pages.

---

## Important Notes:

- With this change you **CANNOT** use raw API Gateway URLs anymore.
- each stack gets its own subdomain
- wildcard certificate is reused
- only one root API mapping per domain
- Cognito URLs must match the domain
- wildcard certificate is in east-2, BUT auth certificate has to be in east-1 because of Cognito setup

---

## Common Issues

When setting this up I came across a couple common issues.

### Too many redirects

Usually caused by:

- wrong API mapping
- duplicate `/Prod`
- incorrect callback URLs

### Forbidden

Usually means:

- route requires authentication
- wrong mapping path

### Styles not loading

Usually caused by:

```text
/Prod/static/...
```

instead of

```text
/static/...
```

Check `ProxyFix` and domain mapping.

Should be fixed by this point, but if this problem reoccurs, then this was how I solved it.