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

## fixture-02
- source_kind: close decision / margin (fixture-01's three rows, one candidate score mutated)
- note: fixture-01/decision_trace.jsonl's three rows unchanged except row 2 (decision_index 2):
  its second candidate ("pass", rank 1) aggregate_score changed 0.5 -> 3.487, so the top two
  candidates (3.5, 3.487) are 0.013 apart -- small, non-zero, and not a round number, so a
  passing test cannot be explained by an implicit exporter cutoff. Real committed rows with a
  small top1_top2_margin already exist elsewhere in this repo (fixture-05/16's real committed
  data, itself derived from data/eval/champions-panel-v0/smoke-i7a-mega -- see the 104-candidate
  entry below), but only at large candidate counts (45/104) or as an exact tie (margin 0.0 on
  every real 2-candidate forced_replacement row sampled). Constructed instead, per §14's own
  second recipe option ("construct if none exists with a small-enough gap"), to keep the fixture
  minimal and to exercise a hand-verifiable non-zero value. Row 0 (team_preview, 0 candidates)
  and row 1 (forced_replacement, exactly 1 candidate) both exercise "fewer than two candidates"
  with two different counts, not just the zero case. Proved via
  tests/python/test_f1_fixture_catalogue.py::test_fixture02_close_decision_margin_small_correct_no_threshold
- `fixtures/viewer-v0/sources/fixture-02/decision_trace.jsonl` sha256 `d149f3ecf7861abec379604641e77126ac545012b87bd5842fcd64c0e7e79e41`

## fixture-17
- source_kind: filtered protocol lines / sparse protocol_index (replay-only, results.jsonl reused
  from fixture-01)
- note: a fresh 11-line battle.log interleaving `|player|` (line 0), `|j|` (1), `|t:|` (2),
  `|request|` (3, 7, 10), and `|c|` chat (5) -- all filtered -- with real `|turn|` (4, 8),
  `|switch|` (6), and `|move|` (9) event lines. `export_battle_jsonl`'s resulting
  `protocol_index` sequence is `[4, 6, 8, 9]`; the gap positions (`{0,1,2,3,5,7,10}`) equal
  exactly the filtered-line positions, not merely "somewhere". results.jsonl is a byte-identical
  copy of fixture-01/results.jsonl (same synthetic sentinel provenance), matching fixture-04's
  precedent for a replay-only export with no decision_trace. Proved via
  tests/python/test_f1_fixture_catalogue.py::test_fixture17_protocol_index_gaps_land_exactly_on_filtered_lines
- `fixtures/viewer-v0/sources/fixture-17/battle.log` sha256 `97f175eecbb788456f5cf8d07a8e24fafed6b569d0982cf7e92406d4c5e01501`
- `fixtures/viewer-v0/sources/fixture-17/results.jsonl` sha256 `5c12db6757eb7bada142b63efa4b3bae7fd9b2908e633cb3ca60b696329345a0`

## fixture-18
- source_kind: synthetic-coherent-v1 (`|request|` skip rules: rqid resend + req.wait)
- battle_id: synthetic00000001 (reused sentinel, same as fixture-01 -- §14.1 condition 3: not a
  real `data/eval/` battle_id, so reuse is not a false producer claim)
- git_sha: unknown (§14.1 condition 4)
- note: a fresh 7-line battle.log with an `rqid=1` request (line 0), a verbatim resend of the
  same `rqid=1` payload (line 2, skipped by the resend rule), an `rqid=2, wait:true` request
  (line 3, skipped by the wait rule), and a surviving `rqid=3` request (line 5) --
  `index_requests_from_log` keeps exactly the two surviving requests (protocol_index 0 and 5).
  decision_trace.jsonl has two rows (fixture-01's own row 0 verbatim -- its request_hash already
  equals the hash of the line-0 payload used here unchanged -- and fixture-01's row 2 reused with
  decision_index/turn_number/request_hash/state_summary updated to match the line-5 payload), so
  both requests join to a real decision (`request_protocol_index` 0 and 5 in the exported
  bundle, neither null) -- internal coherence per §14.1 condition 2. §15 gate 35 (this fixture's
  own gate) is already directly proved by
  tests/python/test_a5_battle_join.py::test_request_skip_rules (Rev. 5 gate-coverage audit:
  "materially stronger than 'new' implies"); no duplicate test is added here, only the catalogue
  directory
- `fixtures/viewer-v0/sources/fixture-18/battle.log` sha256 `2fd8e17a2bd85c55149274c42ab9871f15caace376a132e2c95301b6facafd9f`
- `fixtures/viewer-v0/sources/fixture-18/decision_trace.jsonl` sha256 `2897e71366b42a96ff18f5ca2d4c5c41b5220130d9b7002db1cbe15401cb8373`

## 104-candidate bounded-render (cross-cutting rule 7, index §5; §0.11 Choice Point 3, CLOSED: L1)
- not a numbered §14 fixture; no new directory added under this entry -- **already satisfied**
  by the pre-existing `sources/fixture-16` / `bundles/fixture-16` (Plan A, unmodified by Plan F)
- derivation confirmed: `sources/fixture-16/decision_trace.jsonl` (sha256
  `7070338b77425621b6c3720e1f5cea651dff832dc6a0a8884de047c6647ff197`, same file as
  `sources/fixture-05/decision_trace.jsonl`) is byte-identical
  (`546693fc6e5d3efeeb69f673c4aa270524c0ef639f0fbff861b8b23d5a1a146f`, standard 64-hex sha256,
  computed directly) to the real committed
  `data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl` -- confirmed with a direct
  `sha256sum` comparison of both files, 2026-07-24. Per-row candidate counts, enumerated
  directly: `[0, 104, 45, 45, 2, 41, 41, 2, 5, 5, 5, 0, 104, 45, 45, 2, 41, 41, 1, 25]`, matching
  bundle contract §2.5's own citation exactly; decision_index 1 (first battle) carries 104
  candidates, and `bundles/fixture-16/decisions.jsonl` (already committed) carries that same
  104-candidate row through export un-truncated
- proof, Godot side (rendering bound): `godot/tests/decision/test_candidate_table_view.gd::test_table_bounded_104_candidates`
  opens `bundles/fixture-16`, finds the 104-candidate row, binds it to `CandidateTableView`, and
  asserts `get_item_count() == 104` -- already existing, already passing, not added by this batch
- proof, Python side (export does not truncate first, new this batch):
  tests/python/test_f1_fixture_catalogue.py::test_fixture16_104_candidate_row_export_not_truncated
- **known gap (accepted by owner, §0.11 Choice Point 3 / §1 fixture matrix), preserved here**:
  the `smoke-i7a-mega` corpus directory has no companion battle log, so `fixture-16` is
  `TRACE_ONLY` -- bounded rendering is never exercised together with active replay mode by this
  fixture. A defect only reproducible with board + timeline + a live 104-row candidate table
  simultaneously would not be caught here

## bundle/fixture-02
- produced by a real `export_bundle()` call against `sources/fixture-02/decision_trace.jsonl`
  (TRACE_ONLY, no battle_log); fixture 2 exports cleanly (not a refuse fixture), so this is the
  actual exporter output
- `fixtures/viewer-v0/bundles/fixture-02/decisions.jsonl` sha256 `96d17baf4d095dd205f041d44d0703bf761966ba1db9a7c1bf8682e8286fcfcb`
- `fixtures/viewer-v0/bundles/fixture-02/manifest.json` sha256 `c3b23a68d5229c462e2dcf8f0186082c643c63d19924cda366ee60282fabf881`
- `fixtures/viewer-v0/bundles/fixture-02/warnings.json` sha256 `26860e028a1bae69336c966b7b1dcc1e7bce679796fd4e367228fda1c848ceb1`

## bundle/fixture-17
- produced by a real `export_bundle()` call against `sources/fixture-17/` (battle_log + results,
  no decision_trace -- replay-only, same mode as bundle/fixture-04); fixture 17 exports cleanly
- `fixtures/viewer-v0/bundles/fixture-17/battle.jsonl` sha256 `ff79b8a7ebda06ebe1b72732b3083f5259cd5dd64aab609ce3cfcbef99741add`
- `fixtures/viewer-v0/bundles/fixture-17/manifest.json` sha256 `0570383090e77d98c58b7005f7b51843133d29c440dcf4f7b27a905645f40da4`

## bundle/fixture-18
- produced by a real `export_bundle()` call against `sources/fixture-18/` (battle_log +
  decision_trace, no results/config-manifest); fixture 18 exports cleanly. `decisions.jsonl`'s
  two rows both carry a non-null `request_protocol_index` (0 and 5), confirming the surviving
  joins resolve
- `fixtures/viewer-v0/bundles/fixture-18/battle.jsonl` sha256 `9f2b330e6bcbad24c19924a9a9abdfd4cc0c1518b1ecb2743164db0478361d7b`
- `fixtures/viewer-v0/bundles/fixture-18/decisions.jsonl` sha256 `07da4f9b91ed1ac4d4a35fdc29ffdc9ba66fc138b70e3f9b21112c13e47ed855`
- `fixtures/viewer-v0/bundles/fixture-18/manifest.json` sha256 `6c7d098d324e76f46790f805c592dc24aad1992b7374fe12c1c3991fdc9f5c62`
- `fixtures/viewer-v0/bundles/fixture-18/warnings.json` sha256 `44ceb752d7a26dd6b9091035975b12c12d667a752f1794a0523c51f2755c85eb`
