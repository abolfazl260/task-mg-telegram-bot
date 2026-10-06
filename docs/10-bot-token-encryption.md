# Managed Bot Token Encryption

TaskMG stores managed Telegram Bot API tokens using authenticated encryption. This applies to Bot Profiles persisted in the `custom_bots` table.

## Ciphertext format

Stored values use a versioned envelope:

```text
enc:v1:<key_id>:<fernet_ciphertext>
```

The database contains the ciphertext and key identifier only. Encryption keys must be supplied by the deployment environment and must never be committed to Git.

## Configure the keyring

Generate a Fernet key on the target environment:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Configure the keyring in the service environment:

```env
BOT_TOKEN_ENCRYPTION_KEYS_JSON={"2026-10":"<generated-fernet-key>"}
BOT_TOKEN_ACTIVE_KEY_ID=2026-10
```

The JSON object may contain multiple keys during rotation. New writes always use `BOT_TOKEN_ACTIVE_KEY_ID`.

## Migrate existing plaintext rows

Back up the SQLite database before migration, then run from the application directory:

```bash
python scripts/migrate_bot_tokens.py
```

The command prints counts only, for example:

```json
{"encrypted": 3, "legacy_plaintext": 0, "rotated": 0, "unchanged": 2}
```

It never prints token values. Managed runtime reads also support backward-compatible plaintext rows and automatically rewrap them when a valid keyring is configured.

New or replaced managed tokens fail closed if no encryption key is configured.

## Rotate keys

1. Generate a new Fernet key.
2. Add it to `BOT_TOKEN_ENCRYPTION_KEYS_JSON` without removing the old key.
3. Set `BOT_TOKEN_ACTIVE_KEY_ID` to the new key identifier.
4. Run `python scripts/migrate_bot_tokens.py`.
5. Verify that the result reports no remaining rotation work and that bots start normally.
6. Back up the migrated database.
7. Remove the old key from the keyring only after all stored tokens have been rewrapped.

Example during rotation:

```env
BOT_TOKEN_ENCRYPTION_KEYS_JSON={"2026-10":"<old-key>","2027-01":"<new-key>"}
BOT_TOKEN_ACTIVE_KEY_ID=2027-01
```

If ciphertext references a missing key, TaskMG raises a generic secret-store error and does not attempt to use the ciphertext as a Telegram token.

## Operational rules

- Keep the environment file readable only by the service account.
- Back up the keyring separately from the database; the database alone is insufficient to recover encrypted tokens.
- Never log `BOT_TOKEN_ENCRYPTION_KEYS_JSON`, plaintext bot tokens, or ciphertext payloads.
- Rotate a Telegram Bot API token in BotFather independently from encryption-key rotation. The Back Office token replacement path encrypts the new token before persistence.
