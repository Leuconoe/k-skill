---
"toss-securities": major
"@nomadamas/k-skill": patch
---

Remove the unofficial `tossctl` fallback and expose only the official Toss Securities Open API client. Calls now require official OAuth credentials and do not fall back to CLI sessions, scraping, or undocumented HTTP routes.
