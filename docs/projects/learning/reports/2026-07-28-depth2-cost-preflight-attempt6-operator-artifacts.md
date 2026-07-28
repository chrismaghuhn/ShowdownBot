# Depth-2 Cost Preflight — Attempt 6 Operator Artifacts

**Companion to:** `2026-07-28-depth2-cost-preflight-attempt6-freeze.md`
**Date:** 2026-07-28

This document freezes the operator scripts that executed Attempt 6, so a later reviewer can
reproduce and audit the operator and validation steps rather than take the freeze report's
word for them.

## Provenance of these scripts — read before relying on them

These are **operator scripts, not production code.** They live outside the repository, in
the session scratchpad, and were never part of the candidate worktree — all four run
manifests report `dirty = false`, and the candidate tree at `d64982a` is unmodified.

**What the hashes below are, precisely:** they are the SHA-256 of bytes **currently present
in the session scratchpad**, which the operator states are the scripts that executed. File
modification times are consistent with the run chronology and support that account. **Their
run-time identity was not cryptographically pinned during the run** — the hashes were
computed while authoring this freeze, not recorded into `operator-preflight.json` or any
other run-time artifact, and no contemporaneous log captured them. A later reviewer should
treat them as operator-attested, chronology-supported, and **not** as run-time-sealed.

This is a real gap in the freeze, stated rather than papered over. Pinning operator-script
hashes into `operator-preflight.json` is the obvious closure for a future attempt.

## Encoding — how to verify

Each script appears twice:

- a **readable code block** for review, and
- a **Base64 block of the raw bytes**, which is authoritative.

Verify against Base64, not the code block. The code block is line-normalised by Markdown
rendering and does not reliably reproduce the hash: `preflight6.py` in particular ends with
the three bytes `0A 0D 0A` (LF CR LF), and the lone CR does not survive ordinary line
extraction. An earlier revision of this document claimed all contents were byte-exact; that
was wrong for that file, which is why the Base64 blocks exist.

To check a script:

```bash
python -c "import base64,hashlib,sys; b=base64.b64decode(open(sys.argv[1]).read()); print(hashlib.sha256(b).hexdigest())" b64.txt
```

## Inventory

| Script | Lines | Raw bytes | SHA-256 of raw bytes |
|---|---:|---:|---|
| `preflight6.py` | 97 | 4311 | `9cda144b107161410f312d96bfbb82238bf8d158bcc4eaf93923356979e44c1a` |
| `run_arm.ps1` | 104 | 4522 | `be06d2b60a5389b667839a85593b6edcdf639c36984fb6c65511443e130f7bb5` |
| `verify_arm6.py` | 126 | 5268 | `1ad35d8acf24606f4a6464af54916ad8d1fe7600375725749c0ab726adc30439` |
| `post_arm6.py` | 120 | 5278 | `1f076b8c1fc082a226f02910afeef6633657dd2250eac0762cbebb2523c80a6b` |
| `cross_arm6.py` | 108 | 4545 | `1e576544e5f802c2050012878e3d7e3e025d7ecdafb6234df2b8fca36cf76c8b` |
| `evidence6.py` | 66 | 3781 | `a1f896c8a7c202e671b216a8c6703b524af40dd9f01e37de4ea5004c8593af05` |


---

## `preflight6.py`

Writes `operator-preflight.json`. Run once before arm 1, after `npm ci`.

Raw bytes: 4311 &middot; SHA-256 `9cda144b107161410f312d96bfbb82238bf8d158bcc4eaf93923356979e44c1a`

### Readable form (line-normalised — not authoritative)

```python
﻿import hashlib, json, os, subprocess, sys
import showdown_bot
import showdown_bot.cli

CAND = r"C:\Users\chris\Documents\cost-preflight-worktree-d64982a"
OUT = r"C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt6"
SERVER_DIR = os.path.expanduser(r"~\.cache\showdownbot\pokemon-showdown")

sb = os.path.normpath(str(showdown_bot.__file__ or ""))
cl = os.path.normpath(str(showdown_bot.cli.__file__ or ""))
if CAND.lower() not in sb.lower() or CAND.lower() not in cl.lower():
    sys.exit("IMPORT ROOT FAIL: %s | %s" % (sb, cl))

node_ver = subprocess.check_output("node --version", shell=True).decode().strip()
npm_ver = subprocess.check_output("npm --version", shell=True).decode().strip()

lock = os.path.join(CAND, "showdown_bot", "tools", "calc", "package-lock.json")
calc_lock = hashlib.sha256(open(lock, "rb").read()).hexdigest()

head = subprocess.check_output(["git", "-C", CAND, "rev-parse", "HEAD"]).decode().strip()
dirty = subprocess.check_output(["git", "-C", CAND, "status", "--porcelain"]).decode().strip()

sd_head = subprocess.check_output(["git", "-C", SERVER_DIR, "rev-parse", "HEAD"]).decode().strip()
sd_diff = subprocess.check_output(["git", "-C", SERVER_DIR, "diff", "HEAD"]).decode()
sd_diff_hash = hashlib.sha1(sd_diff.encode()).hexdigest()[:16]

prov_path = os.path.join(CAND, "config", "eval", "provenance.yaml")
prov_commit = None
for line in open(prov_path, encoding="utf-8"):
    stripped = line.strip()
    if stripped.startswith("#") or ":" not in stripped:
        continue
    key, val = stripped.split(":", 1)
    if key.strip() == "showdown_commit":
        prov_commit = val.strip().strip('"').strip("'")
        break

patch_path = os.path.join(CAND, "tools", "eval", "patches", "pokemon-showdown-seeded-battle.patch")
patch_hash = hashlib.sha1(open(patch_path, "rb").read()).hexdigest()[:16]

rec = {
    "attempt": 6,
    "arms_order": ["d1_acc_off", "d1_acc_on", "d2_acc_off", "d2_acc_on"],
    "candidate_sha": head,
    "candidate_dirty": bool(dirty),
    "output_root": OUT,
    "pythonpath": os.environ["PYTHONPATH"],
    "showdown_bot_file": sb,
    "showdown_bot_cli_file": cl,
    "import_root_verified": True,
    "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
    "server_dir": os.path.normpath(SERVER_DIR),
    "server_dir_head": sd_head,
    "server_dir_diff_hash": sd_diff_hash,
    "provenance_yaml_commit": prov_commit,
    "patch_file_hash": patch_hash,
    "head_matches_provenance": sd_head == prov_commit,
    "diff_matches_patch": sd_diff_hash == patch_hash,
    "server_start_command": "node pokemon-showdown start --no-security",
    "server_port": 8000,
    "server_ws_endpoint": "ws://localhost:8000/showdown/websocket",
    "schedule_yaml": r"C:\Users\chris\Documents\SHowdown BOt\config\eval\schedules\cost_preflight_d2_30.yaml",
    "schedule_hash": "b6f5910e4bc3c584",
    "panel_hash": "aac1ea30446fde88",
    "seed_base": "champions-panel-v0-d2-cost-preflight",
    "battle_timeout_s": "unset (effective 180)",
    "node_version": node_ver,
    "npm_version": npm_ver,
    "calc_lockfile_sha256": calc_lock,
    "calc_deps_installed": True,
}

for k in ("candidate_dirty",):
    if rec[k]:
        sys.exit("FAIL: candidate dirty")
for k in ("head_matches_provenance", "diff_matches_patch", "import_root_verified"):
    if not rec[k]:
        sys.exit("FAIL: %s is False" % k)
if rec["candidate_sha"] != "d64982ae9fdba6a877c8c2b7e804923ebcc7fec4":
    sys.exit("FAIL: candidate sha %s" % rec["candidate_sha"])
if rec["pythonhashseed"] != "0":
    sys.exit("FAIL: pythonhashseed %r" % rec["pythonhashseed"])
if rec["calc_lockfile_sha256"] != "c03c577c3e62c7c1de12ba74ac60ca311bf3dd077e37e09c30d5269f2b61dabe":
    sys.exit("FAIL: calc lockfile %s" % rec["calc_lockfile_sha256"])

path = os.path.join(OUT, "operator-preflight.json")
if os.path.exists(path):
    sys.exit("FAIL: operator-preflight.json already exists")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(rec, fh, indent=2, sort_keys=True)

for k in ("candidate_sha", "candidate_dirty", "import_root_verified", "head_matches_provenance",
          "diff_matches_patch", "node_version", "npm_version", "calc_lockfile_sha256",
          "pythonhashseed", "showdown_bot_file"):
    print("%s = %s" % (k, rec[k]))
print("operator-preflight.json WRITTEN")

```

### Raw bytes, Base64 (authoritative)

```text
77u/aW1wb3J0IGhhc2hsaWIsIGpzb24sIG9zLCBzdWJwcm9jZXNzLCBzeXMKaW1wb3J0IHNob3dkb3duX2JvdAppbXBvcnQgc2hv
d2Rvd25fYm90LmNsaQoKQ0FORCA9IHIiQzpcVXNlcnNcY2hyaXNcRG9jdW1lbnRzXGNvc3QtcHJlZmxpZ2h0LXdvcmt0cmVlLWQ2
NDk4MmEiCk9VVCA9IHIiQzpcVXNlcnNcY2hyaXNcRG9jdW1lbnRzXGNvc3QtcHJlZmxpZ2h0LWQyLWQ2NDk4MmEtYXR0ZW1wdDYi
ClNFUlZFUl9ESVIgPSBvcy5wYXRoLmV4cGFuZHVzZXIociJ+XC5jYWNoZVxzaG93ZG93bmJvdFxwb2tlbW9uLXNob3dkb3duIikK
CnNiID0gb3MucGF0aC5ub3JtcGF0aChzdHIoc2hvd2Rvd25fYm90Ll9fZmlsZV9fIG9yICIiKSkKY2wgPSBvcy5wYXRoLm5vcm1w
YXRoKHN0cihzaG93ZG93bl9ib3QuY2xpLl9fZmlsZV9fIG9yICIiKSkKaWYgQ0FORC5sb3dlcigpIG5vdCBpbiBzYi5sb3dlcigp
IG9yIENBTkQubG93ZXIoKSBub3QgaW4gY2wubG93ZXIoKToKICAgIHN5cy5leGl0KCJJTVBPUlQgUk9PVCBGQUlMOiAlcyB8ICVz
IiAlIChzYiwgY2wpKQoKbm9kZV92ZXIgPSBzdWJwcm9jZXNzLmNoZWNrX291dHB1dCgibm9kZSAtLXZlcnNpb24iLCBzaGVsbD1U
cnVlKS5kZWNvZGUoKS5zdHJpcCgpCm5wbV92ZXIgPSBzdWJwcm9jZXNzLmNoZWNrX291dHB1dCgibnBtIC0tdmVyc2lvbiIsIHNo
ZWxsPVRydWUpLmRlY29kZSgpLnN0cmlwKCkKCmxvY2sgPSBvcy5wYXRoLmpvaW4oQ0FORCwgInNob3dkb3duX2JvdCIsICJ0b29s
cyIsICJjYWxjIiwgInBhY2thZ2UtbG9jay5qc29uIikKY2FsY19sb2NrID0gaGFzaGxpYi5zaGEyNTYob3Blbihsb2NrLCAicmIi
KS5yZWFkKCkpLmhleGRpZ2VzdCgpCgpoZWFkID0gc3VicHJvY2Vzcy5jaGVja19vdXRwdXQoWyJnaXQiLCAiLUMiLCBDQU5ELCAi
cmV2LXBhcnNlIiwgIkhFQUQiXSkuZGVjb2RlKCkuc3RyaXAoKQpkaXJ0eSA9IHN1YnByb2Nlc3MuY2hlY2tfb3V0cHV0KFsiZ2l0
IiwgIi1DIiwgQ0FORCwgInN0YXR1cyIsICItLXBvcmNlbGFpbiJdKS5kZWNvZGUoKS5zdHJpcCgpCgpzZF9oZWFkID0gc3VicHJv
Y2Vzcy5jaGVja19vdXRwdXQoWyJnaXQiLCAiLUMiLCBTRVJWRVJfRElSLCAicmV2LXBhcnNlIiwgIkhFQUQiXSkuZGVjb2RlKCku
c3RyaXAoKQpzZF9kaWZmID0gc3VicHJvY2Vzcy5jaGVja19vdXRwdXQoWyJnaXQiLCAiLUMiLCBTRVJWRVJfRElSLCAiZGlmZiIs
ICJIRUFEIl0pLmRlY29kZSgpCnNkX2RpZmZfaGFzaCA9IGhhc2hsaWIuc2hhMShzZF9kaWZmLmVuY29kZSgpKS5oZXhkaWdlc3Qo
KVs6MTZdCgpwcm92X3BhdGggPSBvcy5wYXRoLmpvaW4oQ0FORCwgImNvbmZpZyIsICJldmFsIiwgInByb3ZlbmFuY2UueWFtbCIp
CnByb3ZfY29tbWl0ID0gTm9uZQpmb3IgbGluZSBpbiBvcGVuKHByb3ZfcGF0aCwgZW5jb2Rpbmc9InV0Zi04Iik6CiAgICBzdHJp
cHBlZCA9IGxpbmUuc3RyaXAoKQogICAgaWYgc3RyaXBwZWQuc3RhcnRzd2l0aCgiIyIpIG9yICI6IiBub3QgaW4gc3RyaXBwZWQ6
CiAgICAgICAgY29udGludWUKICAgIGtleSwgdmFsID0gc3RyaXBwZWQuc3BsaXQoIjoiLCAxKQogICAgaWYga2V5LnN0cmlwKCkg
PT0gInNob3dkb3duX2NvbW1pdCI6CiAgICAgICAgcHJvdl9jb21taXQgPSB2YWwuc3RyaXAoKS5zdHJpcCgnIicpLnN0cmlwKCIn
IikKICAgICAgICBicmVhawoKcGF0Y2hfcGF0aCA9IG9zLnBhdGguam9pbihDQU5ELCAidG9vbHMiLCAiZXZhbCIsICJwYXRjaGVz
IiwgInBva2Vtb24tc2hvd2Rvd24tc2VlZGVkLWJhdHRsZS5wYXRjaCIpCnBhdGNoX2hhc2ggPSBoYXNobGliLnNoYTEob3Blbihw
YXRjaF9wYXRoLCAicmIiKS5yZWFkKCkpLmhleGRpZ2VzdCgpWzoxNl0KCnJlYyA9IHsKICAgICJhdHRlbXB0IjogNiwKICAgICJh
cm1zX29yZGVyIjogWyJkMV9hY2Nfb2ZmIiwgImQxX2FjY19vbiIsICJkMl9hY2Nfb2ZmIiwgImQyX2FjY19vbiJdLAogICAgImNh
bmRpZGF0ZV9zaGEiOiBoZWFkLAogICAgImNhbmRpZGF0ZV9kaXJ0eSI6IGJvb2woZGlydHkpLAogICAgIm91dHB1dF9yb290Ijog
T1VULAogICAgInB5dGhvbnBhdGgiOiBvcy5lbnZpcm9uWyJQWVRIT05QQVRIIl0sCiAgICAic2hvd2Rvd25fYm90X2ZpbGUiOiBz
YiwKICAgICJzaG93ZG93bl9ib3RfY2xpX2ZpbGUiOiBjbCwKICAgICJpbXBvcnRfcm9vdF92ZXJpZmllZCI6IFRydWUsCiAgICAi
cHl0aG9uaGFzaHNlZWQiOiBvcy5lbnZpcm9uLmdldCgiUFlUSE9OSEFTSFNFRUQiKSwKICAgICJzZXJ2ZXJfZGlyIjogb3MucGF0
aC5ub3JtcGF0aChTRVJWRVJfRElSKSwKICAgICJzZXJ2ZXJfZGlyX2hlYWQiOiBzZF9oZWFkLAogICAgInNlcnZlcl9kaXJfZGlm
Zl9oYXNoIjogc2RfZGlmZl9oYXNoLAogICAgInByb3ZlbmFuY2VfeWFtbF9jb21taXQiOiBwcm92X2NvbW1pdCwKICAgICJwYXRj
aF9maWxlX2hhc2giOiBwYXRjaF9oYXNoLAogICAgImhlYWRfbWF0Y2hlc19wcm92ZW5hbmNlIjogc2RfaGVhZCA9PSBwcm92X2Nv
bW1pdCwKICAgICJkaWZmX21hdGNoZXNfcGF0Y2giOiBzZF9kaWZmX2hhc2ggPT0gcGF0Y2hfaGFzaCwKICAgICJzZXJ2ZXJfc3Rh
cnRfY29tbWFuZCI6ICJub2RlIHBva2Vtb24tc2hvd2Rvd24gc3RhcnQgLS1uby1zZWN1cml0eSIsCiAgICAic2VydmVyX3BvcnQi
OiA4MDAwLAogICAgInNlcnZlcl93c19lbmRwb2ludCI6ICJ3czovL2xvY2FsaG9zdDo4MDAwL3Nob3dkb3duL3dlYnNvY2tldCIs
CiAgICAic2NoZWR1bGVfeWFtbCI6IHIiQzpcVXNlcnNcY2hyaXNcRG9jdW1lbnRzXFNIb3dkb3duIEJPdFxjb25maWdcZXZhbFxz
Y2hlZHVsZXNcY29zdF9wcmVmbGlnaHRfZDJfMzAueWFtbCIsCiAgICAic2NoZWR1bGVfaGFzaCI6ICJiNmY1OTEwZTRiYzNjNTg0
IiwKICAgICJwYW5lbF9oYXNoIjogImFhYzFlYTMwNDQ2ZmRlODgiLAogICAgInNlZWRfYmFzZSI6ICJjaGFtcGlvbnMtcGFuZWwt
djAtZDItY29zdC1wcmVmbGlnaHQiLAogICAgImJhdHRsZV90aW1lb3V0X3MiOiAidW5zZXQgKGVmZmVjdGl2ZSAxODApIiwKICAg
ICJub2RlX3ZlcnNpb24iOiBub2RlX3ZlciwKICAgICJucG1fdmVyc2lvbiI6IG5wbV92ZXIsCiAgICAiY2FsY19sb2NrZmlsZV9z
aGEyNTYiOiBjYWxjX2xvY2ssCiAgICAiY2FsY19kZXBzX2luc3RhbGxlZCI6IFRydWUsCn0KCmZvciBrIGluICgiY2FuZGlkYXRl
X2RpcnR5IiwpOgogICAgaWYgcmVjW2tdOgogICAgICAgIHN5cy5leGl0KCJGQUlMOiBjYW5kaWRhdGUgZGlydHkiKQpmb3IgayBp
biAoImhlYWRfbWF0Y2hlc19wcm92ZW5hbmNlIiwgImRpZmZfbWF0Y2hlc19wYXRjaCIsICJpbXBvcnRfcm9vdF92ZXJpZmllZCIp
OgogICAgaWYgbm90IHJlY1trXToKICAgICAgICBzeXMuZXhpdCgiRkFJTDogJXMgaXMgRmFsc2UiICUgaykKaWYgcmVjWyJjYW5k
aWRhdGVfc2hhIl0gIT0gImQ2NDk4MmFlOWZkYmE2YTg3N2M4YzJiN2U4MDQ5MjNlYmNjN2ZlYzQiOgogICAgc3lzLmV4aXQoIkZB
SUw6IGNhbmRpZGF0ZSBzaGEgJXMiICUgcmVjWyJjYW5kaWRhdGVfc2hhIl0pCmlmIHJlY1sicHl0aG9uaGFzaHNlZWQiXSAhPSAi
MCI6CiAgICBzeXMuZXhpdCgiRkFJTDogcHl0aG9uaGFzaHNlZWQgJXIiICUgcmVjWyJweXRob25oYXNoc2VlZCJdKQppZiByZWNb
ImNhbGNfbG9ja2ZpbGVfc2hhMjU2Il0gIT0gImMwM2M1NzdjM2U2MmM3YzFkZTEyYmE3NGFjNjBjYTMxMWJmM2RkMDc3ZTM3ZTA5
YzMwZDUyNjlmMmI2MWRhYmUiOgogICAgc3lzLmV4aXQoIkZBSUw6IGNhbGMgbG9ja2ZpbGUgJXMiICUgcmVjWyJjYWxjX2xvY2tm
aWxlX3NoYTI1NiJdKQoKcGF0aCA9IG9zLnBhdGguam9pbihPVVQsICJvcGVyYXRvci1wcmVmbGlnaHQuanNvbiIpCmlmIG9zLnBh
dGguZXhpc3RzKHBhdGgpOgogICAgc3lzLmV4aXQoIkZBSUw6IG9wZXJhdG9yLXByZWZsaWdodC5qc29uIGFscmVhZHkgZXhpc3Rz
IikKd2l0aCBvcGVuKHBhdGgsICJ3IiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZmg6CiAgICBqc29uLmR1bXAocmVjLCBmaCwgaW5k
ZW50PTIsIHNvcnRfa2V5cz1UcnVlKQoKZm9yIGsgaW4gKCJjYW5kaWRhdGVfc2hhIiwgImNhbmRpZGF0ZV9kaXJ0eSIsICJpbXBv
cnRfcm9vdF92ZXJpZmllZCIsICJoZWFkX21hdGNoZXNfcHJvdmVuYW5jZSIsCiAgICAgICAgICAiZGlmZl9tYXRjaGVzX3BhdGNo
IiwgIm5vZGVfdmVyc2lvbiIsICJucG1fdmVyc2lvbiIsICJjYWxjX2xvY2tmaWxlX3NoYTI1NiIsCiAgICAgICAgICAicHl0aG9u
aGFzaHNlZWQiLCAic2hvd2Rvd25fYm90X2ZpbGUiKToKICAgIHByaW50KCIlcyA9ICVzIiAlIChrLCByZWNba10pKQpwcmludCgi
b3BlcmF0b3ItcHJlZmxpZ2h0Lmpzb24gV1JJVFRFTiIpCg0K
```

---

## `run_arm.ps1`

The arm block. One PowerShell process per arm: clears and sets the environment, starts the server, runs the pre-arm gate as the first Python child, then the gauntlet as the second.

Raw bytes: 4522 &middot; SHA-256 `be06d2b60a5389b667839a85593b6edcdf639c36984fb6c65511443e130f7bb5`

### Readable form (line-normalised — not authoritative)

```powershell
param(
  [Parameter(Mandatory=$true)][string]$Arm,
  [Parameter(Mandatory=$true)][int]$Depth,
  [Parameter(Mandatory=$true)][string]$AccMode,
  [string]$Cap = "",
  [string]$TopN = "",
  [string]$TopM = "",
  [int]$PrevPid = 0
)
$ErrorActionPreference = "Stop"

$OUT     = "C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt6"
$CAND    = "C:\Users\chris\Documents\cost-preflight-worktree-d64982a"
$SRVDIR  = "C:\Users\chris\.cache\showdownbot\pokemon-showdown"
$SCHED   = "C:\Users\chris\Documents\SHowdown BOt\config\eval\schedules\cost_preflight_d2_30.yaml"
$SCRATCH = "C:\Users\chris\AppData\Local\Temp\claude\C--Users-chris-Documents-SHowdown-BOt\454f756a-a892-4cf8-b319-a66fe2d26fa6\scratchpad"

Write-Output "=== ARM $Arm ==="

# 1. previous server + calc backend down, port free
$prevStopped = $null
if ($PrevPid -gt 0) {
  $pp = Get-Process -Id $PrevPid -ErrorAction SilentlyContinue
  if ($pp) { Stop-Process -Id $PrevPid -Force; Start-Sleep -Milliseconds 1500 }
  $prevStopped = (-not (Get-Process -Id $PrevPid -ErrorAction SilentlyContinue))
  if (-not $prevStopped) { throw "previous server $PrevPid still running" }
}
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | ForEach-Object {
  if ($_.CommandLine -and ($_.CommandLine -match 'calc_service|tools[\/]calc')) {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
$listen = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listen) { throw "port 8000 occupied by $($listen.OwningProcess -join ',')" }
Write-Output "port 8000 free; previous_stopped=$prevStopped"

# 2. clear then assign the complete environment
Get-ChildItem Env: | Where-Object { $_.Name -like 'SHOWDOWN_*' } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
$seedlog = Join-Path $OUT "cost_preflight_${Arm}_seedlog.jsonl"
$seedAbsent = (-not (Test-Path $seedlog))

$env:PYTHONPATH                   = "$CAND\showdown_bot\src"
$env:PYTHONHASHSEED               = "0"
$env:SHOWDOWN_CALC_BACKEND        = "persistent"
$env:SHOWDOWN_DECISION_PROFILE_OUT= Join-Path $OUT "cost_preflight_${Arm}_profile.jsonl"
$env:SHOWDOWN_BATTLE_SEED_BASE    = "champions-panel-v0-d2-cost-preflight"
$env:SHOWDOWN_EVAL_SEED_LOG       = $seedlog
$env:SHOWDOWN_SEARCH_DEPTH        = "$Depth"
$env:SHOWDOWN_ACCURACY_MODE       = $AccMode
if ($Cap  -ne "") { $env:SHOWDOWN_ACCURACY_BRANCH_CAP = $Cap }
if ($TopN -ne "") { $env:SHOWDOWN_SEARCH_TOPN = $TopN }
if ($TopM -ne "") { $env:SHOWDOWN_SEARCH_TOPM = $TopM }
if (Test-Path Env:SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S) { throw "timeout var must be unset" }

# 3. server as a child of THIS process
$srv = Start-Process -FilePath "node" -ArgumentList "pokemon-showdown","start","--no-security" `
       -WorkingDirectory $SRVDIR -PassThru -WindowStyle Hidden
$utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$deadline = (Get-Date).AddSeconds(60)
do {
  Start-Sleep -Milliseconds 700
  $up = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
} while (-not $up -and (Get-Date) -lt $deadline)
if (-not $up) { Stop-Process -Id $srv.Id -Force; throw "server did not bind port 8000" }
Write-Output "server pid=$($srv.Id) listening"

$life = @{
  arm_id = $Arm; server_pid = $srv.Id
  previous_server_pid = $(if ($PrevPid -gt 0) { $PrevPid } else { $null })
  previous_server_stopped = $prevStopped
  port_free_before_start = $true
  server_start_command = "node pokemon-showdown start --no-security"
  seed_log_path = $seedlog
  seed_log_absent_or_empty_before_start = $seedAbsent
  utc_start_time = $utc
  schedule_yaml = $SCHED
}
$lifePath = Join-Path $SCRATCH "life6_$Arm.json"
$life | ConvertTo-Json | Out-File -FilePath $lifePath -Encoding utf8

Set-Location "$CAND\showdown_bot"

# 4. FIRST python child: pre-arm gate
python "$SCRATCH\verify_arm6.py" $Arm $lifePath
$gate = $LASTEXITCODE
if ($gate -ne 0) {
  Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
  Write-Output "PRE-ARM GATE FAILED (exit $gate) - server stopped, attempt over"
  exit 2
}

# 5. no environment mutation between the two children

# 6. SECOND python child: the gauntlet
$resultOut = Join-Path $OUT "cost_preflight_${Arm}_result.jsonl"
python -m showdown_bot.cli gauntlet --schedule $SCHED --result-out $resultOut
$g = $LASTEXITCODE
Write-Output "GAUNTLET EXIT: $g"

Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 1200
Write-Output "server $($srv.Id) stopped"
if ($g -ne 0) { exit 3 }
Write-Output "ARM $Arm COMPLETE"
```

### Raw bytes, Base64 (authoritative)

```text
cGFyYW0oCiAgW1BhcmFtZXRlcihNYW5kYXRvcnk9JHRydWUpXVtzdHJpbmddJEFybSwKICBbUGFyYW1ldGVyKE1hbmRhdG9yeT0k
dHJ1ZSldW2ludF0kRGVwdGgsCiAgW1BhcmFtZXRlcihNYW5kYXRvcnk9JHRydWUpXVtzdHJpbmddJEFjY01vZGUsCiAgW3N0cmlu
Z10kQ2FwID0gIiIsCiAgW3N0cmluZ10kVG9wTiA9ICIiLAogIFtzdHJpbmddJFRvcE0gPSAiIiwKICBbaW50XSRQcmV2UGlkID0g
MAopCiRFcnJvckFjdGlvblByZWZlcmVuY2UgPSAiU3RvcCIKCiRPVVQgICAgID0gIkM6XFVzZXJzXGNocmlzXERvY3VtZW50c1xj
b3N0LXByZWZsaWdodC1kMi1kNjQ5ODJhLWF0dGVtcHQ2IgokQ0FORCAgICA9ICJDOlxVc2Vyc1xjaHJpc1xEb2N1bWVudHNcY29z
dC1wcmVmbGlnaHQtd29ya3RyZWUtZDY0OTgyYSIKJFNSVkRJUiAgPSAiQzpcVXNlcnNcY2hyaXNcLmNhY2hlXHNob3dkb3duYm90
XHBva2Vtb24tc2hvd2Rvd24iCiRTQ0hFRCAgID0gIkM6XFVzZXJzXGNocmlzXERvY3VtZW50c1xTSG93ZG93biBCT3RcY29uZmln
XGV2YWxcc2NoZWR1bGVzXGNvc3RfcHJlZmxpZ2h0X2QyXzMwLnlhbWwiCiRTQ1JBVENIID0gIkM6XFVzZXJzXGNocmlzXEFwcERh
dGFcTG9jYWxcVGVtcFxjbGF1ZGVcQy0tVXNlcnMtY2hyaXMtRG9jdW1lbnRzLVNIb3dkb3duLUJPdFw0NTRmNzU2YS1hODkyLTRj
ZjgtYjMxOS1hNjZmZTJkMjZmYTZcc2NyYXRjaHBhZCIKCldyaXRlLU91dHB1dCAiPT09IEFSTSAkQXJtID09PSIKCiMgMS4gcHJl
dmlvdXMgc2VydmVyICsgY2FsYyBiYWNrZW5kIGRvd24sIHBvcnQgZnJlZQokcHJldlN0b3BwZWQgPSAkbnVsbAppZiAoJFByZXZQ
aWQgLWd0IDApIHsKICAkcHAgPSBHZXQtUHJvY2VzcyAtSWQgJFByZXZQaWQgLUVycm9yQWN0aW9uIFNpbGVudGx5Q29udGludWUK
ICBpZiAoJHBwKSB7IFN0b3AtUHJvY2VzcyAtSWQgJFByZXZQaWQgLUZvcmNlOyBTdGFydC1TbGVlcCAtTWlsbGlzZWNvbmRzIDE1
MDAgfQogICRwcmV2U3RvcHBlZCA9ICgtbm90IChHZXQtUHJvY2VzcyAtSWQgJFByZXZQaWQgLUVycm9yQWN0aW9uIFNpbGVudGx5
Q29udGludWUpKQogIGlmICgtbm90ICRwcmV2U3RvcHBlZCkgeyB0aHJvdyAicHJldmlvdXMgc2VydmVyICRQcmV2UGlkIHN0aWxs
IHJ1bm5pbmciIH0KfQpHZXQtQ2ltSW5zdGFuY2UgV2luMzJfUHJvY2VzcyAtRmlsdGVyICJOYW1lPSdub2RlLmV4ZSciIHwgRm9y
RWFjaC1PYmplY3QgewogIGlmICgkXy5Db21tYW5kTGluZSAtYW5kICgkXy5Db21tYW5kTGluZSAtbWF0Y2ggJ2NhbGNfc2Vydmlj
ZXx0b29sc1tcL11jYWxjJykpIHsKICAgIFN0b3AtUHJvY2VzcyAtSWQgJF8uUHJvY2Vzc0lkIC1Gb3JjZSAtRXJyb3JBY3Rpb24g
U2lsZW50bHlDb250aW51ZQogIH0KfQokbGlzdGVuID0gR2V0LU5ldFRDUENvbm5lY3Rpb24gLUxvY2FsUG9ydCA4MDAwIC1TdGF0
ZSBMaXN0ZW4gLUVycm9yQWN0aW9uIFNpbGVudGx5Q29udGludWUKaWYgKCRsaXN0ZW4pIHsgdGhyb3cgInBvcnQgODAwMCBvY2N1
cGllZCBieSAkKCRsaXN0ZW4uT3duaW5nUHJvY2VzcyAtam9pbiAnLCcpIiB9CldyaXRlLU91dHB1dCAicG9ydCA4MDAwIGZyZWU7
IHByZXZpb3VzX3N0b3BwZWQ9JHByZXZTdG9wcGVkIgoKIyAyLiBjbGVhciB0aGVuIGFzc2lnbiB0aGUgY29tcGxldGUgZW52aXJv
bm1lbnQKR2V0LUNoaWxkSXRlbSBFbnY6IHwgV2hlcmUtT2JqZWN0IHsgJF8uTmFtZSAtbGlrZSAnU0hPV0RPV05fKicgfSB8IEZv
ckVhY2gtT2JqZWN0IHsgUmVtb3ZlLUl0ZW0gIkVudjokKCRfLk5hbWUpIiB9CiRzZWVkbG9nID0gSm9pbi1QYXRoICRPVVQgImNv
c3RfcHJlZmxpZ2h0XyR7QXJtfV9zZWVkbG9nLmpzb25sIgokc2VlZEFic2VudCA9ICgtbm90IChUZXN0LVBhdGggJHNlZWRsb2cp
KQoKJGVudjpQWVRIT05QQVRIICAgICAgICAgICAgICAgICAgID0gIiRDQU5EXHNob3dkb3duX2JvdFxzcmMiCiRlbnY6UFlUSE9O
SEFTSFNFRUQgICAgICAgICAgICAgICA9ICIwIgokZW52OlNIT1dET1dOX0NBTENfQkFDS0VORCAgICAgICAgPSAicGVyc2lzdGVu
dCIKJGVudjpTSE9XRE9XTl9ERUNJU0lPTl9QUk9GSUxFX09VVD0gSm9pbi1QYXRoICRPVVQgImNvc3RfcHJlZmxpZ2h0XyR7QXJt
fV9wcm9maWxlLmpzb25sIgokZW52OlNIT1dET1dOX0JBVFRMRV9TRUVEX0JBU0UgICAgPSAiY2hhbXBpb25zLXBhbmVsLXYwLWQy
LWNvc3QtcHJlZmxpZ2h0IgokZW52OlNIT1dET1dOX0VWQUxfU0VFRF9MT0cgICAgICAgPSAkc2VlZGxvZwokZW52OlNIT1dET1dO
X1NFQVJDSF9ERVBUSCAgICAgICAgPSAiJERlcHRoIgokZW52OlNIT1dET1dOX0FDQ1VSQUNZX01PREUgICAgICAgPSAkQWNjTW9k
ZQppZiAoJENhcCAgLW5lICIiKSB7ICRlbnY6U0hPV0RPV05fQUNDVVJBQ1lfQlJBTkNIX0NBUCA9ICRDYXAgfQppZiAoJFRvcE4g
LW5lICIiKSB7ICRlbnY6U0hPV0RPV05fU0VBUkNIX1RPUE4gPSAkVG9wTiB9CmlmICgkVG9wTSAtbmUgIiIpIHsgJGVudjpTSE9X
RE9XTl9TRUFSQ0hfVE9QTSA9ICRUb3BNIH0KaWYgKFRlc3QtUGF0aCBFbnY6U0hPV0RPV05fR0FVTlRMRVRfQkFUVExFX1RJTUVP
VVRfUykgeyB0aHJvdyAidGltZW91dCB2YXIgbXVzdCBiZSB1bnNldCIgfQoKIyAzLiBzZXJ2ZXIgYXMgYSBjaGlsZCBvZiBUSElT
IHByb2Nlc3MKJHNydiA9IFN0YXJ0LVByb2Nlc3MgLUZpbGVQYXRoICJub2RlIiAtQXJndW1lbnRMaXN0ICJwb2tlbW9uLXNob3dk
b3duIiwic3RhcnQiLCItLW5vLXNlY3VyaXR5IiBgCiAgICAgICAtV29ya2luZ0RpcmVjdG9yeSAkU1JWRElSIC1QYXNzVGhydSAt
V2luZG93U3R5bGUgSGlkZGVuCiR1dGMgPSBbRGF0ZVRpbWVdOjpVdGNOb3cuVG9TdHJpbmcoInl5eXktTU0tZGRUSEg6bW06c3Na
IikKJGRlYWRsaW5lID0gKEdldC1EYXRlKS5BZGRTZWNvbmRzKDYwKQpkbyB7CiAgU3RhcnQtU2xlZXAgLU1pbGxpc2Vjb25kcyA3
MDAKICAkdXAgPSBHZXQtTmV0VENQQ29ubmVjdGlvbiAtTG9jYWxQb3J0IDgwMDAgLVN0YXRlIExpc3RlbiAtRXJyb3JBY3Rpb24g
U2lsZW50bHlDb250aW51ZQp9IHdoaWxlICgtbm90ICR1cCAtYW5kIChHZXQtRGF0ZSkgLWx0ICRkZWFkbGluZSkKaWYgKC1ub3Qg
JHVwKSB7IFN0b3AtUHJvY2VzcyAtSWQgJHNydi5JZCAtRm9yY2U7IHRocm93ICJzZXJ2ZXIgZGlkIG5vdCBiaW5kIHBvcnQgODAw
MCIgfQpXcml0ZS1PdXRwdXQgInNlcnZlciBwaWQ9JCgkc3J2LklkKSBsaXN0ZW5pbmciCgokbGlmZSA9IEB7CiAgYXJtX2lkID0g
JEFybTsgc2VydmVyX3BpZCA9ICRzcnYuSWQKICBwcmV2aW91c19zZXJ2ZXJfcGlkID0gJChpZiAoJFByZXZQaWQgLWd0IDApIHsg
JFByZXZQaWQgfSBlbHNlIHsgJG51bGwgfSkKICBwcmV2aW91c19zZXJ2ZXJfc3RvcHBlZCA9ICRwcmV2U3RvcHBlZAogIHBvcnRf
ZnJlZV9iZWZvcmVfc3RhcnQgPSAkdHJ1ZQogIHNlcnZlcl9zdGFydF9jb21tYW5kID0gIm5vZGUgcG9rZW1vbi1zaG93ZG93biBz
dGFydCAtLW5vLXNlY3VyaXR5IgogIHNlZWRfbG9nX3BhdGggPSAkc2VlZGxvZwogIHNlZWRfbG9nX2Fic2VudF9vcl9lbXB0eV9i
ZWZvcmVfc3RhcnQgPSAkc2VlZEFic2VudAogIHV0Y19zdGFydF90aW1lID0gJHV0YwogIHNjaGVkdWxlX3lhbWwgPSAkU0NIRUQK
fQokbGlmZVBhdGggPSBKb2luLVBhdGggJFNDUkFUQ0ggImxpZmU2XyRBcm0uanNvbiIKJGxpZmUgfCBDb252ZXJ0VG8tSnNvbiB8
IE91dC1GaWxlIC1GaWxlUGF0aCAkbGlmZVBhdGggLUVuY29kaW5nIHV0ZjgKClNldC1Mb2NhdGlvbiAiJENBTkRcc2hvd2Rvd25f
Ym90IgoKIyA0LiBGSVJTVCBweXRob24gY2hpbGQ6IHByZS1hcm0gZ2F0ZQpweXRob24gIiRTQ1JBVENIXHZlcmlmeV9hcm02LnB5
IiAkQXJtICRsaWZlUGF0aAokZ2F0ZSA9ICRMQVNURVhJVENPREUKaWYgKCRnYXRlIC1uZSAwKSB7CiAgU3RvcC1Qcm9jZXNzIC1J
ZCAkc3J2LklkIC1Gb3JjZSAtRXJyb3JBY3Rpb24gU2lsZW50bHlDb250aW51ZQogIFdyaXRlLU91dHB1dCAiUFJFLUFSTSBHQVRF
IEZBSUxFRCAoZXhpdCAkZ2F0ZSkgLSBzZXJ2ZXIgc3RvcHBlZCwgYXR0ZW1wdCBvdmVyIgogIGV4aXQgMgp9CgojIDUuIG5vIGVu
dmlyb25tZW50IG11dGF0aW9uIGJldHdlZW4gdGhlIHR3byBjaGlsZHJlbgoKIyA2LiBTRUNPTkQgcHl0aG9uIGNoaWxkOiB0aGUg
Z2F1bnRsZXQKJHJlc3VsdE91dCA9IEpvaW4tUGF0aCAkT1VUICJjb3N0X3ByZWZsaWdodF8ke0FybX1fcmVzdWx0Lmpzb25sIgpw
eXRob24gLW0gc2hvd2Rvd25fYm90LmNsaSBnYXVudGxldCAtLXNjaGVkdWxlICRTQ0hFRCAtLXJlc3VsdC1vdXQgJHJlc3VsdE91
dAokZyA9ICRMQVNURVhJVENPREUKV3JpdGUtT3V0cHV0ICJHQVVOVExFVCBFWElUOiAkZyIKClN0b3AtUHJvY2VzcyAtSWQgJHNy
di5JZCAtRm9yY2UgLUVycm9yQWN0aW9uIFNpbGVudGx5Q29udGludWUKU3RhcnQtU2xlZXAgLU1pbGxpc2Vjb25kcyAxMjAwCldy
aXRlLU91dHB1dCAic2VydmVyICQoJHNydi5JZCkgc3RvcHBlZCIKaWYgKCRnIC1uZSAwKSB7IGV4aXQgMyB9CldyaXRlLU91dHB1
dCAiQVJNICRBcm0gQ09NUExFVEUiCg==
```

---

## `verify_arm6.py`

Pre-arm gate (§7.3 + §4.2). First Python child. Writes `operator-server-<arm>.json` in both the pass and the fail case.

Raw bytes: 5268 &middot; SHA-256 `1ad35d8acf24606f4a6464af54916ad8d1fe7600375725749c0ab726adc30439`

### Readable form (line-normalised — not authoritative)

```python
"""Pre-arm treatment verification (amendment §4.2 + §7.3).

argv: <arm_id> <lifecycle_json_path>
Writes <output-root>/operator-server-<arm>.json ALWAYS (success or failure record).
Exit 0 = gate passed, gauntlet may run. Non-zero = gate failed, attempt over.
"""
import json, os, sys

CAND = r"C:\Users\chris\Documents\cost-preflight-worktree-d64982a"
OUT = r"C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt6"
FORMAT_ID = "gen9championsvgc2026regma"
AGENT = "heuristic"

ARM_VARS = ("SHOWDOWN_SEARCH_DEPTH", "SHOWDOWN_ACCURACY_MODE",
            "SHOWDOWN_ACCURACY_BRANCH_CAP", "SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM")

EXPECTED = {
    "d1_acc_off": dict(depth=1, acc=False, cap=6, topn=2, topm=2, cfg="03d2d5ee27911fc4"),
    "d1_acc_on":  dict(depth=1, acc=True,  cap=6, topn=2, topm=2, cfg="50cf67d5b04a1b04"),
    "d2_acc_off": dict(depth=2, acc=False, cap=6, topn=3, topm=3, cfg="b4c98c07c32f3f9f"),
    "d2_acc_on":  dict(depth=2, acc=True,  cap=6, topn=3, topm=3, cfg="68e04be0173586b2"),
}

arm = sys.argv[1]
life = json.load(open(sys.argv[2], encoding="utf-8-sig"))
exp = EXPECTED[arm]
failures = []

from showdown_bot.battle import decision
dec_file = os.path.normpath(str(decision.__file__ or ""))
import_ok = CAND.lower() in dec_file.lower()
if not import_ok:
    failures.append("decision.__file__ outside candidate: %s" % dec_file)

got = dict(
    depth=decision._search_depth(),
    acc=decision._accuracy_mode(),
    cap=decision._accuracy_branch_cap(),
    topn=decision._search_topn(),
    topm=decision._search_topm(),
)
for k in ("depth", "acc", "cap", "topn", "topm"):
    if got[k] != exp[k]:
        failures.append("%s: got %r expected %r" % (k, got[k], exp[k]))

from showdown_bot.eval.config_env import effective_config_manifest, behavior_env
from showdown_bot.eval.result_jsonl import make_config_hash
benv = behavior_env()
computed = make_config_hash(effective_config_manifest(agent=AGENT, format_id=FORMAT_ID))
if computed != exp["cfg"]:
    failures.append("config_hash: got %s expected %s" % (computed, exp["cfg"]))

# amendment §4.2: schedule + panel + team content binding
sched_ok = panel_ok = teams_ok = False
try:
    from showdown_bot.eval.schedule import load_schedule
    from showdown_bot.eval.i8d_schedule import build_i8d_schedule, verify_i8d_panel_and_teams
    from showdown_bot.eval.panel import load_panel
    teams_root = os.path.join(CAND, "showdown_bot")
    yaml_sched = load_schedule(life["schedule_yaml"])
    if yaml_sched.schedule_hash != "b6f5910e4bc3c584":
        failures.append("yaml schedule_hash %s" % yaml_sched.schedule_hash)
    panel = load_panel(os.path.join(CAND, "config", "eval", "panels", "panel_champions_v0.yaml"),
                       teams_root=teams_root)
    rebuilt = build_i8d_schedule(panel, n_battles=30, teams_root=teams_root)
    if rebuilt.schedule_hash != "b6f5910e4bc3c584":
        failures.append("rebuilt schedule_hash %s != b6f5910e4bc3c584" % rebuilt.schedule_hash)
    else:
        sched_ok = True
    verify_i8d_panel_and_teams(yaml_sched, teams_root=teams_root)
    panel_ok = True
    from showdown_bot.team.pack import load_packed_team
    empties = []
    for row in yaml_sched.rows:
        for p in (row.hero_team_path, row.opp_team_path):
            if not (load_packed_team(os.path.join(teams_root, p)) or "").strip():
                empties.append(p)
    if empties:
        failures.append("empty/missing team files: %s" % sorted(set(empties)))
    else:
        teams_ok = True
except Exception as exc:  # noqa: BLE001 - any §4.2 failure is a gate failure
    failures.append("schedule/panel check raised: %r" % (exc,))

rec = dict(life)
rec.update({
    "arm_id": arm,
    "arm_env_raw": {v: os.environ.get(v) for v in ARM_VARS},
    "decision_module_file": dec_file,
    "import_root_verified": import_ok,
    "resolved_search_depth": got["depth"],
    "resolved_accuracy_mode": got["acc"],
    "resolved_accuracy_branch_cap": got["cap"],
    "resolved_search_topn": got["topn"],
    "resolved_search_topm": got["topm"],
    "behavior_env": benv,
    "expected_config_hash": exp["cfg"],
    "computed_config_hash": computed,
    "resolvers_match_arm": not any(
        got[k] != exp[k] for k in ("depth", "acc", "cap", "topn", "topm")
    ),
    "config_hash_matches_expected": computed == exp["cfg"],
    "schedule_rebuild_verified": sched_ok,
    "panel_and_team_content_verified": panel_ok,
    "team_files_non_empty": teams_ok,
    "gate_passed": not failures,
    "gate_failures": failures,
})

path = os.path.join(OUT, "operator-server-%s.json" % arm)
if os.path.exists(path):
    sys.exit("FAIL: %s already exists; output is immutable" % path)
with open(path, "w", encoding="utf-8") as fh:
    json.dump(rec, fh, indent=2, sort_keys=True)

print("arm=%s depth=%r acc=%r cap=%r topn=%r topm=%r" % (
    arm, got["depth"], got["acc"], got["cap"], got["topn"], got["topm"]))
print("config_hash computed=%s expected=%s" % (computed, exp["cfg"]))
print("behavior_env=%s" % json.dumps(benv, sort_keys=True))
print("schedule_rebuild=%s panel_content=%s teams_non_empty=%s" % (sched_ok, panel_ok, teams_ok))
if failures:
    print("GATE FAILED:")
    for f in failures:
        print("  - %s" % f)
    sys.exit(2)
print("GATE PASSED")
```

### Raw bytes, Base64 (authoritative)

```text
IiIiUHJlLWFybSB0cmVhdG1lbnQgdmVyaWZpY2F0aW9uIChhbWVuZG1lbnQgwqc0LjIgKyDCpzcuMykuCgphcmd2OiA8YXJtX2lk
PiA8bGlmZWN5Y2xlX2pzb25fcGF0aD4KV3JpdGVzIDxvdXRwdXQtcm9vdD4vb3BlcmF0b3Itc2VydmVyLTxhcm0+Lmpzb24gQUxX
QVlTIChzdWNjZXNzIG9yIGZhaWx1cmUgcmVjb3JkKS4KRXhpdCAwID0gZ2F0ZSBwYXNzZWQsIGdhdW50bGV0IG1heSBydW4uIE5v
bi16ZXJvID0gZ2F0ZSBmYWlsZWQsIGF0dGVtcHQgb3Zlci4KIiIiCmltcG9ydCBqc29uLCBvcywgc3lzCgpDQU5EID0gciJDOlxV
c2Vyc1xjaHJpc1xEb2N1bWVudHNcY29zdC1wcmVmbGlnaHQtd29ya3RyZWUtZDY0OTgyYSIKT1VUID0gciJDOlxVc2Vyc1xjaHJp
c1xEb2N1bWVudHNcY29zdC1wcmVmbGlnaHQtZDItZDY0OTgyYS1hdHRlbXB0NiIKRk9STUFUX0lEID0gImdlbjljaGFtcGlvbnN2
Z2MyMDI2cmVnbWEiCkFHRU5UID0gImhldXJpc3RpYyIKCkFSTV9WQVJTID0gKCJTSE9XRE9XTl9TRUFSQ0hfREVQVEgiLCAiU0hP
V0RPV05fQUNDVVJBQ1lfTU9ERSIsCiAgICAgICAgICAgICJTSE9XRE9XTl9BQ0NVUkFDWV9CUkFOQ0hfQ0FQIiwgIlNIT1dET1dO
X1NFQVJDSF9UT1BOIiwgIlNIT1dET1dOX1NFQVJDSF9UT1BNIikKCkVYUEVDVEVEID0gewogICAgImQxX2FjY19vZmYiOiBkaWN0
KGRlcHRoPTEsIGFjYz1GYWxzZSwgY2FwPTYsIHRvcG49MiwgdG9wbT0yLCBjZmc9IjAzZDJkNWVlMjc5MTFmYzQiKSwKICAgICJk
MV9hY2Nfb24iOiAgZGljdChkZXB0aD0xLCBhY2M9VHJ1ZSwgIGNhcD02LCB0b3BuPTIsIHRvcG09MiwgY2ZnPSI1MGNmNjdkNWIw
NGExYjA0IiksCiAgICAiZDJfYWNjX29mZiI6IGRpY3QoZGVwdGg9MiwgYWNjPUZhbHNlLCBjYXA9NiwgdG9wbj0zLCB0b3BtPTMs
IGNmZz0iYjRjOThjMDdjMzJmM2Y5ZiIpLAogICAgImQyX2FjY19vbiI6ICBkaWN0KGRlcHRoPTIsIGFjYz1UcnVlLCAgY2FwPTYs
IHRvcG49MywgdG9wbT0zLCBjZmc9IjY4ZTA0YmUwMTczNTg2YjIiKSwKfQoKYXJtID0gc3lzLmFyZ3ZbMV0KbGlmZSA9IGpzb24u
bG9hZChvcGVuKHN5cy5hcmd2WzJdLCBlbmNvZGluZz0idXRmLTgtc2lnIikpCmV4cCA9IEVYUEVDVEVEW2FybV0KZmFpbHVyZXMg
PSBbXQoKZnJvbSBzaG93ZG93bl9ib3QuYmF0dGxlIGltcG9ydCBkZWNpc2lvbgpkZWNfZmlsZSA9IG9zLnBhdGgubm9ybXBhdGgo
c3RyKGRlY2lzaW9uLl9fZmlsZV9fIG9yICIiKSkKaW1wb3J0X29rID0gQ0FORC5sb3dlcigpIGluIGRlY19maWxlLmxvd2VyKCkK
aWYgbm90IGltcG9ydF9vazoKICAgIGZhaWx1cmVzLmFwcGVuZCgiZGVjaXNpb24uX19maWxlX18gb3V0c2lkZSBjYW5kaWRhdGU6
ICVzIiAlIGRlY19maWxlKQoKZ290ID0gZGljdCgKICAgIGRlcHRoPWRlY2lzaW9uLl9zZWFyY2hfZGVwdGgoKSwKICAgIGFjYz1k
ZWNpc2lvbi5fYWNjdXJhY3lfbW9kZSgpLAogICAgY2FwPWRlY2lzaW9uLl9hY2N1cmFjeV9icmFuY2hfY2FwKCksCiAgICB0b3Bu
PWRlY2lzaW9uLl9zZWFyY2hfdG9wbigpLAogICAgdG9wbT1kZWNpc2lvbi5fc2VhcmNoX3RvcG0oKSwKKQpmb3IgayBpbiAoImRl
cHRoIiwgImFjYyIsICJjYXAiLCAidG9wbiIsICJ0b3BtIik6CiAgICBpZiBnb3Rba10gIT0gZXhwW2tdOgogICAgICAgIGZhaWx1
cmVzLmFwcGVuZCgiJXM6IGdvdCAlciBleHBlY3RlZCAlciIgJSAoaywgZ290W2tdLCBleHBba10pKQoKZnJvbSBzaG93ZG93bl9i
b3QuZXZhbC5jb25maWdfZW52IGltcG9ydCBlZmZlY3RpdmVfY29uZmlnX21hbmlmZXN0LCBiZWhhdmlvcl9lbnYKZnJvbSBzaG93
ZG93bl9ib3QuZXZhbC5yZXN1bHRfanNvbmwgaW1wb3J0IG1ha2VfY29uZmlnX2hhc2gKYmVudiA9IGJlaGF2aW9yX2VudigpCmNv
bXB1dGVkID0gbWFrZV9jb25maWdfaGFzaChlZmZlY3RpdmVfY29uZmlnX21hbmlmZXN0KGFnZW50PUFHRU5ULCBmb3JtYXRfaWQ9
Rk9STUFUX0lEKSkKaWYgY29tcHV0ZWQgIT0gZXhwWyJjZmciXToKICAgIGZhaWx1cmVzLmFwcGVuZCgiY29uZmlnX2hhc2g6IGdv
dCAlcyBleHBlY3RlZCAlcyIgJSAoY29tcHV0ZWQsIGV4cFsiY2ZnIl0pKQoKIyBhbWVuZG1lbnQgwqc0LjI6IHNjaGVkdWxlICsg
cGFuZWwgKyB0ZWFtIGNvbnRlbnQgYmluZGluZwpzY2hlZF9vayA9IHBhbmVsX29rID0gdGVhbXNfb2sgPSBGYWxzZQp0cnk6CiAg
ICBmcm9tIHNob3dkb3duX2JvdC5ldmFsLnNjaGVkdWxlIGltcG9ydCBsb2FkX3NjaGVkdWxlCiAgICBmcm9tIHNob3dkb3duX2Jv
dC5ldmFsLmk4ZF9zY2hlZHVsZSBpbXBvcnQgYnVpbGRfaThkX3NjaGVkdWxlLCB2ZXJpZnlfaThkX3BhbmVsX2FuZF90ZWFtcwog
ICAgZnJvbSBzaG93ZG93bl9ib3QuZXZhbC5wYW5lbCBpbXBvcnQgbG9hZF9wYW5lbAogICAgdGVhbXNfcm9vdCA9IG9zLnBhdGgu
am9pbihDQU5ELCAic2hvd2Rvd25fYm90IikKICAgIHlhbWxfc2NoZWQgPSBsb2FkX3NjaGVkdWxlKGxpZmVbInNjaGVkdWxlX3lh
bWwiXSkKICAgIGlmIHlhbWxfc2NoZWQuc2NoZWR1bGVfaGFzaCAhPSAiYjZmNTkxMGU0YmMzYzU4NCI6CiAgICAgICAgZmFpbHVy
ZXMuYXBwZW5kKCJ5YW1sIHNjaGVkdWxlX2hhc2ggJXMiICUgeWFtbF9zY2hlZC5zY2hlZHVsZV9oYXNoKQogICAgcGFuZWwgPSBs
b2FkX3BhbmVsKG9zLnBhdGguam9pbihDQU5ELCAiY29uZmlnIiwgImV2YWwiLCAicGFuZWxzIiwgInBhbmVsX2NoYW1waW9uc192
MC55YW1sIiksCiAgICAgICAgICAgICAgICAgICAgICAgdGVhbXNfcm9vdD10ZWFtc19yb290KQogICAgcmVidWlsdCA9IGJ1aWxk
X2k4ZF9zY2hlZHVsZShwYW5lbCwgbl9iYXR0bGVzPTMwLCB0ZWFtc19yb290PXRlYW1zX3Jvb3QpCiAgICBpZiByZWJ1aWx0LnNj
aGVkdWxlX2hhc2ggIT0gImI2ZjU5MTBlNGJjM2M1ODQiOgogICAgICAgIGZhaWx1cmVzLmFwcGVuZCgicmVidWlsdCBzY2hlZHVs
ZV9oYXNoICVzICE9IGI2ZjU5MTBlNGJjM2M1ODQiICUgcmVidWlsdC5zY2hlZHVsZV9oYXNoKQogICAgZWxzZToKICAgICAgICBz
Y2hlZF9vayA9IFRydWUKICAgIHZlcmlmeV9pOGRfcGFuZWxfYW5kX3RlYW1zKHlhbWxfc2NoZWQsIHRlYW1zX3Jvb3Q9dGVhbXNf
cm9vdCkKICAgIHBhbmVsX29rID0gVHJ1ZQogICAgZnJvbSBzaG93ZG93bl9ib3QudGVhbS5wYWNrIGltcG9ydCBsb2FkX3BhY2tl
ZF90ZWFtCiAgICBlbXB0aWVzID0gW10KICAgIGZvciByb3cgaW4geWFtbF9zY2hlZC5yb3dzOgogICAgICAgIGZvciBwIGluIChy
b3cuaGVyb190ZWFtX3BhdGgsIHJvdy5vcHBfdGVhbV9wYXRoKToKICAgICAgICAgICAgaWYgbm90IChsb2FkX3BhY2tlZF90ZWFt
KG9zLnBhdGguam9pbih0ZWFtc19yb290LCBwKSkgb3IgIiIpLnN0cmlwKCk6CiAgICAgICAgICAgICAgICBlbXB0aWVzLmFwcGVu
ZChwKQogICAgaWYgZW1wdGllczoKICAgICAgICBmYWlsdXJlcy5hcHBlbmQoImVtcHR5L21pc3NpbmcgdGVhbSBmaWxlczogJXMi
ICUgc29ydGVkKHNldChlbXB0aWVzKSkpCiAgICBlbHNlOgogICAgICAgIHRlYW1zX29rID0gVHJ1ZQpleGNlcHQgRXhjZXB0aW9u
IGFzIGV4YzogICMgbm9xYTogQkxFMDAxIC0gYW55IMKnNC4yIGZhaWx1cmUgaXMgYSBnYXRlIGZhaWx1cmUKICAgIGZhaWx1cmVz
LmFwcGVuZCgic2NoZWR1bGUvcGFuZWwgY2hlY2sgcmFpc2VkOiAlciIgJSAoZXhjLCkpCgpyZWMgPSBkaWN0KGxpZmUpCnJlYy51
cGRhdGUoewogICAgImFybV9pZCI6IGFybSwKICAgICJhcm1fZW52X3JhdyI6IHt2OiBvcy5lbnZpcm9uLmdldCh2KSBmb3IgdiBp
biBBUk1fVkFSU30sCiAgICAiZGVjaXNpb25fbW9kdWxlX2ZpbGUiOiBkZWNfZmlsZSwKICAgICJpbXBvcnRfcm9vdF92ZXJpZmll
ZCI6IGltcG9ydF9vaywKICAgICJyZXNvbHZlZF9zZWFyY2hfZGVwdGgiOiBnb3RbImRlcHRoIl0sCiAgICAicmVzb2x2ZWRfYWNj
dXJhY3lfbW9kZSI6IGdvdFsiYWNjIl0sCiAgICAicmVzb2x2ZWRfYWNjdXJhY3lfYnJhbmNoX2NhcCI6IGdvdFsiY2FwIl0sCiAg
ICAicmVzb2x2ZWRfc2VhcmNoX3RvcG4iOiBnb3RbInRvcG4iXSwKICAgICJyZXNvbHZlZF9zZWFyY2hfdG9wbSI6IGdvdFsidG9w
bSJdLAogICAgImJlaGF2aW9yX2VudiI6IGJlbnYsCiAgICAiZXhwZWN0ZWRfY29uZmlnX2hhc2giOiBleHBbImNmZyJdLAogICAg
ImNvbXB1dGVkX2NvbmZpZ19oYXNoIjogY29tcHV0ZWQsCiAgICAicmVzb2x2ZXJzX21hdGNoX2FybSI6IG5vdCBhbnkoCiAgICAg
ICAgZ290W2tdICE9IGV4cFtrXSBmb3IgayBpbiAoImRlcHRoIiwgImFjYyIsICJjYXAiLCAidG9wbiIsICJ0b3BtIikKICAgICks
CiAgICAiY29uZmlnX2hhc2hfbWF0Y2hlc19leHBlY3RlZCI6IGNvbXB1dGVkID09IGV4cFsiY2ZnIl0sCiAgICAic2NoZWR1bGVf
cmVidWlsZF92ZXJpZmllZCI6IHNjaGVkX29rLAogICAgInBhbmVsX2FuZF90ZWFtX2NvbnRlbnRfdmVyaWZpZWQiOiBwYW5lbF9v
aywKICAgICJ0ZWFtX2ZpbGVzX25vbl9lbXB0eSI6IHRlYW1zX29rLAogICAgImdhdGVfcGFzc2VkIjogbm90IGZhaWx1cmVzLAog
ICAgImdhdGVfZmFpbHVyZXMiOiBmYWlsdXJlcywKfSkKCnBhdGggPSBvcy5wYXRoLmpvaW4oT1VULCAib3BlcmF0b3Itc2VydmVy
LSVzLmpzb24iICUgYXJtKQppZiBvcy5wYXRoLmV4aXN0cyhwYXRoKToKICAgIHN5cy5leGl0KCJGQUlMOiAlcyBhbHJlYWR5IGV4
aXN0czsgb3V0cHV0IGlzIGltbXV0YWJsZSIgJSBwYXRoKQp3aXRoIG9wZW4ocGF0aCwgInciLCBlbmNvZGluZz0idXRmLTgiKSBh
cyBmaDoKICAgIGpzb24uZHVtcChyZWMsIGZoLCBpbmRlbnQ9Miwgc29ydF9rZXlzPVRydWUpCgpwcmludCgiYXJtPSVzIGRlcHRo
PSVyIGFjYz0lciBjYXA9JXIgdG9wbj0lciB0b3BtPSVyIiAlICgKICAgIGFybSwgZ290WyJkZXB0aCJdLCBnb3RbImFjYyJdLCBn
b3RbImNhcCJdLCBnb3RbInRvcG4iXSwgZ290WyJ0b3BtIl0pKQpwcmludCgiY29uZmlnX2hhc2ggY29tcHV0ZWQ9JXMgZXhwZWN0
ZWQ9JXMiICUgKGNvbXB1dGVkLCBleHBbImNmZyJdKSkKcHJpbnQoImJlaGF2aW9yX2Vudj0lcyIgJSBqc29uLmR1bXBzKGJlbnYs
IHNvcnRfa2V5cz1UcnVlKSkKcHJpbnQoInNjaGVkdWxlX3JlYnVpbGQ9JXMgcGFuZWxfY29udGVudD0lcyB0ZWFtc19ub25fZW1w
dHk9JXMiICUgKHNjaGVkX29rLCBwYW5lbF9vaywgdGVhbXNfb2spKQppZiBmYWlsdXJlczoKICAgIHByaW50KCJHQVRFIEZBSUxF
RDoiKQogICAgZm9yIGYgaW4gZmFpbHVyZXM6CiAgICAgICAgcHJpbnQoIiAgLSAlcyIgJSBmKQogICAgc3lzLmV4aXQoMikKcHJp
bnQoIkdBVEUgUEFTU0VEIikK
```

---

## `post_arm6.py`

Post-arm gate (§11.0, §11.1, §11.1a, §11.2). Run after each arm, before the next arm starts.

Raw bytes: 5278 &middot; SHA-256 `1f076b8c1fc082a226f02910afeef6633657dd2250eac0762cbebb2523c80a6b`

### Readable form (line-normalised — not authoritative)

```python
"""Post-arm treatment gate (amendment §11.0 + §11.1 + §11.1a + §11.2).

argv: <arm_id>.  Exit 0 = arm valid, next arm may start.  Non-zero = attempt invalid.
"""
import json, os, sys

OUT = r"C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt6"
GIT_SHA = "d64982ae9fdba6a877c8c2b7e804923ebcc7fec4"

EXPECTED = {
    "d1_acc_off": dict(depth=1, acc=False, cap=6, topn=2, topm=2, cfg="03d2d5ee27911fc4", d2=False),
    "d1_acc_on":  dict(depth=1, acc=True,  cap=6, topn=2, topm=2, cfg="50cf67d5b04a1b04", d2=False),
    "d2_acc_off": dict(depth=2, acc=False, cap=6, topn=3, topm=3, cfg="b4c98c07c32f3f9f", d2=True),
    "d2_acc_on":  dict(depth=2, acc=True,  cap=6, topn=3, topm=3, cfg="68e04be0173586b2", d2=True),
}

arm = sys.argv[1]
exp = EXPECTED[arm]
fails = []

prof_p = os.path.join(OUT, "cost_preflight_%s_profile.jsonl" % arm)
res_p = os.path.join(OUT, "cost_preflight_%s_result.jsonl" % arm)
seed_p = os.path.join(OUT, "cost_preflight_%s_seedlog.jsonl" % arm)
man_p = res_p + ".manifest.json"

rows = [json.loads(l) for l in open(prof_p, encoding="utf-8") if l.strip()]
res = [json.loads(l) for l in open(res_p, encoding="utf-8") if l.strip()]
seeds = [l for l in open(seed_p, encoding="utf-8") if l.strip()]
man = json.load(open(man_p, encoding="utf-8-sig"))

if not rows:
    fails.append("profile dataset EMPTY")
if len(res) != 30:
    fails.append("result rows %d != 30" % len(res))
if len(seeds) != 30:
    fails.append("seedlog entries %d != 30" % len(seeds))

# §11.1a treatment, every row
bad = {}
for r in rows:
    for key, want in (("search_depth", exp["depth"]), ("accuracy_mode", exp["acc"]),
                      ("accuracy_branch_cap", exp["cap"]),
                      ("search_topn_requested", exp["topn"]),
                      ("search_topm_requested", exp["topm"])):
        if r.get(key) != want:
            bad.setdefault(key, set()).add(repr(r.get(key)))
for k, v in bad.items():
    fails.append("treatment %s: saw %s expected %r" % (k, sorted(v), EXPECTED[arm][
        {"search_depth": "depth", "accuracy_mode": "acc", "accuracy_branch_cap": "cap",
         "search_topn_requested": "topn", "search_topm_requested": "topm"}[k]]))

# §11.1a depth-2 frontier
frontiers = [r.get("depth2_frontier", 0) for r in rows]
n_pos = sum(1 for f in frontiers if f and f > 0)
if exp["d2"] and n_pos == 0:
    fails.append("depth-2 arm has NO row with depth2_frontier > 0 -> no depth-2 cost evidence")
if (not exp["d2"]) and n_pos:
    fails.append("depth-1 arm has %d rows with depth2_frontier > 0" % n_pos)

# §11.1 config_hash + git_sha
cfgs = {r.get("config_hash") for r in rows}
if cfgs != {exp["cfg"]}:
    fails.append("profile config_hash %s expected {%s}" % (sorted(cfgs), exp["cfg"]))
if man.get("config_hash") != exp["cfg"]:
    fails.append("manifest config_hash %s expected %s" % (man.get("config_hash"), exp["cfg"]))
shas = {r.get("git_sha") for r in rows}
if shas != {GIT_SHA}:
    fails.append("git_sha %s" % sorted(shas))
if man.get("dirty"):
    fails.append("manifest dirty=True")

# §11.2 dataset health
vers = {r.get("schema_version") for r in rows}
if vers != {"decision-profile-v4"}:
    fails.append("schema_version %s" % sorted(vers))
keys = [(r.get("battle_id"), r.get("decision_index")) for r in rows]
if len(keys) != len(set(keys)):
    fails.append("duplicate (battle_id, decision_index)")
outs = {r.get("outcome") for r in rows}
if outs != {"ok"}:
    fails.append("outcome %s" % sorted(outs))
stages = {r.get("selection_stage") for r in rows}
if stages != {"heuristic"}:
    fails.append("selection_stage %s" % sorted(stages))
fbs = {r.get("fallback_reason") for r in rows}
if fbs - {None}:
    fails.append("fallback_reason %s" % sorted(x for x in fbs if x))
classes = {r.get("backend_class") for r in rows}
if classes - {"clean_cold", "clean_warm"}:
    fails.append("backend_class %s" % sorted(classes))
prof_bids = {r.get("battle_id") for r in rows}
res_bids = {r.get("battle_id") for r in res}
missing = res_bids - prof_bids
if missing:
    fails.append("%d result battle_ids have no profile row" % len(missing))
crashes = sum(r.get("crashes") or 0 for r in res)
invalid = sum(r.get("invalid") or 0 for r in res)
if crashes or invalid:
    fails.append("crashes=%d invalid=%d" % (crashes, invalid))

ms = [r["measured_ms"] for r in rows if r.get("measured_ms") is not None]
ms.sort()
p50 = ms[len(ms) // 2] if ms else None
p95 = ms[int(len(ms) * 0.95)] if ms else None

print("arm=%s profile_rows=%d result_rows=%d seedlog=%d" % (arm, len(rows), len(res), len(seeds)))
print("treatment depth=%r acc=%r cap=%r topn=%r topm=%r" % (
    rows[0].get("search_depth"), rows[0].get("accuracy_mode"), rows[0].get("accuracy_branch_cap"),
    rows[0].get("search_topn_requested"), rows[0].get("search_topm_requested")))
print("config_hash profile=%s manifest=%s expected=%s" % (
    sorted(cfgs), man.get("config_hash"), exp["cfg"]))
print("depth2_frontier: %d/%d rows > 0 (max %s)" % (n_pos, len(rows), max(frontiers) if frontiers else 0))
print("backend_class=%s  measured_ms p50=%.1f p95=%.1f max=%.1f" % (
    sorted(classes), p50 or 0, p95 or 0, ms[-1] if ms else 0))
if fails:
    print("POST-ARM GATE FAILED:")
    for f in fails:
        print("  - %s" % f)
    sys.exit(2)
print("POST-ARM GATE PASSED")
```

### Raw bytes, Base64 (authoritative)

```text
IiIiUG9zdC1hcm0gdHJlYXRtZW50IGdhdGUgKGFtZW5kbWVudCDCpzExLjAgKyDCpzExLjEgKyDCpzExLjFhICsgwqcxMS4yKS4K
CmFyZ3Y6IDxhcm1faWQ+LiAgRXhpdCAwID0gYXJtIHZhbGlkLCBuZXh0IGFybSBtYXkgc3RhcnQuICBOb24temVybyA9IGF0dGVt
cHQgaW52YWxpZC4KIiIiCmltcG9ydCBqc29uLCBvcywgc3lzCgpPVVQgPSByIkM6XFVzZXJzXGNocmlzXERvY3VtZW50c1xjb3N0
LXByZWZsaWdodC1kMi1kNjQ5ODJhLWF0dGVtcHQ2IgpHSVRfU0hBID0gImQ2NDk4MmFlOWZkYmE2YTg3N2M4YzJiN2U4MDQ5MjNl
YmNjN2ZlYzQiCgpFWFBFQ1RFRCA9IHsKICAgICJkMV9hY2Nfb2ZmIjogZGljdChkZXB0aD0xLCBhY2M9RmFsc2UsIGNhcD02LCB0
b3BuPTIsIHRvcG09MiwgY2ZnPSIwM2QyZDVlZTI3OTExZmM0IiwgZDI9RmFsc2UpLAogICAgImQxX2FjY19vbiI6ICBkaWN0KGRl
cHRoPTEsIGFjYz1UcnVlLCAgY2FwPTYsIHRvcG49MiwgdG9wbT0yLCBjZmc9IjUwY2Y2N2Q1YjA0YTFiMDQiLCBkMj1GYWxzZSks
CiAgICAiZDJfYWNjX29mZiI6IGRpY3QoZGVwdGg9MiwgYWNjPUZhbHNlLCBjYXA9NiwgdG9wbj0zLCB0b3BtPTMsIGNmZz0iYjRj
OThjMDdjMzJmM2Y5ZiIsIGQyPVRydWUpLAogICAgImQyX2FjY19vbiI6ICBkaWN0KGRlcHRoPTIsIGFjYz1UcnVlLCAgY2FwPTYs
IHRvcG49MywgdG9wbT0zLCBjZmc9IjY4ZTA0YmUwMTczNTg2YjIiLCBkMj1UcnVlKSwKfQoKYXJtID0gc3lzLmFyZ3ZbMV0KZXhw
ID0gRVhQRUNURURbYXJtXQpmYWlscyA9IFtdCgpwcm9mX3AgPSBvcy5wYXRoLmpvaW4oT1VULCAiY29zdF9wcmVmbGlnaHRfJXNf
cHJvZmlsZS5qc29ubCIgJSBhcm0pCnJlc19wID0gb3MucGF0aC5qb2luKE9VVCwgImNvc3RfcHJlZmxpZ2h0XyVzX3Jlc3VsdC5q
c29ubCIgJSBhcm0pCnNlZWRfcCA9IG9zLnBhdGguam9pbihPVVQsICJjb3N0X3ByZWZsaWdodF8lc19zZWVkbG9nLmpzb25sIiAl
IGFybSkKbWFuX3AgPSByZXNfcCArICIubWFuaWZlc3QuanNvbiIKCnJvd3MgPSBbanNvbi5sb2FkcyhsKSBmb3IgbCBpbiBvcGVu
KHByb2ZfcCwgZW5jb2Rpbmc9InV0Zi04IikgaWYgbC5zdHJpcCgpXQpyZXMgPSBbanNvbi5sb2FkcyhsKSBmb3IgbCBpbiBvcGVu
KHJlc19wLCBlbmNvZGluZz0idXRmLTgiKSBpZiBsLnN0cmlwKCldCnNlZWRzID0gW2wgZm9yIGwgaW4gb3BlbihzZWVkX3AsIGVu
Y29kaW5nPSJ1dGYtOCIpIGlmIGwuc3RyaXAoKV0KbWFuID0ganNvbi5sb2FkKG9wZW4obWFuX3AsIGVuY29kaW5nPSJ1dGYtOC1z
aWciKSkKCmlmIG5vdCByb3dzOgogICAgZmFpbHMuYXBwZW5kKCJwcm9maWxlIGRhdGFzZXQgRU1QVFkiKQppZiBsZW4ocmVzKSAh
PSAzMDoKICAgIGZhaWxzLmFwcGVuZCgicmVzdWx0IHJvd3MgJWQgIT0gMzAiICUgbGVuKHJlcykpCmlmIGxlbihzZWVkcykgIT0g
MzA6CiAgICBmYWlscy5hcHBlbmQoInNlZWRsb2cgZW50cmllcyAlZCAhPSAzMCIgJSBsZW4oc2VlZHMpKQoKIyDCpzExLjFhIHRy
ZWF0bWVudCwgZXZlcnkgcm93CmJhZCA9IHt9CmZvciByIGluIHJvd3M6CiAgICBmb3Iga2V5LCB3YW50IGluICgoInNlYXJjaF9k
ZXB0aCIsIGV4cFsiZGVwdGgiXSksICgiYWNjdXJhY3lfbW9kZSIsIGV4cFsiYWNjIl0pLAogICAgICAgICAgICAgICAgICAgICAg
KCJhY2N1cmFjeV9icmFuY2hfY2FwIiwgZXhwWyJjYXAiXSksCiAgICAgICAgICAgICAgICAgICAgICAoInNlYXJjaF90b3BuX3Jl
cXVlc3RlZCIsIGV4cFsidG9wbiJdKSwKICAgICAgICAgICAgICAgICAgICAgICgic2VhcmNoX3RvcG1fcmVxdWVzdGVkIiwgZXhw
WyJ0b3BtIl0pKToKICAgICAgICBpZiByLmdldChrZXkpICE9IHdhbnQ6CiAgICAgICAgICAgIGJhZC5zZXRkZWZhdWx0KGtleSwg
c2V0KCkpLmFkZChyZXByKHIuZ2V0KGtleSkpKQpmb3IgaywgdiBpbiBiYWQuaXRlbXMoKToKICAgIGZhaWxzLmFwcGVuZCgidHJl
YXRtZW50ICVzOiBzYXcgJXMgZXhwZWN0ZWQgJXIiICUgKGssIHNvcnRlZCh2KSwgRVhQRUNURURbYXJtXVsKICAgICAgICB7InNl
YXJjaF9kZXB0aCI6ICJkZXB0aCIsICJhY2N1cmFjeV9tb2RlIjogImFjYyIsICJhY2N1cmFjeV9icmFuY2hfY2FwIjogImNhcCIs
CiAgICAgICAgICJzZWFyY2hfdG9wbl9yZXF1ZXN0ZWQiOiAidG9wbiIsICJzZWFyY2hfdG9wbV9yZXF1ZXN0ZWQiOiAidG9wbSJ9
W2tdXSkpCgojIMKnMTEuMWEgZGVwdGgtMiBmcm9udGllcgpmcm9udGllcnMgPSBbci5nZXQoImRlcHRoMl9mcm9udGllciIsIDAp
IGZvciByIGluIHJvd3NdCm5fcG9zID0gc3VtKDEgZm9yIGYgaW4gZnJvbnRpZXJzIGlmIGYgYW5kIGYgPiAwKQppZiBleHBbImQy
Il0gYW5kIG5fcG9zID09IDA6CiAgICBmYWlscy5hcHBlbmQoImRlcHRoLTIgYXJtIGhhcyBOTyByb3cgd2l0aCBkZXB0aDJfZnJv
bnRpZXIgPiAwIC0+IG5vIGRlcHRoLTIgY29zdCBldmlkZW5jZSIpCmlmIChub3QgZXhwWyJkMiJdKSBhbmQgbl9wb3M6CiAgICBm
YWlscy5hcHBlbmQoImRlcHRoLTEgYXJtIGhhcyAlZCByb3dzIHdpdGggZGVwdGgyX2Zyb250aWVyID4gMCIgJSBuX3BvcykKCiMg
wqcxMS4xIGNvbmZpZ19oYXNoICsgZ2l0X3NoYQpjZmdzID0ge3IuZ2V0KCJjb25maWdfaGFzaCIpIGZvciByIGluIHJvd3N9Cmlm
IGNmZ3MgIT0ge2V4cFsiY2ZnIl19OgogICAgZmFpbHMuYXBwZW5kKCJwcm9maWxlIGNvbmZpZ19oYXNoICVzIGV4cGVjdGVkIHsl
c30iICUgKHNvcnRlZChjZmdzKSwgZXhwWyJjZmciXSkpCmlmIG1hbi5nZXQoImNvbmZpZ19oYXNoIikgIT0gZXhwWyJjZmciXToK
ICAgIGZhaWxzLmFwcGVuZCgibWFuaWZlc3QgY29uZmlnX2hhc2ggJXMgZXhwZWN0ZWQgJXMiICUgKG1hbi5nZXQoImNvbmZpZ19o
YXNoIiksIGV4cFsiY2ZnIl0pKQpzaGFzID0ge3IuZ2V0KCJnaXRfc2hhIikgZm9yIHIgaW4gcm93c30KaWYgc2hhcyAhPSB7R0lU
X1NIQX06CiAgICBmYWlscy5hcHBlbmQoImdpdF9zaGEgJXMiICUgc29ydGVkKHNoYXMpKQppZiBtYW4uZ2V0KCJkaXJ0eSIpOgog
ICAgZmFpbHMuYXBwZW5kKCJtYW5pZmVzdCBkaXJ0eT1UcnVlIikKCiMgwqcxMS4yIGRhdGFzZXQgaGVhbHRoCnZlcnMgPSB7ci5n
ZXQoInNjaGVtYV92ZXJzaW9uIikgZm9yIHIgaW4gcm93c30KaWYgdmVycyAhPSB7ImRlY2lzaW9uLXByb2ZpbGUtdjQifToKICAg
IGZhaWxzLmFwcGVuZCgic2NoZW1hX3ZlcnNpb24gJXMiICUgc29ydGVkKHZlcnMpKQprZXlzID0gWyhyLmdldCgiYmF0dGxlX2lk
IiksIHIuZ2V0KCJkZWNpc2lvbl9pbmRleCIpKSBmb3IgciBpbiByb3dzXQppZiBsZW4oa2V5cykgIT0gbGVuKHNldChrZXlzKSk6
CiAgICBmYWlscy5hcHBlbmQoImR1cGxpY2F0ZSAoYmF0dGxlX2lkLCBkZWNpc2lvbl9pbmRleCkiKQpvdXRzID0ge3IuZ2V0KCJv
dXRjb21lIikgZm9yIHIgaW4gcm93c30KaWYgb3V0cyAhPSB7Im9rIn06CiAgICBmYWlscy5hcHBlbmQoIm91dGNvbWUgJXMiICUg
c29ydGVkKG91dHMpKQpzdGFnZXMgPSB7ci5nZXQoInNlbGVjdGlvbl9zdGFnZSIpIGZvciByIGluIHJvd3N9CmlmIHN0YWdlcyAh
PSB7ImhldXJpc3RpYyJ9OgogICAgZmFpbHMuYXBwZW5kKCJzZWxlY3Rpb25fc3RhZ2UgJXMiICUgc29ydGVkKHN0YWdlcykpCmZi
cyA9IHtyLmdldCgiZmFsbGJhY2tfcmVhc29uIikgZm9yIHIgaW4gcm93c30KaWYgZmJzIC0ge05vbmV9OgogICAgZmFpbHMuYXBw
ZW5kKCJmYWxsYmFja19yZWFzb24gJXMiICUgc29ydGVkKHggZm9yIHggaW4gZmJzIGlmIHgpKQpjbGFzc2VzID0ge3IuZ2V0KCJi
YWNrZW5kX2NsYXNzIikgZm9yIHIgaW4gcm93c30KaWYgY2xhc3NlcyAtIHsiY2xlYW5fY29sZCIsICJjbGVhbl93YXJtIn06CiAg
ICBmYWlscy5hcHBlbmQoImJhY2tlbmRfY2xhc3MgJXMiICUgc29ydGVkKGNsYXNzZXMpKQpwcm9mX2JpZHMgPSB7ci5nZXQoImJh
dHRsZV9pZCIpIGZvciByIGluIHJvd3N9CnJlc19iaWRzID0ge3IuZ2V0KCJiYXR0bGVfaWQiKSBmb3IgciBpbiByZXN9Cm1pc3Np
bmcgPSByZXNfYmlkcyAtIHByb2ZfYmlkcwppZiBtaXNzaW5nOgogICAgZmFpbHMuYXBwZW5kKCIlZCByZXN1bHQgYmF0dGxlX2lk
cyBoYXZlIG5vIHByb2ZpbGUgcm93IiAlIGxlbihtaXNzaW5nKSkKY3Jhc2hlcyA9IHN1bShyLmdldCgiY3Jhc2hlcyIpIG9yIDAg
Zm9yIHIgaW4gcmVzKQppbnZhbGlkID0gc3VtKHIuZ2V0KCJpbnZhbGlkIikgb3IgMCBmb3IgciBpbiByZXMpCmlmIGNyYXNoZXMg
b3IgaW52YWxpZDoKICAgIGZhaWxzLmFwcGVuZCgiY3Jhc2hlcz0lZCBpbnZhbGlkPSVkIiAlIChjcmFzaGVzLCBpbnZhbGlkKSkK
Cm1zID0gW3JbIm1lYXN1cmVkX21zIl0gZm9yIHIgaW4gcm93cyBpZiByLmdldCgibWVhc3VyZWRfbXMiKSBpcyBub3QgTm9uZV0K
bXMuc29ydCgpCnA1MCA9IG1zW2xlbihtcykgLy8gMl0gaWYgbXMgZWxzZSBOb25lCnA5NSA9IG1zW2ludChsZW4obXMpICogMC45
NSldIGlmIG1zIGVsc2UgTm9uZQoKcHJpbnQoImFybT0lcyBwcm9maWxlX3Jvd3M9JWQgcmVzdWx0X3Jvd3M9JWQgc2VlZGxvZz0l
ZCIgJSAoYXJtLCBsZW4ocm93cyksIGxlbihyZXMpLCBsZW4oc2VlZHMpKSkKcHJpbnQoInRyZWF0bWVudCBkZXB0aD0lciBhY2M9
JXIgY2FwPSVyIHRvcG49JXIgdG9wbT0lciIgJSAoCiAgICByb3dzWzBdLmdldCgic2VhcmNoX2RlcHRoIiksIHJvd3NbMF0uZ2V0
KCJhY2N1cmFjeV9tb2RlIiksIHJvd3NbMF0uZ2V0KCJhY2N1cmFjeV9icmFuY2hfY2FwIiksCiAgICByb3dzWzBdLmdldCgic2Vh
cmNoX3RvcG5fcmVxdWVzdGVkIiksIHJvd3NbMF0uZ2V0KCJzZWFyY2hfdG9wbV9yZXF1ZXN0ZWQiKSkpCnByaW50KCJjb25maWdf
aGFzaCBwcm9maWxlPSVzIG1hbmlmZXN0PSVzIGV4cGVjdGVkPSVzIiAlICgKICAgIHNvcnRlZChjZmdzKSwgbWFuLmdldCgiY29u
ZmlnX2hhc2giKSwgZXhwWyJjZmciXSkpCnByaW50KCJkZXB0aDJfZnJvbnRpZXI6ICVkLyVkIHJvd3MgPiAwIChtYXggJXMpIiAl
IChuX3BvcywgbGVuKHJvd3MpLCBtYXgoZnJvbnRpZXJzKSBpZiBmcm9udGllcnMgZWxzZSAwKSkKcHJpbnQoImJhY2tlbmRfY2xh
c3M9JXMgIG1lYXN1cmVkX21zIHA1MD0lLjFmIHA5NT0lLjFmIG1heD0lLjFmIiAlICgKICAgIHNvcnRlZChjbGFzc2VzKSwgcDUw
IG9yIDAsIHA5NSBvciAwLCBtc1stMV0gaWYgbXMgZWxzZSAwKSkKaWYgZmFpbHM6CiAgICBwcmludCgiUE9TVC1BUk0gR0FURSBG
QUlMRUQ6IikKICAgIGZvciBmIGluIGZhaWxzOgogICAgICAgIHByaW50KCIgIC0gJXMiICUgZikKICAgIHN5cy5leGl0KDIpCnBy
aW50KCJQT1NULUFSTSBHQVRFIFBBU1NFRCIpCg==
```

---

## `cross_arm6.py`

Cross-arm validation (§11.3, §11.4), output completeness (§10) and the SHA-256 freeze.

Raw bytes: 4545 &middot; SHA-256 `1e576544e5f802c2050012878e3d7e3e025d7ecdafb6234df2b8fca36cf76c8b`

### Readable form (line-normalised — not authoritative)

```python
"""Cross-arm validation (§11.3) then output completeness + immutable hashes (§10, §11.3 #13)."""
import collections, hashlib, json, os, sys

OUT = r"C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt6"
ARMS = ["d1_acc_off", "d1_acc_on", "d2_acc_off", "d2_acc_on"]
EXPECTED_CFG = {
    "d1_acc_off": "03d2d5ee27911fc4",
    "d1_acc_on":  "50cf67d5b04a1b04",
    "d2_acc_off": "b4c98c07c32f3f9f",
    "d2_acc_on":  "68e04be0173586b2",
}
EMPTY_ENV_CFG = "594295543f13a55d"
GIT_SHA = "d64982ae9fdba6a877c8c2b7e804923ebcc7fec4"
SHOWDOWN_COMMIT = "f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5"
PATCH_HASH = "86e31891547e87da"

fails = []
mans, profs, ress = {}, {}, {}
for a in ARMS:
    rp = os.path.join(OUT, "cost_preflight_%s_result.jsonl" % a)
    mans[a] = json.load(open(rp + ".manifest.json", encoding="utf-8-sig"))
    profs[a] = [json.loads(l) for l in open(
        os.path.join(OUT, "cost_preflight_%s_profile.jsonl" % a), encoding="utf-8") if l.strip()]
    ress[a] = [json.loads(l) for l in open(rp, encoding="utf-8") if l.strip()]

print("=== §11.3 #14/#15  exact config_hash assignment ===")
for a in ARMS:
    want = EXPECTED_CFG[a]
    mh = mans[a].get("config_hash")
    ph = {r.get("config_hash") for r in profs[a]}
    ok = (mh == want) and (ph == {want})
    print("  %-11s manifest=%s  profile=%s  expected=%s  %s" % (
        a, mh, sorted(ph), want, "OK" if ok else "MISMATCH"))
    if not ok:
        fails.append("%s config_hash assignment" % a)
    if want == EMPTY_ENV_CFG or mh == EMPTY_ENV_CFG:
        fails.append("%s carries the empty-behavior_env hash" % a)
seen = [mans[a].get("config_hash") for a in ARMS]
print("  distinct across arms: %d/4" % len(set(seen)))
if len(set(seen)) != 4:
    fails.append("config_hash values not distinct across arms")

print("=== §11.3 #10  identical battle_id sets ===")
bsets = {a: {r.get("battle_id") for r in ress[a]} for a in ARMS}
base = bsets[ARMS[0]]
for a in ARMS:
    same = bsets[a] == base
    print("  %-11s n=%d  identical_to_arm1=%s" % (a, len(bsets[a]), same))
    if not same:
        fails.append("%s battle_id set differs" % a)

print("=== §11.3 #11/#12  shared schedule/panel/seed + provenance ===")
for field, want in (("schedule_hash", "b6f5910e4bc3c584"), ("panel_hash", "aac1ea30446fde88"),
                    ("seed_base", "champions-panel-v0-d2-cost-preflight"),
                    ("git_sha", GIT_SHA), ("showdown_commit", SHOWDOWN_COMMIT),
                    ("server_patch_hash", PATCH_HASH), ("pythonhashseed", "0")):
    vals = {a: mans[a].get(field) for a in ARMS}
    uniq = set(vals.values())
    ok = (uniq == {want})
    print("  %-18s %s  %s" % (field, sorted(uniq), "OK" if ok else "MISMATCH expected %r" % want))
    if not ok:
        fails.append("%s: %s" % (field, sorted(uniq)))
    dirty = {a: mans[a].get("dirty") for a in ARMS}
    if field == "git_sha" and any(dirty.values()):
        fails.append("dirty manifest: %s" % dirty)
# profile-row git_sha too
for a in ARMS:
    s = {r.get("git_sha") for r in profs[a]}
    if s != {GIT_SHA}:
        fails.append("%s profile git_sha %s" % (a, sorted(s)))

print("=== §11.4  cache-class ===")
for a in ARMS:
    cl = collections.Counter(r.get("backend_class") for r in profs[a])
    bad = set(cl) - {"clean_cold", "clean_warm"}
    print("  %-11s %s%s" % (a, dict(cl), "  CONTAMINATED" if bad else ""))
    if bad:
        fails.append("%s contaminated backend_class %s" % (a, sorted(bad)))

print("=== §10  output completeness ===")
files = sorted(f for f in os.listdir(OUT) if os.path.isfile(os.path.join(OUT, f)))
expected = {"operator-preflight.json"}
for a in ARMS:
    expected |= {
        "cost_preflight_%s_result.jsonl" % a,
        "cost_preflight_%s_result.jsonl.manifest.json" % a,
        "cost_preflight_%s_profile.jsonl" % a,
        "cost_preflight_%s_seedlog.jsonl" % a,
        "operator-server-%s.json" % a,
    }
missing = sorted(expected - set(files))
extra = sorted(set(files) - expected)
print("  found %d files (expected 21); missing=%s extra=%s" % (len(files), missing, extra))
if len(files) != 21 or missing:
    fails.append("output inventory: %d files, missing %s, extra %s" % (len(files), missing, extra))

print("=== §11.3 #13  immutable SHA-256 ===")
for f in files:
    h = hashlib.sha256(open(os.path.join(OUT, f), "rb").read()).hexdigest()
    print("| `%s` | `%s` |" % (f, h))

print()
if fails:
    print("CROSS-ARM VALIDATION FAILED:")
    for f in fails:
        print("  - %s" % f)
    sys.exit(2)
print("CROSS-ARM VALIDATION PASSED")
```

### Raw bytes, Base64 (authoritative)

```text
IiIiQ3Jvc3MtYXJtIHZhbGlkYXRpb24gKMKnMTEuMykgdGhlbiBvdXRwdXQgY29tcGxldGVuZXNzICsgaW1tdXRhYmxlIGhhc2hl
cyAowqcxMCwgwqcxMS4zICMxMykuIiIiCmltcG9ydCBjb2xsZWN0aW9ucywgaGFzaGxpYiwganNvbiwgb3MsIHN5cwoKT1VUID0g
ciJDOlxVc2Vyc1xjaHJpc1xEb2N1bWVudHNcY29zdC1wcmVmbGlnaHQtZDItZDY0OTgyYS1hdHRlbXB0NiIKQVJNUyA9IFsiZDFf
YWNjX29mZiIsICJkMV9hY2Nfb24iLCAiZDJfYWNjX29mZiIsICJkMl9hY2Nfb24iXQpFWFBFQ1RFRF9DRkcgPSB7CiAgICAiZDFf
YWNjX29mZiI6ICIwM2QyZDVlZTI3OTExZmM0IiwKICAgICJkMV9hY2Nfb24iOiAgIjUwY2Y2N2Q1YjA0YTFiMDQiLAogICAgImQy
X2FjY19vZmYiOiAiYjRjOThjMDdjMzJmM2Y5ZiIsCiAgICAiZDJfYWNjX29uIjogICI2OGUwNGJlMDE3MzU4NmIyIiwKfQpFTVBU
WV9FTlZfQ0ZHID0gIjU5NDI5NTU0M2YxM2E1NWQiCkdJVF9TSEEgPSAiZDY0OTgyYWU5ZmRiYTZhODc3YzhjMmI3ZTgwNDkyM2Vi
Y2M3ZmVjNCIKU0hPV0RPV05fQ09NTUlUID0gImY4YWMxNDAwM2E1ZjI3ZTFiZGM4ZDhjNTk2MDhhNzczYzFjYjk2ZTUiClBBVENI
X0hBU0ggPSAiODZlMzE4OTE1NDdlODdkYSIKCmZhaWxzID0gW10KbWFucywgcHJvZnMsIHJlc3MgPSB7fSwge30sIHt9CmZvciBh
IGluIEFSTVM6CiAgICBycCA9IG9zLnBhdGguam9pbihPVVQsICJjb3N0X3ByZWZsaWdodF8lc19yZXN1bHQuanNvbmwiICUgYSkK
ICAgIG1hbnNbYV0gPSBqc29uLmxvYWQob3BlbihycCArICIubWFuaWZlc3QuanNvbiIsIGVuY29kaW5nPSJ1dGYtOC1zaWciKSkK
ICAgIHByb2ZzW2FdID0gW2pzb24ubG9hZHMobCkgZm9yIGwgaW4gb3BlbigKICAgICAgICBvcy5wYXRoLmpvaW4oT1VULCAiY29z
dF9wcmVmbGlnaHRfJXNfcHJvZmlsZS5qc29ubCIgJSBhKSwgZW5jb2Rpbmc9InV0Zi04IikgaWYgbC5zdHJpcCgpXQogICAgcmVz
c1thXSA9IFtqc29uLmxvYWRzKGwpIGZvciBsIGluIG9wZW4ocnAsIGVuY29kaW5nPSJ1dGYtOCIpIGlmIGwuc3RyaXAoKV0KCnBy
aW50KCI9PT0gwqcxMS4zICMxNC8jMTUgIGV4YWN0IGNvbmZpZ19oYXNoIGFzc2lnbm1lbnQgPT09IikKZm9yIGEgaW4gQVJNUzoK
ICAgIHdhbnQgPSBFWFBFQ1RFRF9DRkdbYV0KICAgIG1oID0gbWFuc1thXS5nZXQoImNvbmZpZ19oYXNoIikKICAgIHBoID0ge3Iu
Z2V0KCJjb25maWdfaGFzaCIpIGZvciByIGluIHByb2ZzW2FdfQogICAgb2sgPSAobWggPT0gd2FudCkgYW5kIChwaCA9PSB7d2Fu
dH0pCiAgICBwcmludCgiICAlLTExcyBtYW5pZmVzdD0lcyAgcHJvZmlsZT0lcyAgZXhwZWN0ZWQ9JXMgICVzIiAlICgKICAgICAg
ICBhLCBtaCwgc29ydGVkKHBoKSwgd2FudCwgIk9LIiBpZiBvayBlbHNlICJNSVNNQVRDSCIpKQogICAgaWYgbm90IG9rOgogICAg
ICAgIGZhaWxzLmFwcGVuZCgiJXMgY29uZmlnX2hhc2ggYXNzaWdubWVudCIgJSBhKQogICAgaWYgd2FudCA9PSBFTVBUWV9FTlZf
Q0ZHIG9yIG1oID09IEVNUFRZX0VOVl9DRkc6CiAgICAgICAgZmFpbHMuYXBwZW5kKCIlcyBjYXJyaWVzIHRoZSBlbXB0eS1iZWhh
dmlvcl9lbnYgaGFzaCIgJSBhKQpzZWVuID0gW21hbnNbYV0uZ2V0KCJjb25maWdfaGFzaCIpIGZvciBhIGluIEFSTVNdCnByaW50
KCIgIGRpc3RpbmN0IGFjcm9zcyBhcm1zOiAlZC80IiAlIGxlbihzZXQoc2VlbikpKQppZiBsZW4oc2V0KHNlZW4pKSAhPSA0Ogog
ICAgZmFpbHMuYXBwZW5kKCJjb25maWdfaGFzaCB2YWx1ZXMgbm90IGRpc3RpbmN0IGFjcm9zcyBhcm1zIikKCnByaW50KCI9PT0g
wqcxMS4zICMxMCAgaWRlbnRpY2FsIGJhdHRsZV9pZCBzZXRzID09PSIpCmJzZXRzID0ge2E6IHtyLmdldCgiYmF0dGxlX2lkIikg
Zm9yIHIgaW4gcmVzc1thXX0gZm9yIGEgaW4gQVJNU30KYmFzZSA9IGJzZXRzW0FSTVNbMF1dCmZvciBhIGluIEFSTVM6CiAgICBz
YW1lID0gYnNldHNbYV0gPT0gYmFzZQogICAgcHJpbnQoIiAgJS0xMXMgbj0lZCAgaWRlbnRpY2FsX3RvX2FybTE9JXMiICUgKGEs
IGxlbihic2V0c1thXSksIHNhbWUpKQogICAgaWYgbm90IHNhbWU6CiAgICAgICAgZmFpbHMuYXBwZW5kKCIlcyBiYXR0bGVfaWQg
c2V0IGRpZmZlcnMiICUgYSkKCnByaW50KCI9PT0gwqcxMS4zICMxMS8jMTIgIHNoYXJlZCBzY2hlZHVsZS9wYW5lbC9zZWVkICsg
cHJvdmVuYW5jZSA9PT0iKQpmb3IgZmllbGQsIHdhbnQgaW4gKCgic2NoZWR1bGVfaGFzaCIsICJiNmY1OTEwZTRiYzNjNTg0Iiks
ICgicGFuZWxfaGFzaCIsICJhYWMxZWEzMDQ0NmZkZTg4IiksCiAgICAgICAgICAgICAgICAgICAgKCJzZWVkX2Jhc2UiLCAiY2hh
bXBpb25zLXBhbmVsLXYwLWQyLWNvc3QtcHJlZmxpZ2h0IiksCiAgICAgICAgICAgICAgICAgICAgKCJnaXRfc2hhIiwgR0lUX1NI
QSksICgic2hvd2Rvd25fY29tbWl0IiwgU0hPV0RPV05fQ09NTUlUKSwKICAgICAgICAgICAgICAgICAgICAoInNlcnZlcl9wYXRj
aF9oYXNoIiwgUEFUQ0hfSEFTSCksICgicHl0aG9uaGFzaHNlZWQiLCAiMCIpKToKICAgIHZhbHMgPSB7YTogbWFuc1thXS5nZXQo
ZmllbGQpIGZvciBhIGluIEFSTVN9CiAgICB1bmlxID0gc2V0KHZhbHMudmFsdWVzKCkpCiAgICBvayA9ICh1bmlxID09IHt3YW50
fSkKICAgIHByaW50KCIgICUtMThzICVzICAlcyIgJSAoZmllbGQsIHNvcnRlZCh1bmlxKSwgIk9LIiBpZiBvayBlbHNlICJNSVNN
QVRDSCBleHBlY3RlZCAlciIgJSB3YW50KSkKICAgIGlmIG5vdCBvazoKICAgICAgICBmYWlscy5hcHBlbmQoIiVzOiAlcyIgJSAo
ZmllbGQsIHNvcnRlZCh1bmlxKSkpCiAgICBkaXJ0eSA9IHthOiBtYW5zW2FdLmdldCgiZGlydHkiKSBmb3IgYSBpbiBBUk1TfQog
ICAgaWYgZmllbGQgPT0gImdpdF9zaGEiIGFuZCBhbnkoZGlydHkudmFsdWVzKCkpOgogICAgICAgIGZhaWxzLmFwcGVuZCgiZGly
dHkgbWFuaWZlc3Q6ICVzIiAlIGRpcnR5KQojIHByb2ZpbGUtcm93IGdpdF9zaGEgdG9vCmZvciBhIGluIEFSTVM6CiAgICBzID0g
e3IuZ2V0KCJnaXRfc2hhIikgZm9yIHIgaW4gcHJvZnNbYV19CiAgICBpZiBzICE9IHtHSVRfU0hBfToKICAgICAgICBmYWlscy5h
cHBlbmQoIiVzIHByb2ZpbGUgZ2l0X3NoYSAlcyIgJSAoYSwgc29ydGVkKHMpKSkKCnByaW50KCI9PT0gwqcxMS40ICBjYWNoZS1j
bGFzcyA9PT0iKQpmb3IgYSBpbiBBUk1TOgogICAgY2wgPSBjb2xsZWN0aW9ucy5Db3VudGVyKHIuZ2V0KCJiYWNrZW5kX2NsYXNz
IikgZm9yIHIgaW4gcHJvZnNbYV0pCiAgICBiYWQgPSBzZXQoY2wpIC0geyJjbGVhbl9jb2xkIiwgImNsZWFuX3dhcm0ifQogICAg
cHJpbnQoIiAgJS0xMXMgJXMlcyIgJSAoYSwgZGljdChjbCksICIgIENPTlRBTUlOQVRFRCIgaWYgYmFkIGVsc2UgIiIpKQogICAg
aWYgYmFkOgogICAgICAgIGZhaWxzLmFwcGVuZCgiJXMgY29udGFtaW5hdGVkIGJhY2tlbmRfY2xhc3MgJXMiICUgKGEsIHNvcnRl
ZChiYWQpKSkKCnByaW50KCI9PT0gwqcxMCAgb3V0cHV0IGNvbXBsZXRlbmVzcyA9PT0iKQpmaWxlcyA9IHNvcnRlZChmIGZvciBm
IGluIG9zLmxpc3RkaXIoT1VUKSBpZiBvcy5wYXRoLmlzZmlsZShvcy5wYXRoLmpvaW4oT1VULCBmKSkpCmV4cGVjdGVkID0geyJv
cGVyYXRvci1wcmVmbGlnaHQuanNvbiJ9CmZvciBhIGluIEFSTVM6CiAgICBleHBlY3RlZCB8PSB7CiAgICAgICAgImNvc3RfcHJl
ZmxpZ2h0XyVzX3Jlc3VsdC5qc29ubCIgJSBhLAogICAgICAgICJjb3N0X3ByZWZsaWdodF8lc19yZXN1bHQuanNvbmwubWFuaWZl
c3QuanNvbiIgJSBhLAogICAgICAgICJjb3N0X3ByZWZsaWdodF8lc19wcm9maWxlLmpzb25sIiAlIGEsCiAgICAgICAgImNvc3Rf
cHJlZmxpZ2h0XyVzX3NlZWRsb2cuanNvbmwiICUgYSwKICAgICAgICAib3BlcmF0b3Itc2VydmVyLSVzLmpzb24iICUgYSwKICAg
IH0KbWlzc2luZyA9IHNvcnRlZChleHBlY3RlZCAtIHNldChmaWxlcykpCmV4dHJhID0gc29ydGVkKHNldChmaWxlcykgLSBleHBl
Y3RlZCkKcHJpbnQoIiAgZm91bmQgJWQgZmlsZXMgKGV4cGVjdGVkIDIxKTsgbWlzc2luZz0lcyBleHRyYT0lcyIgJSAobGVuKGZp
bGVzKSwgbWlzc2luZywgZXh0cmEpKQppZiBsZW4oZmlsZXMpICE9IDIxIG9yIG1pc3Npbmc6CiAgICBmYWlscy5hcHBlbmQoIm91
dHB1dCBpbnZlbnRvcnk6ICVkIGZpbGVzLCBtaXNzaW5nICVzLCBleHRyYSAlcyIgJSAobGVuKGZpbGVzKSwgbWlzc2luZywgZXh0
cmEpKQoKcHJpbnQoIj09PSDCpzExLjMgIzEzICBpbW11dGFibGUgU0hBLTI1NiA9PT0iKQpmb3IgZiBpbiBmaWxlczoKICAgIGgg
PSBoYXNobGliLnNoYTI1NihvcGVuKG9zLnBhdGguam9pbihPVVQsIGYpLCAicmIiKS5yZWFkKCkpLmhleGRpZ2VzdCgpCiAgICBw
cmludCgifCBgJXNgIHwgYCVzYCB8IiAlIChmLCBoKSkKCnByaW50KCkKaWYgZmFpbHM6CiAgICBwcmludCgiQ1JPU1MtQVJNIFZB
TElEQVRJT04gRkFJTEVEOiIpCiAgICBmb3IgZiBpbiBmYWlsczoKICAgICAgICBwcmludCgiICAtICVzIiAlIGYpCiAgICBzeXMu
ZXhpdCgyKQpwcmludCgiQ1JPU1MtQVJNIFZBTElEQVRJT04gUEFTU0VEIikK
```

---

## `evidence6.py`

Generates the §12 per-arm × per-stratum tables. Imports `_percentile` from `run_cap_latency_sweep.py`.

Raw bytes: 3781 &middot; SHA-256 `a1f896c8a7c202e671b216a8c6703b524af40dd9f01e37de4ea5004c8593af05`

### Readable form (line-normalised — not authoritative)

```python
"""Full §12 evidence per arm x backend_class stratum, using the project's own _percentile."""
import collections, importlib.util, json, os

CAND = r"C:\Users\chris\Documents\cost-preflight-worktree-d64982a"
OUT = r"C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt6"
ARMS = ["d1_acc_off", "d1_acc_on", "d2_acc_off", "d2_acc_on"]

spec = importlib.util.spec_from_file_location(
    "sweep", os.path.join(CAND, "showdown_bot", "scripts", "run_cap_latency_sweep.py"))
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
P = sweep._percentile
print("percentile source: %s" % sweep.__file__)
import inspect
print("".join(inspect.getsource(P).splitlines(keepends=True)[:3]).rstrip())
print()

SUM = ("turn1_accuracy_leaf_count", "turn2_accuracy_leaf_count",
       "turn1_accuracy_cap_hits", "turn2_accuracy_cap_hits",
       "depth2_candidates_selected", "depth2_response_slots_eligible",
       "transport_calls", "transport_attempts", "spawn_calls",
       "requests_total", "requests_unique", "cache_hits")

for a in ARMS:
    rows = [json.loads(l) for l in open(
        os.path.join(OUT, "cost_preflight_%s_profile.jsonl" % a), encoding="utf-8") if l.strip()]
    res = [json.loads(l) for l in open(
        os.path.join(OUT, "cost_preflight_%s_result.jsonl" % a), encoding="utf-8") if l.strip()]
    man = json.load(open(os.path.join(
        OUT, "cost_preflight_%s_result.jsonl.manifest.json" % a), encoding="utf-8-sig"))

    timeouts = sum(1 for r in res if (r.get("end_reason") or "") == "timeout")
    print("### %s   config_hash=%s  git_sha=%s" % (a, man["config_hash"], man["git_sha"][:12]))
    print("    battles=%d  timeouts(end_reason==timeout)=%d  crashes=%d  invalid=%d"
          % (len(res), timeouts,
             sum(r.get("crashes") or 0 for r in res), sum(r.get("invalid") or 0 for r in res)))

    by = collections.defaultdict(list)
    for r in rows:
        by[r["backend_class"]].append(r)
    for cls in ("clean_cold", "clean_warm"):
        g = by.get(cls, [])
        ms = sorted(r["measured_ms"] for r in g if r.get("measured_ms") is not None)
        bat = {r["battle_id"] for r in g}
        fb = sum(1 for r in g if r.get("selection_stage") != "heuristic"
                 or r.get("fallback_reason") is not None)
        degr = sum(1 for r in g if r.get("degraded") or r.get("degradation_reason"))
        capfb = sum(1 for r in g if r.get("turn1_accuracy_cap_fallback")
                    or r.get("turn2_accuracy_cap_fallback"))
        tot = {k: sum(r.get(k) or 0 for r in g) for k in SUM}
        topn = sorted({r.get("search_topn_requested") for r in g})
        topm = sorted({r.get("search_topm_requested") for r in g})
        fr = [r.get("depth2_frontier") or 0 for r in g]
        print("  [%s] obs=%d battles=%d | p50=%.1f p95=%.1f max=%.1f" % (
            cls, len(g), len(bat), P(ms, 0.5), P(ms, 0.95), ms[-1] if ms else 0))
        print("        chooser_fallback=%d degradation=%d cap_fallback=%d" % (fb, degr, capfb))
        print("        topn=%s topm=%s frontier>0=%d max_frontier=%d" % (
            topn, topm, sum(1 for f in fr if f > 0), max(fr) if fr else 0))
        print("        acc_leaf t1=%d t2=%d | cap_hits t1=%d t2=%d | d2_cand=%d d2_slots=%d" % (
            tot["turn1_accuracy_leaf_count"], tot["turn2_accuracy_leaf_count"],
            tot["turn1_accuracy_cap_hits"], tot["turn2_accuracy_cap_hits"],
            tot["depth2_candidates_selected"], tot["depth2_response_slots_eligible"]))
        print("        calc: transport_calls=%d attempts=%d spawn=%d req_total=%d req_uniq=%d cache_hits=%d" % (
            tot["transport_calls"], tot["transport_attempts"], tot["spawn_calls"],
            tot["requests_total"], tot["requests_unique"], tot["cache_hits"]))
    print()
```

### Raw bytes, Base64 (authoritative)

```text
IiIiRnVsbCDCpzEyIGV2aWRlbmNlIHBlciBhcm0geCBiYWNrZW5kX2NsYXNzIHN0cmF0dW0sIHVzaW5nIHRoZSBwcm9qZWN0J3Mg
b3duIF9wZXJjZW50aWxlLiIiIgppbXBvcnQgY29sbGVjdGlvbnMsIGltcG9ydGxpYi51dGlsLCBqc29uLCBvcwoKQ0FORCA9IHIi
QzpcVXNlcnNcY2hyaXNcRG9jdW1lbnRzXGNvc3QtcHJlZmxpZ2h0LXdvcmt0cmVlLWQ2NDk4MmEiCk9VVCA9IHIiQzpcVXNlcnNc
Y2hyaXNcRG9jdW1lbnRzXGNvc3QtcHJlZmxpZ2h0LWQyLWQ2NDk4MmEtYXR0ZW1wdDYiCkFSTVMgPSBbImQxX2FjY19vZmYiLCAi
ZDFfYWNjX29uIiwgImQyX2FjY19vZmYiLCAiZDJfYWNjX29uIl0KCnNwZWMgPSBpbXBvcnRsaWIudXRpbC5zcGVjX2Zyb21fZmls
ZV9sb2NhdGlvbigKICAgICJzd2VlcCIsIG9zLnBhdGguam9pbihDQU5ELCAic2hvd2Rvd25fYm90IiwgInNjcmlwdHMiLCAicnVu
X2NhcF9sYXRlbmN5X3N3ZWVwLnB5IikpCnN3ZWVwID0gaW1wb3J0bGliLnV0aWwubW9kdWxlX2Zyb21fc3BlYyhzcGVjKQpzcGVj
LmxvYWRlci5leGVjX21vZHVsZShzd2VlcCkKUCA9IHN3ZWVwLl9wZXJjZW50aWxlCnByaW50KCJwZXJjZW50aWxlIHNvdXJjZTog
JXMiICUgc3dlZXAuX19maWxlX18pCmltcG9ydCBpbnNwZWN0CnByaW50KCIiLmpvaW4oaW5zcGVjdC5nZXRzb3VyY2UoUCkuc3Bs
aXRsaW5lcyhrZWVwZW5kcz1UcnVlKVs6M10pLnJzdHJpcCgpKQpwcmludCgpCgpTVU0gPSAoInR1cm4xX2FjY3VyYWN5X2xlYWZf
Y291bnQiLCAidHVybjJfYWNjdXJhY3lfbGVhZl9jb3VudCIsCiAgICAgICAidHVybjFfYWNjdXJhY3lfY2FwX2hpdHMiLCAidHVy
bjJfYWNjdXJhY3lfY2FwX2hpdHMiLAogICAgICAgImRlcHRoMl9jYW5kaWRhdGVzX3NlbGVjdGVkIiwgImRlcHRoMl9yZXNwb25z
ZV9zbG90c19lbGlnaWJsZSIsCiAgICAgICAidHJhbnNwb3J0X2NhbGxzIiwgInRyYW5zcG9ydF9hdHRlbXB0cyIsICJzcGF3bl9j
YWxscyIsCiAgICAgICAicmVxdWVzdHNfdG90YWwiLCAicmVxdWVzdHNfdW5pcXVlIiwgImNhY2hlX2hpdHMiKQoKZm9yIGEgaW4g
QVJNUzoKICAgIHJvd3MgPSBbanNvbi5sb2FkcyhsKSBmb3IgbCBpbiBvcGVuKAogICAgICAgIG9zLnBhdGguam9pbihPVVQsICJj
b3N0X3ByZWZsaWdodF8lc19wcm9maWxlLmpzb25sIiAlIGEpLCBlbmNvZGluZz0idXRmLTgiKSBpZiBsLnN0cmlwKCldCiAgICBy
ZXMgPSBbanNvbi5sb2FkcyhsKSBmb3IgbCBpbiBvcGVuKAogICAgICAgIG9zLnBhdGguam9pbihPVVQsICJjb3N0X3ByZWZsaWdo
dF8lc19yZXN1bHQuanNvbmwiICUgYSksIGVuY29kaW5nPSJ1dGYtOCIpIGlmIGwuc3RyaXAoKV0KICAgIG1hbiA9IGpzb24ubG9h
ZChvcGVuKG9zLnBhdGguam9pbigKICAgICAgICBPVVQsICJjb3N0X3ByZWZsaWdodF8lc19yZXN1bHQuanNvbmwubWFuaWZlc3Qu
anNvbiIgJSBhKSwgZW5jb2Rpbmc9InV0Zi04LXNpZyIpKQoKICAgIHRpbWVvdXRzID0gc3VtKDEgZm9yIHIgaW4gcmVzIGlmIChy
LmdldCgiZW5kX3JlYXNvbiIpIG9yICIiKSA9PSAidGltZW91dCIpCiAgICBwcmludCgiIyMjICVzICAgY29uZmlnX2hhc2g9JXMg
IGdpdF9zaGE9JXMiICUgKGEsIG1hblsiY29uZmlnX2hhc2giXSwgbWFuWyJnaXRfc2hhIl1bOjEyXSkpCiAgICBwcmludCgiICAg
IGJhdHRsZXM9JWQgIHRpbWVvdXRzKGVuZF9yZWFzb249PXRpbWVvdXQpPSVkICBjcmFzaGVzPSVkICBpbnZhbGlkPSVkIgogICAg
ICAgICAgJSAobGVuKHJlcyksIHRpbWVvdXRzLAogICAgICAgICAgICAgc3VtKHIuZ2V0KCJjcmFzaGVzIikgb3IgMCBmb3IgciBp
biByZXMpLCBzdW0oci5nZXQoImludmFsaWQiKSBvciAwIGZvciByIGluIHJlcykpKQoKICAgIGJ5ID0gY29sbGVjdGlvbnMuZGVm
YXVsdGRpY3QobGlzdCkKICAgIGZvciByIGluIHJvd3M6CiAgICAgICAgYnlbclsiYmFja2VuZF9jbGFzcyJdXS5hcHBlbmQocikK
ICAgIGZvciBjbHMgaW4gKCJjbGVhbl9jb2xkIiwgImNsZWFuX3dhcm0iKToKICAgICAgICBnID0gYnkuZ2V0KGNscywgW10pCiAg
ICAgICAgbXMgPSBzb3J0ZWQoclsibWVhc3VyZWRfbXMiXSBmb3IgciBpbiBnIGlmIHIuZ2V0KCJtZWFzdXJlZF9tcyIpIGlzIG5v
dCBOb25lKQogICAgICAgIGJhdCA9IHtyWyJiYXR0bGVfaWQiXSBmb3IgciBpbiBnfQogICAgICAgIGZiID0gc3VtKDEgZm9yIHIg
aW4gZyBpZiByLmdldCgic2VsZWN0aW9uX3N0YWdlIikgIT0gImhldXJpc3RpYyIKICAgICAgICAgICAgICAgICBvciByLmdldCgi
ZmFsbGJhY2tfcmVhc29uIikgaXMgbm90IE5vbmUpCiAgICAgICAgZGVnciA9IHN1bSgxIGZvciByIGluIGcgaWYgci5nZXQoImRl
Z3JhZGVkIikgb3Igci5nZXQoImRlZ3JhZGF0aW9uX3JlYXNvbiIpKQogICAgICAgIGNhcGZiID0gc3VtKDEgZm9yIHIgaW4gZyBp
ZiByLmdldCgidHVybjFfYWNjdXJhY3lfY2FwX2ZhbGxiYWNrIikKICAgICAgICAgICAgICAgICAgICBvciByLmdldCgidHVybjJf
YWNjdXJhY3lfY2FwX2ZhbGxiYWNrIikpCiAgICAgICAgdG90ID0ge2s6IHN1bShyLmdldChrKSBvciAwIGZvciByIGluIGcpIGZv
ciBrIGluIFNVTX0KICAgICAgICB0b3BuID0gc29ydGVkKHtyLmdldCgic2VhcmNoX3RvcG5fcmVxdWVzdGVkIikgZm9yIHIgaW4g
Z30pCiAgICAgICAgdG9wbSA9IHNvcnRlZCh7ci5nZXQoInNlYXJjaF90b3BtX3JlcXVlc3RlZCIpIGZvciByIGluIGd9KQogICAg
ICAgIGZyID0gW3IuZ2V0KCJkZXB0aDJfZnJvbnRpZXIiKSBvciAwIGZvciByIGluIGddCiAgICAgICAgcHJpbnQoIiAgWyVzXSBv
YnM9JWQgYmF0dGxlcz0lZCB8IHA1MD0lLjFmIHA5NT0lLjFmIG1heD0lLjFmIiAlICgKICAgICAgICAgICAgY2xzLCBsZW4oZyks
IGxlbihiYXQpLCBQKG1zLCAwLjUpLCBQKG1zLCAwLjk1KSwgbXNbLTFdIGlmIG1zIGVsc2UgMCkpCiAgICAgICAgcHJpbnQoIiAg
ICAgICAgY2hvb3Nlcl9mYWxsYmFjaz0lZCBkZWdyYWRhdGlvbj0lZCBjYXBfZmFsbGJhY2s9JWQiICUgKGZiLCBkZWdyLCBjYXBm
YikpCiAgICAgICAgcHJpbnQoIiAgICAgICAgdG9wbj0lcyB0b3BtPSVzIGZyb250aWVyPjA9JWQgbWF4X2Zyb250aWVyPSVkIiAl
ICgKICAgICAgICAgICAgdG9wbiwgdG9wbSwgc3VtKDEgZm9yIGYgaW4gZnIgaWYgZiA+IDApLCBtYXgoZnIpIGlmIGZyIGVsc2Ug
MCkpCiAgICAgICAgcHJpbnQoIiAgICAgICAgYWNjX2xlYWYgdDE9JWQgdDI9JWQgfCBjYXBfaGl0cyB0MT0lZCB0Mj0lZCB8IGQy
X2NhbmQ9JWQgZDJfc2xvdHM9JWQiICUgKAogICAgICAgICAgICB0b3RbInR1cm4xX2FjY3VyYWN5X2xlYWZfY291bnQiXSwgdG90
WyJ0dXJuMl9hY2N1cmFjeV9sZWFmX2NvdW50Il0sCiAgICAgICAgICAgIHRvdFsidHVybjFfYWNjdXJhY3lfY2FwX2hpdHMiXSwg
dG90WyJ0dXJuMl9hY2N1cmFjeV9jYXBfaGl0cyJdLAogICAgICAgICAgICB0b3RbImRlcHRoMl9jYW5kaWRhdGVzX3NlbGVjdGVk
Il0sIHRvdFsiZGVwdGgyX3Jlc3BvbnNlX3Nsb3RzX2VsaWdpYmxlIl0pKQogICAgICAgIHByaW50KCIgICAgICAgIGNhbGM6IHRy
YW5zcG9ydF9jYWxscz0lZCBhdHRlbXB0cz0lZCBzcGF3bj0lZCByZXFfdG90YWw9JWQgcmVxX3VuaXE9JWQgY2FjaGVfaGl0cz0l
ZCIgJSAoCiAgICAgICAgICAgIHRvdFsidHJhbnNwb3J0X2NhbGxzIl0sIHRvdFsidHJhbnNwb3J0X2F0dGVtcHRzIl0sIHRvdFsi
c3Bhd25fY2FsbHMiXSwKICAgICAgICAgICAgdG90WyJyZXF1ZXN0c190b3RhbCJdLCB0b3RbInJlcXVlc3RzX3VuaXF1ZSJdLCB0
b3RbImNhY2hlX2hpdHMiXSkpCiAgICBwcmludCgpCg==
```
