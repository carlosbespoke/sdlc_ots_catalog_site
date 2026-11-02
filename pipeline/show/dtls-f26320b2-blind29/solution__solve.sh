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
      "file": "internal/handshake/fsm.go",
      "function": "handleRetransmitTimeout"
    },
    {
      "file": "pkg/protocol/extension/dtls13/early_data.go",
      "function": "EarlyData.UnmarshalData"
    },
    {
      "file": "state.go",
      "function": "State.ExportKeyingMaterial"
    },
    {
      "file": "errors.go",
      "function": "invalidCipherSuiteError.Is"
    },
    {
      "file": "conn.go",
      "function": "reconstructSequenceNumber"
    },
    {
      "file": "internal/flight/flight13/extensions.go",
      "function": "processClientHelloExtensions"
    },
    {
      "file": "pkg/protocol/handshake/message_new_connection_id.go",
      "function": "MessageNewConnectionID.Marshal"
    },
    {
      "file": "errors.go",
      "function": "alertError.IsFatalOrCloseNotify"
    },
    {
      "file": "internal/flight/flight12/flight3handler.go",
      "function": "handleResumption"
    },
    {
      "file": "internal/handshake/protected_flight.go",
      "function": "protectedHandshakeFlight.verifyConnection"
    },
    {
      "file": "pkg/protocol/extension/dtls13/post_handshake_auth.go",
      "function": "PostHandshakeAuth.UnmarshalData"
    },
    {
      "file": "pkg/protocol/extension/dtls13/psk_key_exchange_modes.go",
      "function": "PSKKeyExchangeModes.UnmarshalData"
    },
    {
      "file": "internal/flight/flight13/flight1handler.go",
      "function": "flight1Generate"
    },
    {
      "file": "internal/handshake/reliable_flight.go",
      "function": "reliableFlight.acknowledge"
    },
    {
      "file": "pkg/protocol/handshake/message_client_hello.go",
      "function": "MessageClientHello.Marshal"
    },
    {
      "file": "pkg/protocol/recordlayer/inner_plaintext.go",
      "function": "InnerPlaintext.Unmarshal"
    },
    {
      "file": "internal/flight/flight12/flight3handler.go",
      "function": "flight3Generate"
    },
    {
      "file": "pkg/protocol/handshake/extensions.go",
      "function": "extensionValueForContext"
    },
    {
      "file": "internal/ciphersuite/tls_psk_with_aes_128_cbc_sha256.go",
      "function": "TLSPskWithAes128CbcSha256.Init"
    },
    {
      "file": "pkg/protocol/change_cipher_spec.go",
      "function": "ChangeCipherSpec.Unmarshal"
    },
    {
      "file": "internal/handshake/handshake_context.go",
      "function": "handshakeContext.transitionRequiresReaderPause"
    },
    {
      "file": "pkg/crypto/signaturehash/signaturehash.go",
      "function": "Algorithm.Marshal"
    },
    {
      "file": "internal/ciphersuite/tls_psk_with_aes_128_cbc_sha256.go",
      "function": "TLSPskWithAes128CbcSha256.IsInitialized"
    },
    {
      "file": "internal/handshake/reliable_flight.go",
      "function": "reliableFlight.pendingForMessage"
    },
    {
      "file": "internal/handshake/handshake_context.go",
      "function": "handshakeContext.afterSend"
    },
    {
      "file": "internal/flight/flight13/flight1handler.go",
      "function": "flight1Parse"
    },
    {
      "file": "pkg/crypto/elliptic/elliptic.go",
      "function": "generateX25519MLKEM768ServerKeypair"
    },
    {
      "file": "pkg/protocol/handshake/message_new_connection_id.go",
      "function": "MessageNewConnectionID.Unmarshal"
    },
    {
      "file": "config.go",
      "function": "effectiveProtocolVersionRange"
    }
  ]
}
RCA
mkdir -p "$(dirname /app/RESEARCH_AND_PLANNING.md)"
cat > /app/RESEARCH_AND_PLANNING.md <<'PLAN'
# Research and plan

## What I investigated
I read the reported misbehaviours and traced each one to the function whose output
changed, comparing the broken areas against neighbouring code that still works to localise
the edits rather than guessing from names.

## Constraints that shape the change
Each defect is a single-line edit inside one function. The fix must restore the original
behaviour at that site without touching unrelated code, and must be reachable from the same
call paths the reports describe.

## How I will carry it out
Restore each identified site to the behaviour the reports expect, record every edited
function in /app/rca.json, then verify by re-exercising the affected behaviours and
confirming the previously-wrong outputs are correct again while the working neighbours stay
working.
PLAN
