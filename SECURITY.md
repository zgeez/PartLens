# Security

Please report security issues privately to the repository owner through GitHub's private vulnerability
reporting (Security › Report a vulnerability) rather than in a public issue.

How PartLens handles sensitive data:

- **API keys** (JLCPCB, Zetaris) are entered in the app and encrypted with Windows DPAPI for the current
  Windows user in `%LOCALAPPDATA%\PartLens\settings.json`. They are never written to the repository, the
  executable, browser storage, logs or run records; error text is redacted before display.
- **Supplier access** is read-only and limited to the official JLCPCB component-detail endpoint and your own
  Zetaris gateway. PartLens never places orders.
- **The desktop bridge** accepts calls only from its bundled page with a per-launch token, and refuses
  requests after navigation away from the local document.
- **Inference** is local (Ollama on loopback). Paid or cloud inference is disabled with no silent fallback.
- The build refuses to package any source file that contains a configured credential value.
