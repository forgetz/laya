Put your organisation's root CA certificate(s) here as PEM files ending in `.crt` when the proxy
inspects TLS (you see `CERTIFICATE_VERIFY_FAILED` / `self-signed certificate in certificate chain`
during the build). The Dockerfile adds them to the system trust store before pip or the model
download runs. Leave the folder empty otherwise.

A `.cer` file in PEM form can simply be renamed to `.crt`. A DER (binary) file needs converting:

    openssl x509 -inform der -in corp-root.cer -out corp-root.crt
