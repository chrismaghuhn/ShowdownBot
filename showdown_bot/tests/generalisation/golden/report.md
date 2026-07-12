# Team- und Matchup-Generalisation

Status: `INCONCLUSIVE`

Analysis-ID: `7fa288b289bbd0c23c2af75c09152b5a12baf2cd7d4a0638a6c781c976cebed5`

## Coverage

| cell_id | n | complete |
|---|---:|---|
| 01e6998d32e39901ad46 | 2 | False |
| 0fb35d4d15e68af3285f | 2 | False |
| 102a906508626a69bc10 | 5 | False |
| 1fc1d5bc12733458c031 | 2 | False |
| 517f6aed8840b72f5f65 | 3 | False |
| 91ad28d83c26713f5434 | 2 | False |
| afe2bb8b476dc0c43c79 | 2 | False |
| b66912f5ba7772034888 | 2 | False |
| d9853857f87e3cb49e50 | 5 | False |
| de7cf93368718e8fb213 | 3 | False |
| e6ada5a1881bcbaeb9da | 5 | False |
| e75ad8989574b907851f | 5 | False |
| ec92376df39caadd9141 | 5 | False |
| f57a3c2162a379dc9293 | 5 | False |
| ff455e00de7fcd10c806 | 3 | False |

## Diagnostic slices

| dimension | value | n | win_rate | underpowered |
|---|---|---:|---:|---|
| hero_activated_speed_control | ["speed_reduction", "tailwind", "trick_room"] | 1 | 1.000000 | True |
| hero_activated_speed_control | ["speed_reduction", "tailwind"] | 8 | 0.500000 | True |
| hero_activated_speed_control | ["tailwind", "trick_room"] | 2 | 1.000000 | True |
| hero_activated_speed_control | ["tailwind"] | 33 | 0.181818 | False |
| hero_activated_speed_control | ["trick_room"] | 2 | 1.000000 | True |
| hero_activated_speed_control | [] | 5 | 0.400000 | True |
| hero_lead | ["incineroar", "rillaboom"] | 51 | 0.333333 | False |
| hero_side | p1 | 51 | 0.333333 | False |
| hero_static_speed_control | tailwind_only | 51 | 0.333333 | False |
| opponent_activated_speed_control | ["tailwind"] | 7 | 0.285714 | True |
| opponent_activated_speed_control | ["trick_room"] | 5 | 1.000000 | True |
| opponent_activated_speed_control | [] | 39 | 0.256410 | False |
| opponent_lead | ["incineroar", "pelipper"] | 17 | 0.235294 | False |
| opponent_lead | ["incineroar", "torkoal"] | 17 | 0.176471 | False |
| opponent_lead | ["indeedee", "incineroar"] | 17 | 0.588235 | False |
| opponent_static_speed_control | none | 17 | 0.176471 | False |
| opponent_static_speed_control | tailwind_only | 17 | 0.235294 | False |
| opponent_static_speed_control | trick_room_only | 17 | 0.588235 | False |

## Findings

- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `CELL_UNDERPOWERED`: cell is underpowered
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `REQUIRED_CELL_MISSING`: required cell is incomplete
- `WARN` `SIDE_GENERALISATION_NOT_EVALUABLE`: only one controlled side is unavailable
