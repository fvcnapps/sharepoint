#!/usr/bin/env bash
# Makes a self-signed certificate for the tenant admin app. Run once, on the machine
# that will hold the private key. Upload the .cer to the app registration; keep the .pem.
set -euo pipefail
name="${1:-tvc-spo-admin}"
days="${2:-730}"
openssl req -x509 -newkey rsa:2048 -sha256 -days "$days" -nodes \
  -subj "/CN=${name}" -keyout "${name}.key" -out "${name}.crt"
cat "${name}.key" "${name}.crt" > "${name}.pem"
openssl x509 -in "${name}.crt" -outform DER -out "${name}.cer"
rm "${name}.key"
chmod 600 "${name}.pem"
echo "upload   : ${name}.cer   (public, goes to Entra > app > Certificates & secrets)"
echo "keep     : ${name}.pem   (private, never leaves this machine or Key Vault)"
echo "expires  : $(openssl x509 -in "${name}.crt" -noout -enddate)"
