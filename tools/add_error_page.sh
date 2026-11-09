#!/bin/bash
# Run by .cpanel.yml on every deploy (Nov 9, 2026). Tells the web server to show our
# friendly /404.html for addresses that don't exist. Adds one line to the live site's
# .htaccess only if it isn't there yet, and leaves the rest of that file untouched.
f="${1:?}.htaccess"
touch "$f"
grep -q '^ErrorDocument 404' "$f" || printf '\nErrorDocument 404 /404.html\n' >> "$f"
