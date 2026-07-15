# Charizard-Mega-Y ground truth fixture

## Source

- Report: `reports/champions-pkmn-protocol-differential-audit.md` @ git `fc4f251`
- Showdown pin: `f8ac140` (`~/.cache/showdownbot/pokemon-showdown`)
- Extraction: manual transcription of §protocol_mega_line_ground_truth (audit lines 63–74) plus post-mega speed 122 from sim probe (`tools/_pkmn_differential_audit/out/_i7_timing_probe.mjs`, Charizard @ Charizardite Y, EVs 32 HP / 32 SpA / 2 Spe)

## Protocol ground truth

```text
|-mega|p1a: Charizard|Charizard|Charizardite Y
```

## Fixture SHA-256

```
2f7eca632b7ad3ae6ffa2b1375835574adce4ea2fdd2be8c45eb20de91685d23
```

Run `Get-FileHash tests/fixtures/i7a_charizard_mega_y_gt.json -Algorithm SHA256` to verify.
