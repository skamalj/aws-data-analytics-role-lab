# Mission D13 solution: Partner A gets partner B's answers

```bash
patch -p1 -E < solutions/D13-multi-tenant-kb-metadata/fix.patch     # -E removes the misnamed sidecar files
./scripts/deploy.sh D13                                              # uploads the renamed sidecars, deletes the old objects
$(terraform -chdir=missions/D13-multi-tenant-kb-metadata/terraform output -raw sync_command)
python3 missions/D13-multi-tenant-kb-metadata/scenarios/check.py
```

## Fault 1: coastline's sidecars have the wrong file names

| | |
|---|---|
| Symptom | Coastline searches return nothing. The sync scans more than 6 "documents" |
| Root cause | A sidecar must be named **`<document file name>.metadata.json`**, so `returns.md.metadata.json`. `returns.metadata.json` isn't recognised as metadata: the document is indexed **without** `tenant_id` (so every tenant-filtered query excludes it), and the JSON file itself is ingested as a document |
| Fix | Rename both coastline sidecars |

## Fault 2: one sidecar isn't in the sidecar format

| | |
|---|---|
| Symptom | `peak-gear/returns.md` fails, or loses its metadata, during ingestion (`failureReasons` mentions the metadata file) |
| Root cause | Attributes must be wrapped in `{"metadataAttributes": { … }}`. Top-level keys aren't valid |
| Fix | Wrap them. Validate sidecars in CI with a JSON schema |

## Fault 3: the tool filters on the wrong key, and trusts the model

| | |
|---|---|
| Symptom | With the wrong key (`tenant`), no chunk matches. When the model passes `tenant_id`, it *wins* over the authenticated context |
| Fix | Read the tenant **only** from `event.context.tenant_id` (and refuse without one). Filter with `andAll: [tenant_id = <tenant>, audience = customer]`, using the same keys as the sidecars |

## Debrief answers

1. Filterable: anything access control or routing depends on (`tenant_id`, `audience`, `doc_type`, language). One KB with a tenant filter keeps cost and operations
   flat as partners grow. Separate KBs are for strict isolation, per-tenant encryption keys, or very different content.
2. A filter is only as good as the code that builds it, and a bug or a missing filter leaks everything. For high-risk data, add layers: separate stores or
   KBs per tenant, row-level security on a self-managed table (D12), output checks that every returned `source` belongs to the tenant, and audit logs.
3. A pre-upload check (CI or an S3-triggered Lambda) that verifies every document has `<name>.metadata.json`, that it parses, that it matches a schema
   (`metadataAttributes` with the required keys), and that `tenant_id` matches the folder.
4. RLS enforces isolation **inside the database for every query**, whoever issues it. KB filters enforce it **per API call**, in application code. RLS is stronger.
   KB filters are fully managed and simpler. Both depend on the tenant coming from authentication.
