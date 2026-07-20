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
