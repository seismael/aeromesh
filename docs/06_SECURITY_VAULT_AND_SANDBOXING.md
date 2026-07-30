# Zero-Trust Vault & Sandbox Security Architecture Specification

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Package Path:** [`packages/aero/src/aero/infrastructure/vault.py`](file:///c:/dev/projects/aeromesh/packages/aero/src/aero/infrastructure/vault.py)  
**Security Paradigm:** Strict Zero-Trust & Explicit Human Permission Protocol  

---

## 1. Executive Summary: Strict User Permission Protocol

In accordance with Zero-Trust principles, **no credential found in environment variables or configuration files is used without explicit human permission in interactive sessions**.

1. **Interactive Human Sessions (`non_interactive=False`)**:
   - `ZeroTrustVaultResolver` displays existing keys found in the environment to the user (`AMXTerminalUI.prompt_credential_approval`).
   - The user must explicitly approve using the discovered key, enter a replacement key, or reject the credential.
   - If rejected, execution halts deterministically with `AMX_ERR_VAULT_KEY_MISSING` (Exit 20).
2. **Automated Non-Interactive Sessions (`--non-interactive`)**:
   - For background cron jobs or CI/CD pipelines, pre-approved credentials are resolved automatically from environment variables or vault keyring stores.

---

## 2. Explicit User Approval UI Layout

```
┌──────────────────────── 🔑 Explicit User Key Approval ────────────────────────┐
│ Found Environment Credential: GITHUB_TOKEN (Value: ghp_****...90)            │
│                                                                               │
│ Options:                                                                      │
│   [1] Approve using existing environment key                                  │
│   [2] Enter a new secret key                                                  │
│   [3] Reject and abort                                                        │
└───────────────────────────────────────────────────────────────────────────────┘
Select option [1-3] (Default 1): 1
✅ Approved using existing key 'GITHUB_TOKEN'.
```
