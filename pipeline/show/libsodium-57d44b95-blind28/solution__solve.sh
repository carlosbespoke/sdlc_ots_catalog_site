#!/usr/bin/env bash
# Reference solution. Undoes each edit and writes the expected report.
# Proves the task is solvable. Never present in the agent image.
set -euo pipefail
cd /workspace/repo
git apply --whitespace=nowarn /solution/solution.patch
mkdir -p /app
cat > /app/rca.json <<'RCA'
{
  "causes": [
    {
      "file": "/workspace/repo/src/libsodium/crypto_pwhash/scryptsalsa208sha256/crypto_scrypt-common.c",
      "function": "escrypt_parse_setting"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_sign/ed25519/ref10/open.c",
      "function": "crypto_sign_ed25519_open"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_ipcrypt/ipcrypt_aesni.c",
      "function": "pfx_encrypt"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_pwhash/scryptsalsa208sha256/pwhash_scryptsalsa208sha256.c",
      "function": "crypto_pwhash_scryptsalsa208sha256"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_aead/xchacha20poly1305/aead_xchacha20poly1305.c",
      "function": "_decrypt_detached"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_aead/aes256gcm/aesni/aead_aes256gcm_aesni.c",
      "function": "aes_gcm_encrypt_generic"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_secretstream/xchacha20poly1305/secretstream_xchacha20poly1305.c",
      "function": "crypto_secretstream_xchacha20poly1305_push"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_pwhash/scryptsalsa208sha256/sse/pwhash_scryptsalsa208sha256_sse.c",
      "function": "smix"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_xof/shake256/ref/shake256_ref.c",
      "function": "shake256_ref_update"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_kem/mlkem768/ref/kem_mlkem768_ref.c",
      "function": "mlkem768_ref_dec"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_generichash/blake2b/ref/blake2b-ref.c",
      "function": "blake2b_init_salt_personal"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_aead/aegis256/aead_aegis256.c",
      "function": "crypto_aead_aegis256_encrypt_detached"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_core/ed25519/ref10/ed25519_ref10.c",
      "function": "sc25519_muladd"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_generichash/blake2b/ref/generichash_blake2b.c",
      "function": "crypto_generichash_blake2b_init_salt_personal"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_core/ed25519/core_h2c.c",
      "function": "core_h2c_string_to_hash_sha512"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_pwhash/argon2/argon2-encoding.c",
      "function": "argon2_decode_string"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_pwhash/argon2/pwhash_argon2i.c",
      "function": "_needs_rehash"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_aead/chacha20poly1305/aead_chacha20poly1305.c",
      "function": "crypto_aead_chacha20poly1305_decrypt_detached"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_scalarmult/ed25519/ref10/scalarmult_ed25519_ref10.c",
      "function": "_crypto_scalarmult_ed25519"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_core/ed25519/core_ed25519.c",
      "function": "crypto_core_ed25519_is_valid_point"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_shorthash/siphash24/ref/shorthash_siphashx24_ref.c",
      "function": "crypto_shorthash_siphashx24"
    },
    {
      "file": "/workspace/repo/src/libsodium/sodium/core.c",
      "function": "sodium_misuse"
    },
    {
      "file": "/workspace/repo/src/libsodium/sodium/codecs.c",
      "function": "sodium_bin2ip"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_xof/turboshake128/ref/turboshake128_ref.c",
      "function": "turboshake128_ref_update"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_xof/shake128/ref/shake128_ref.c",
      "function": "shake128_ref_update"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_pwhash/scryptsalsa208sha256/crypto_scrypt-common.c",
      "function": "crypto_pwhash_scryptsalsa208sha256_ll"
    }
  ]
}
RCA
