# Private CV downloads

Production uses the existing Apache PHP-FPM hosting. The contact form sends a
POST request to `/cv-download.php`; only the document matching the submitted
code is returned as an attachment. Codes, filenames and other CV versions are
not listed in the page.

## Private storage

The PHP worker owns `/var/tmp/peterhudcovic-cv` (mode 0700). PDFs and the config
have mode 0600. Config contains bcrypt hashes, never plaintext codes. Private
files are outside `/var/www/html` and must never be committed to Git or added to
the public SCP source list. Preserve this private directory during server moves
and maintenance; it is not part of the public deployment or a Git backup.

The initial transfer used a short-lived, authenticated installer over HTTPS.
The installer is removed by deployment, and its temporary GitHub secret is
deleted after verification. Future CV updates require a deliberate private
provisioning step; ordinary pushes change only the public endpoint and website.

## Protection and deployment

The PHP endpoint accepts JSON POST requests from the website origin, applies
bcrypt verification, disables caching, returns a generic download filename,
and limits attempts to 10 per 15 minutes per Apache connection address. It uses
a nonblocking file lock to bound simultaneous password checks. When a reverse
proxy does not restore client addresses, the limit may be shared by its users.
Untrusted forwarding headers are not used for client identity.

GitHub Actions uploads and checks the PHP endpoint before publishing the form.
The check requires an invalid code to return HTTP 403. Missing private storage
returns HTTP 503 and stops deployment before the new HTML is copied.

## Local preview

`python cv_server.py --config <private-config-path> --port 8766`

Visit `http://127.0.0.1:8766/#connect`. This local Python preview mirrors the
form endpoint and uses a private JSON config outside the repository, with
`allowed_origins` and `documents` (path, salt, scrypt hash). It is not the
production backend. Local test command: `python -m unittest test_cv_server.py`.
