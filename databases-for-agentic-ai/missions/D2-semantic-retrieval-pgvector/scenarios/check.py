"""
Self-check for D2 (run after a successful sync).
Part A: the knowledge base on pgvector works. Part B: metadata files and the agent's audience filter.
"""
import json
import os
import sys

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, mission_outputs, rows, safe  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
region = out["runtime_arn"].split(":")[3]
admin = Db("admin")

# ---- Part A
r, err = safe(admin.run, "SELECT count(*) AS n, count(DISTINCT metadata->>'x-amz-bedrock-kb-source-uri') AS docs, "
                         "min(vector_dims(embedding)) AS dims FROM bedrock_kb.manual_chunks")
st = rows(r)[0] if r else {}
check("A: all 6 documents are ingested into bedrock_kb.manual_chunks with 1024-d vectors",
      st.get("docs") == 6 and st.get("dims") == 1024, err or json.dumps(st))

# ---- Part B
meta = rows(admin.run("SELECT metadata->>'x-amz-bedrock-kb-source-uri' AS uri, custom_metadata->>'audience' AS audience "
                      "FROM bedrock_kb.manual_chunks"))
bad = sorted({f"{m['uri'].rsplit('/', 1)[-1]}={m['audience']}" for m in meta if m["audience"] not in ("customer", "staff")})
check("B: every chunk has audience = customer or staff", not bad, ", ".join(bad))

runtime_id = out["runtime_arn"].rsplit("/", 1)[-1]
env = boto3.client("bedrock-agentcore-control", region_name=region).get_agent_runtime(agentRuntimeId=runtime_id)["environmentVariables"]
flt = json.loads(env.get("KB_FILTER") or "null")
kb = boto3.client("bedrock-agent-runtime", region_name=region)


def search(q):
    vsc = {"numberOfResults": 4, **({"filter": flt} if flt else {})}
    res = kb.retrieve(knowledgeBaseId=out["knowledge_base_id"], retrievalQuery={"text": q},
                      retrievalConfiguration={"vectorSearchConfiguration": vsc})["retrievalResults"]
    return [x["location"]["s3Location"]["uri"].rsplit("/", 1)[-1] for x in res]


hits = search("staff discount code and price override rules")
check("B: the agent's filter never returns the staff-only document", "staff-discount-matrix.md" not in hits, ", ".join(hits))
hits = search("What is the warranty on an expedition pack?")
check("B: customers still get the warranty policy", "warranty-policy.md" in hits, ", ".join(hits) or "no hits")
finish()
