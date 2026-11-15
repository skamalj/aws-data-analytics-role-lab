"""
Larchmont agent: one small agent, configured by environment variables, used by every challenge.

AgentCore Runtime mode (default): HTTP on 0.0.0.0:8080, POST /invocations (JSON), GET /ping.
Self-hosted mode (challenge S2, on EC2):  python3 agent.py --self-hosted [--action credential]

Payload: {"action": "whoami" | "credential" | "file_report", ...}

Environment:
  AGENT_NAME        name reported in responses
  IDENTITY_MODE     "jwt"     - who is calling comes from the (runtime-verified) Authorization header
                    "payload" - who is calling comes from payload["acting_as"]   (legacy, spoofable)
  CREDENTIAL        "apikey" | "oauth2" | "none"   - outbound credential fetched from the AgentCore token vault
  PROVIDER_NAME     credential provider name
  OAUTH_SCOPES      comma-separated scopes for the oauth2 (M2M) flow
  SSM_PREFIX        self-hosted only: parameter path holding workload-name and credential-provider
"""
import base64
import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"
NAME = os.environ.get("AGENT_NAME", "larchmont-agent")
_dp = None


def dataplane():
    global _dp
    if _dp is None:
        _dp = boto3.client("bedrock-agentcore", region_name=REGION)
    return _dp


def err(e):
    code = getattr(e, "response", {}).get("Error", {}).get("Code") if hasattr(e, "response") else None
    return {"error": code or type(e).__name__, "message": str(e)[:300]}


def jwt_claims(auth_header):
    """Claims of the bearer token. Signature/expiry were already verified by the AgentCore Runtime authorizer."""
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    try:
        part = auth_header.split()[1].split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:  # noqa: BLE001
        return None


def caller(payload, headers):
    mode = os.environ.get("IDENTITY_MODE", "jwt")
    if mode == "payload":
        return {"source": "payload", "principal": payload.get("acting_as", "unknown")}
    c = jwt_claims(headers.get("Authorization"))
    if not c:
        return {"source": "none", "principal": None}
    return {"source": "jwt", "principal": c.get("client_id") or c.get("sub"), "scope": c.get("scope"), "iss": c.get("iss")}


def fetch_credential(workload_token, provider=None, kind=None):
    kind = kind or os.environ.get("CREDENTIAL", "none")
    provider = provider or os.environ.get("PROVIDER_NAME")
    if kind == "none":
        return {"credential": "not-configured"}
    if not workload_token:
        return {"credential": "failed", "error": "NoWorkloadAccessToken",
                "message": "no workload access token: the agent has no identity to present to the token vault"}
    try:
        if kind == "apikey":
            secret = dataplane().get_resource_api_key(workloadIdentityToken=workload_token,
                                                      resourceCredentialProviderName=provider)["apiKey"]
        else:
            scopes = [s for s in os.environ.get("OAUTH_SCOPES", "").split(",") if s]
            secret = dataplane().get_resource_oauth2_token(workloadIdentityToken=workload_token, resourceCredentialProviderName=provider,
                                                           scopes=scopes, oauth2Flow="M2M")["accessToken"]
    except Exception as e:  # noqa: BLE001
        return {"credential": "failed", "provider": provider, **err(e)}
    # never return the secret itself - only a fingerprint
    return {"credential": "obtained", "kind": kind, "provider": provider, "fingerprint": hashlib.sha256(secret.encode()).hexdigest()[:12]}


def handle(payload, headers):
    action = payload.get("action", "whoami")
    wat = headers.get("WorkloadAccessToken")
    who = caller(payload, headers)
    base = {"agent": NAME, "action": action, "caller": who, "workload_token": bool(wat),
            "runtime_user_id": headers.get("X-Amzn-Bedrock-AgentCore-Runtime-User-Id")}
    if action == "whoami":
        return base
    if action == "credential":
        return {**base, **fetch_credential(wat)}
    if action == "file_report":
        if not who["principal"]:
            return {**base, "filed": False, "error": "UnknownFiler", "message": "cannot determine who is filing"}
        rid = "RR-" + hashlib.sha256(f"{who['principal']}|{payload.get('report', '')}".encode()).hexdigest()[:8].upper()
        return {**base, "filed": True, "report_id": rid, "filed_by": who["principal"], "identity_source": who["source"]}
    return {**base, "error": "UnknownAction"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/ping"):
            self._send(200, {"status": "Healthy", "time_of_last_update": int(time.time())})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/invocations"):
            return self._send(404, {"error": "not found"})
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid JSON"})
        hdrs = {k: self.headers.get(k) for k in ("Authorization", "WorkloadAccessToken", "X-Amzn-Bedrock-AgentCore-Runtime-User-Id")}
        res = handle(payload, hdrs)
        print(json.dumps({"agent": NAME, "action": res.get("action"), "caller": res.get("caller"), "credential": res.get("credential")}), flush=True)
        self._send(200, res)

    def log_message(self, *args):
        pass


def self_hosted(action):
    """Agent running outside AgentCore Runtime: it must obtain its own workload access token."""
    prefix = os.environ.get("SSM_PREFIX", "/larchmont/research-agent")
    out = {"agent": NAME, "mode": "self-hosted"}
    try:
        ssm = boto3.client("ssm", region_name=REGION)
        workload = ssm.get_parameter(Name=f"{prefix}/workload-name")["Parameter"]["Value"]
        provider = ssm.get_parameter(Name=f"{prefix}/credential-provider")["Parameter"]["Value"]
        out.update(workload=workload, provider=provider)
    except Exception as e:  # noqa: BLE001
        return {**out, "step": "read-config", **err(e)}
    try:
        wat = dataplane().get_workload_access_token(workloadName=workload)["workloadAccessToken"]
        out["workload_token"] = True
    except Exception as e:  # noqa: BLE001
        return {**out, "step": "get-workload-access-token", "workload_token": False, **err(e)}
    if action == "whoami":
        return out
    return {**out, **fetch_credential(wat, provider, "apikey")}


if __name__ == "__main__":
    if "--self-hosted" in sys.argv:
        act = sys.argv[sys.argv.index("--action") + 1] if "--action" in sys.argv else "credential"
        print(json.dumps(self_hosted(act)))
        sys.exit(0)
    print(f"{NAME} listening on :8080 (region {REGION})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
