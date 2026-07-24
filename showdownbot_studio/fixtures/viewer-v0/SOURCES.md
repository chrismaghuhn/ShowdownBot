# Viewer v0 Plan A fixture sources

## fixture-01
- source_kind: synthetic-coherent-v1
- battle_id: synthetic00000001
- run_id: syntheticrun00001
- git_sha: unknown
- config_hash: bbbbbbbbbbbbbbbb
- schedule_hash: cccccccccccccccc
- config_id: synthetic_fixture
- format_id: gen9championsvgc2026regma
- dirty: false
- seed_index: 0
- our_side: p1
- note: bundle emits source_provenance.dirty null because git_sha is unknown (§8.4)
- `fixtures/viewer-v0/sources/fixture-01/battle.log` sha256 `883a930a78e7b9a4f193b7846c826a8f992682c1ce1ed77f4da89021e0b933dc`
- `fixtures/viewer-v0/sources/fixture-01/decision_trace.jsonl` sha256 `54bd449414199dfac7c2cbaf0f995f3114df296ae4d95619d94f1e4bab5ec8ca`
- `fixtures/viewer-v0/sources/fixture-01/results.config-manifest.json` sha256 `af503a05ce17b9527a3e97e2b89729007d5b092921abf4f91422902b46cab42e`
- `fixtures/viewer-v0/sources/fixture-01/results.jsonl` sha256 `5c12db6757eb7bada142b63efa4b3bae7fd9b2908e633cb3ca60b696329345a0`
- `fixtures/viewer-v0/sources/fixture-01/results.manifest.json` sha256 `d373e92589c42551ed3a5e60ff8567286c381f589740778bba3ea587cef3eba5`

## fixture-03
- source_kind: synthetic-coherent-v1
- battle_id: synthetic00000003
- run_id: syntheticrun00003
- git_sha: unknown
- config_hash: dddddddddddddddd
- schedule_hash: eeeeeeeeeeeeeeee
- config_id: synthetic_fixture_03
- format_id: gen9championsvgc2026regma
- dirty: false
- seed_index: 0
- our_side: p1
- note: bundle emits source_provenance.dirty null because git_sha is unknown (§8.4)
- `fixtures/viewer-v0/sources/fixture-03/battle.log` sha256 `883a930a78e7b9a4f193b7846c826a8f992682c1ce1ed77f4da89021e0b933dc`
- `fixtures/viewer-v0/sources/fixture-03/decision_trace.jsonl` sha256 `41cb296906d8e287adbb3c4eb50f9ea07909e51c1333be378a2484ca9eb98a96`
- `fixtures/viewer-v0/sources/fixture-03/results.config-manifest.json` sha256 `eed9e311925f5623d5b33e50119f66492a82d8a538a8104c606484ff3146ba36`
- `fixtures/viewer-v0/sources/fixture-03/results.jsonl` sha256 `999866bb0982450776485866b3bf6581f759de1c2c497224755210ba5bf1a484`
- `fixtures/viewer-v0/sources/fixture-03/results.manifest.json` sha256 `023852a15512f1f1e1bfbc08bcae6921d800b65742b82fcd0470797efe683677`

## fixture-04
- source_kind: replay-only (fixture-01 battle slice)
- `fixtures/viewer-v0/sources/fixture-04/battle.log` sha256 `883a930a78e7b9a4f193b7846c826a8f992682c1ce1ed77f4da89021e0b933dc`
- `fixtures/viewer-v0/sources/fixture-04/results.config-manifest.json` sha256 `af503a05ce17b9527a3e97e2b89729007d5b092921abf4f91422902b46cab42e`
- `fixtures/viewer-v0/sources/fixture-04/results.jsonl` sha256 `5c12db6757eb7bada142b63efa4b3bae7fd9b2908e633cb3ca60b696329345a0`
- `fixtures/viewer-v0/sources/fixture-04/results.manifest.json` sha256 `d373e92589c42551ed3a5e60ff8567286c381f589740778bba3ea587cef3eba5`

## fixture-05
- source_kind: smoke trace-only
- `fixtures/viewer-v0/sources/fixture-05/decision_trace.jsonl` sha256 `7070338b77425621b6c3720e1f5cea651dff832dc6a0a8884de047c6647ff197`
- `fixtures/viewer-v0/sources/fixture-05/results.config-manifest.json` sha256 `c953a619529338c8b3ed26d68042b5ee1a4de4323b94bba3324b847f408b70c7`
- `fixtures/viewer-v0/sources/fixture-05/results.jsonl` sha256 `f4da66b80d700343998da818cc3c89aa239fb8b3c3ecbd214930f209c8bd7cb0`
- `fixtures/viewer-v0/sources/fixture-05/results.manifest.json` sha256 `1224ceac19eb7fa97e0b32bb844b9e95a9aa3eb97de2f1387c5a8a00a1cdf957`

## fixture-06
- source_kind: invalid hash (bundle copy)
- `fixtures/viewer-v0/sources/fixture-06/bundle/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/sources/fixture-06/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-06/bundle/decisions.jsonl` sha256 `546ef147cf26532bc276812dcdb539a141a611dde2fa65f7d11d817521efa004`
- `fixtures/viewer-v0/sources/fixture-06/bundle/manifest.json` sha256 `c42b843880a09fd88aa9a712d8e51f4ac46223e15e616bc02f30db9371d6d369`
- `fixtures/viewer-v0/sources/fixture-06/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-07
- source_kind: unsupported major (bundle copy)
- note: copy of bundles/fixture-01 with viewer_bundle_schema.major mutated 1 -> 2; every
  data file is byte-identical to bundle/fixture-01 (unchanged, correctly-hashed); only
  manifest.json differs
- `fixtures/viewer-v0/sources/fixture-07/bundle/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/sources/fixture-07/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-07/bundle/decisions.jsonl` sha256 `cbd340e8f50f8eed4ac520e0337ab3cad17d070df0b8b406029ad21f7900d0a0`
- `fixtures/viewer-v0/sources/fixture-07/bundle/manifest.json` sha256 `b981eaeb816a8bae600898bbee34fa9eaa27f8c42aae6aa7a6f953a3209bf5ca`
- `fixtures/viewer-v0/sources/fixture-07/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-08
- source_kind: missing mandatory file (bundle copy)
- note: copy of bundles/fixture-01 with decisions.jsonl deleted from disk; manifest.json is
  BYTE-IDENTICAL to bundle/fixture-01's (same sha256 as fixture-01's own manifest.json) --
  files.decision_trace still declares present:true/required:true with its original,
  correct sha256, which is now unreachable on disk. This is the fixture-integrity guard's
  second known exception (tests/python/test_fixture_manifest_hash_guard.py,
  godot/tests/bundle/test_fixture_manifest_hash_guard.gd): a present:true entry whose file
  is absent is reported as "missing_on_disk", asserted positively, not excluded
- `fixtures/viewer-v0/sources/fixture-08/bundle/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/sources/fixture-08/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-08/bundle/decisions.jsonl` -- deleted; manifest still declares sha256 `cbd340e8f50f8eed4ac520e0337ab3cad17d070df0b8b406029ad21f7900d0a0` (unreachable on disk, by design)
- `fixtures/viewer-v0/sources/fixture-08/bundle/manifest.json` sha256 `c42b843880a09fd88aa9a712d8e51f4ac46223e15e616bc02f30db9371d6d369`
- `fixtures/viewer-v0/sources/fixture-08/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-09
- source_kind: duplicate decision identity (bundle copy)
- note: copy of bundles/fixture-01 with decisions.jsonl mutated to duplicate the last row
  (decision_index 2 appended a second time, byte-identical to the first occurrence);
  manifest.json's decision_trace hash is correctly recomputed for the mutated bytes via
  python/reseal_manifest_hashes.py -- other files unchanged/correctly-hashed. Same shape as
  godot/tests/fixtures/unit/refuse-duplicate-decision-index, but owned by Plan F's own §14
  catalogue (§0.2) with its own correctly-hashed manifest; does not repeat the §0.6 drift
- `fixtures/viewer-v0/sources/fixture-09/bundle/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/sources/fixture-09/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-09/bundle/decisions.jsonl` sha256 `1b3f2285901fedd008e2b098769f95f760fb3392b8002bade796f7d99258b32a`
- `fixtures/viewer-v0/sources/fixture-09/bundle/manifest.json` sha256 `eb21dbb3c3c6d846129ff97ceda5483dc18c6b782ca15eab5a4e7c475cf7682c`
- `fixtures/viewer-v0/sources/fixture-09/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-11
- source_kind: non-finite value (exporter-side refuse, no bundle produced)
- note: copy of fixture-01/decision_trace.jsonl with row 1's decision_latency_ms mutated to
  NaN. Proved via tests/python/test_f1_fixture_catalogue.py::test_fixture11_non_finite_value_fails_export.
  Finding: through the real load_trace_rows pipeline this is intercepted by
  showdown_bot.eval.decision_capture.validate_trace_row before export_decisions_jsonl's own
  non_finite_value check is ever reached, so the observed refuse reason is "trace_validation",
  not "non_finite_value" as the plan's §1 recipe column assumed -- see the test docstring and
  the task report for the full finding. Bundle contract §15 gate 8 itself only requires
  "fails export" and does not name a reason string, so this is satisfied regardless
- `fixtures/viewer-v0/sources/fixture-11/decision_trace.jsonl` sha256 `c7140dc550f0605215399508a863f688f1545597d78957c1b72a6376ca950f79`

## fixture-14
- source_kind: chosen-candidate desync (exporter-side refuse, no bundle produced)
- note: copy of fixture-01/decision_trace.jsonl with row 2's chosen (and matching candidate)
  candidate_key move_index mutated 1 -> 2; normalized_action left untouched (still move_index
  1), so the resolved chosen candidate disagrees with normalized_action (§11.4). Proved via
  tests/python/test_f1_fixture_catalogue.py::test_fixture14_chosen_candidate_desync_refuses
  (reason "chosen_integrity")
- `fixtures/viewer-v0/sources/fixture-14/decision_trace.jsonl` sha256 `5980b324fed9ae386bb47962f75eaf23a4db1e177cee258bd676e456a59cf8c5`

## fixture-19
- source_kind: unjoinable decision (exports cleanly; not a refuse fixture)
- note: fixture-01's battle.log unchanged; decision_trace.jsonl's row 2 (decision_index 2)
  request_hash mutated to 64 `f` characters, matching no `|request|` line in the log. The
  decision stays a distinct timeline entry with request_protocol_index null, never dropped.
  Proved via tests/python/test_f1_fixture_catalogue.py::test_fixture19_unjoinable_decision_not_dropped
  and godot/tests/bundle/test_bundle_validator.gd::test_fixture19_unjoinable_decision_stays_in_timeline
- `fixtures/viewer-v0/sources/fixture-19/battle.log` sha256 `883a930a78e7b9a4f193b7846c826a8f992682c1ce1ed77f4da89021e0b933dc`
- `fixtures/viewer-v0/sources/fixture-19/decision_trace.jsonl` sha256 `8f0b0ed8c0dde0813513bf166ad6eb620db60f4afb32100ccffd25683188b2f0`

## fixture-21
- source_kind: provenance disagreement (exporter-side refuse, no bundle produced)
- note: fixture-01's decision_trace.jsonl unchanged; results.jsonl's config_hash mutated to
  `deadbeefdeadbeef` (disagreeing with the trace rows' `bbbbbbbbbbbbbbbb`). §14 completeness
  fixture only -- gate 33 is already COVERED by three existing tests (Rev. 5 gate-coverage
  audit, §3), no duplicate test is added here:
  tests/python/test_a6_provenance_modes.py::test_provenance_disagreement_refuses,
  tests/python/test_a6_provenance_modes.py::test_trace_rows_disagreeing_config_hash_refuses,
  tests/python/test_a7_cli.py::test_cli_refuse_provenance_disagreement
- `fixtures/viewer-v0/sources/fixture-21/decision_trace.jsonl` sha256 `54bd449414199dfac7c2cbaf0f995f3114df296ae4d95619d94f1e4bab5ec8ca`
- `fixtures/viewer-v0/sources/fixture-21/results.jsonl` sha256 `ec7f9dc9cfc54f8c7691ba1edad9af8e7b3e93151abce6e91c7eefade88dc4a3`

## fixture-12
- source_kind: unknown required capability (bundle copy)
- note: copy of bundles/fixture-01 with required_capabilities mutated [] -> ["belief_v2"];
  data files unchanged/correctly-hashed; only manifest.json differs
- `fixtures/viewer-v0/sources/fixture-12/bundle/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/sources/fixture-12/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-12/bundle/decisions.jsonl` sha256 `cbd340e8f50f8eed4ac520e0337ab3cad17d070df0b8b406029ad21f7900d0a0`
- `fixtures/viewer-v0/sources/fixture-12/bundle/manifest.json` sha256 `647fd0321401432735878816427d97dabb8665251db72dff21610223e7e95f68`
- `fixtures/viewer-v0/sources/fixture-12/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-22a
- source_kind: mode key required:false present:true (bundle copy, §11.1.1 invariant 1)
- note: copy of bundles/fixture-01 with files.battle_log.required mutated true -> false
  (present stays true); data files unchanged/correctly-hashed; only manifest.json differs
- `fixtures/viewer-v0/sources/fixture-22a/bundle/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/sources/fixture-22a/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-22a/bundle/decisions.jsonl` sha256 `cbd340e8f50f8eed4ac520e0337ab3cad17d070df0b8b406029ad21f7900d0a0`
- `fixtures/viewer-v0/sources/fixture-22a/bundle/manifest.json` sha256 `c92f2842a0eef0164134113261ac1130c9767fe4e95c16f27a303663561de0d1`
- `fixtures/viewer-v0/sources/fixture-22a/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-22b
- source_kind: mode key required:true present:false (bundle copy, §11.1.1 invariant 1)
- note: copy of bundles/fixture-01 with files.battle_log.present mutated true -> false
  (path/sha256 nulled per §5.2; required stays true) and battle.jsonl deleted from disk to
  match the declared absence. Distinct from fixture-08, where the file *is* declared
  present and is merely missing on disk (invariant 5)
- `fixtures/viewer-v0/sources/fixture-22b/bundle/battle.jsonl` -- deleted (files.battle_log.present:false)
- `fixtures/viewer-v0/sources/fixture-22b/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-22b/bundle/decisions.jsonl` sha256 `cbd340e8f50f8eed4ac520e0337ab3cad17d070df0b8b406029ad21f7900d0a0`
- `fixtures/viewer-v0/sources/fixture-22b/bundle/manifest.json` sha256 `74d1078fcaca495ebfcc292406ea1759052ab97e06d47914ed42d80d80e9b971`
- `fixtures/viewer-v0/sources/fixture-22b/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-23
- source_kind: optional key required:true (bundle copy, §11.1.1 invariant 2)
- note: copy of bundles/fixture-01 with files.warnings.required mutated false -> true
  (present stays true); data files unchanged/correctly-hashed; only manifest.json differs
- `fixtures/viewer-v0/sources/fixture-23/bundle/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/sources/fixture-23/bundle/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/sources/fixture-23/bundle/decisions.jsonl` sha256 `cbd340e8f50f8eed4ac520e0337ab3cad17d070df0b8b406029ad21f7900d0a0`
- `fixtures/viewer-v0/sources/fixture-23/bundle/manifest.json` sha256 `526c6f9aedc29547b5590a67ffdc72e58fd142d249a6980dd96acff2848cd5b9`
- `fixtures/viewer-v0/sources/fixture-23/bundle/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## fixture-10
- source_kind: privacy counterexample
- `fixtures/viewer-v0/sources/fixture-10/battle.log` sha256 `14f5217bf1d0dd420e79d7d5fec6dbe5a9e850d0d1f6f49a315698c1c7c342f6`
- `fixtures/viewer-v0/sources/fixture-10/results.jsonl` sha256 `914f9d3e644886f07592e2e83c4adbc160ba096b756fe78b16e93f1842962933`

## fixture-16
- source_kind: smoke team-preview empty candidates
- `fixtures/viewer-v0/sources/fixture-16/decision_trace.jsonl` sha256 `7070338b77425621b6c3720e1f5cea651dff832dc6a0a8884de047c6647ff197`
- `fixtures/viewer-v0/sources/fixture-16/results.config-manifest.json` sha256 `c953a619529338c8b3ed26d68042b5ee1a4de4323b94bba3324b847f408b70c7`
- `fixtures/viewer-v0/sources/fixture-16/results.jsonl` sha256 `f4da66b80d700343998da818cc3c89aa239fb8b3c3ecbd214930f209c8bd7cb0`
- `fixtures/viewer-v0/sources/fixture-16/results.manifest.json` sha256 `1224ceac19eb7fa97e0b32bb844b9e95a9aa3eb97de2f1387c5a8a00a1cdf957`

## bundle/fixture-01
- `fixtures/viewer-v0/bundles/fixture-01/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/bundles/fixture-01/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/bundles/fixture-01/decisions.jsonl` sha256 `cbd340e8f50f8eed4ac520e0337ab3cad17d070df0b8b406029ad21f7900d0a0`
- `fixtures/viewer-v0/bundles/fixture-01/manifest.json` sha256 `c42b843880a09fd88aa9a712d8e51f4ac46223e15e616bc02f30db9371d6d369`
- `fixtures/viewer-v0/bundles/fixture-01/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## bundle/fixture-03
- `fixtures/viewer-v0/bundles/fixture-03/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/bundles/fixture-03/config-manifest.json` sha256 `e7fb6903633c5cbc653d25e4f1ed2ce24219ed6774a304292b3f0131d34900ce`
- `fixtures/viewer-v0/bundles/fixture-03/decisions.jsonl` sha256 `d66f0f329ce6ac63461afced801a445fc5a177a9240d317983c579e88c1ac70a`
- `fixtures/viewer-v0/bundles/fixture-03/manifest.json` sha256 `86d170965232bccc03f05b154205b738551198efa5ca298c164d59133af5a644`
- `fixtures/viewer-v0/bundles/fixture-03/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## bundle/fixture-04
- `fixtures/viewer-v0/bundles/fixture-04/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/bundles/fixture-04/config-manifest.json` sha256 `87df009d9c2b35b553712885dfa66bc15f403c4551a9a6d7283ed6e36d08e27a`
- `fixtures/viewer-v0/bundles/fixture-04/manifest.json` sha256 `bae11441412c6cb0205fa449d53cd17393e75bbc9b8579c3d802ceade13d02cc`

## bundle/fixture-05
- `fixtures/viewer-v0/bundles/fixture-05/config-manifest.json` sha256 `0067979d71e64b781b41895489ff05730790bbffd746695869ed40caa85172eb`
- `fixtures/viewer-v0/bundles/fixture-05/decisions.jsonl` sha256 `2523603f04deb59de8e30295a5a15586e122f7a2c4742b98e4b19a422e580784`
- `fixtures/viewer-v0/bundles/fixture-05/manifest.json` sha256 `4ecc71685848fed65a45f4e3ac0926c8ec6dab2056216d0f047d11aeda20c8d5`
- `fixtures/viewer-v0/bundles/fixture-05/warnings.json` sha256 `2a1e15bb8e71a2f7ed99f6a7774081207e9e496b4b6406ed0e2778eebdea0155`

## bundle/fixture-10
- `fixtures/viewer-v0/bundles/fixture-10/battle.jsonl` sha256 `31c6becbc52c8b26a4eea32c3291e4991d50a9677426625b36c73f3095fa53a9`
- `fixtures/viewer-v0/bundles/fixture-10/manifest.json` sha256 `44dbb49c843396ba75fb0712bb1c4ef55aa20c9fb2b5bb29bbb0cde41e33f1fa`

## bundle/fixture-16
- `fixtures/viewer-v0/bundles/fixture-16/config-manifest.json` sha256 `0067979d71e64b781b41895489ff05730790bbffd746695869ed40caa85172eb`
- `fixtures/viewer-v0/bundles/fixture-16/decisions.jsonl` sha256 `2523603f04deb59de8e30295a5a15586e122f7a2c4742b98e4b19a422e580784`
- `fixtures/viewer-v0/bundles/fixture-16/manifest.json` sha256 `4ecc71685848fed65a45f4e3ac0926c8ec6dab2056216d0f047d11aeda20c8d5`
- `fixtures/viewer-v0/bundles/fixture-16/warnings.json` sha256 `2a1e15bb8e71a2f7ed99f6a7774081207e9e496b4b6406ed0e2778eebdea0155`

## bundle/fixture-19
- produced by a real `export_bundle()` call against `sources/fixture-19/` (battle_log +
  decision_trace, no results/config-manifest); fixture 19 exports cleanly (not a refuse
  fixture), so this is the actual exporter output, not a hand-mutated manifest
- `fixtures/viewer-v0/bundles/fixture-19/battle.jsonl` sha256 `0083247f928417764d3fa4962f5dc2cee5f7537aea62c9f54e65b8e6496aa070`
- `fixtures/viewer-v0/bundles/fixture-19/decisions.jsonl` sha256 `8b644676a28b8e7800d8d4f96983f728599df7306f9201c60d96b43de1216e42`
- `fixtures/viewer-v0/bundles/fixture-19/manifest.json` sha256 `43ca63c9d8c5f9b9a307b6b5bffb80a28e168455ebd3c7c9a21182799497cd8f`
- `fixtures/viewer-v0/bundles/fixture-19/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`
