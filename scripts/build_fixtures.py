import json, pathlib
from trust_eval.corpus import build_corpus
out = pathlib.Path("fixtures/valid"); out.mkdir(parents=True, exist_ok=True)
bundles = build_corpus()
for b in bundles:
    (out / f"{b.bundle_id}.json").write_text(json.dumps(b.model_dump(), indent=2, sort_keys=True) + "\n")
index = {"schema_version": bundles[0].manifest.schema_version, "count": len(bundles),
         "bundle_ids": [b.bundle_id for b in bundles]}
pathlib.Path("fixtures/index.json").write_text(json.dumps(index, indent=2) + "\n")
print(f"wrote {len(bundles)} valid bundles to fixtures/valid/")
