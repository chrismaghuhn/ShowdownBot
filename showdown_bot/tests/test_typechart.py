from showdown_bot.engine.typechart import effectiveness


def test_single_type_effectiveness():
    assert effectiveness("Fire", ["Grass"]) == 2.0
    assert effectiveness("Fire", ["Water"]) == 0.5
    assert effectiveness("Ground", ["Flying"]) == 0.0
    assert effectiveness("Electric", ["Ground"]) == 0.0
    assert effectiveness("Ghost", ["Normal"]) == 0.0
    assert effectiveness("Dragon", ["Fairy"]) == 0.0
    assert effectiveness("Normal", ["Normal"]) == 1.0  # neutral


def test_dual_type_effectiveness():
    assert effectiveness("Fire", ["Grass", "Steel"]) == 4.0       # Ferrothorn
    assert effectiveness("Ground", ["Fire", "Flying"]) == 0.0     # Charizard (immune via Flying)
    assert effectiveness("Rock", ["Fire", "Flying"]) == 4.0
    assert effectiveness("Water", ["Fire", "Ground"]) == 4.0
    assert effectiveness("Grass", ["Water", "Flying"]) == 1.0     # 2x * 0.5x


def test_case_insensitive_and_unknown():
    assert effectiveness("fire", ["grass"]) == 2.0
    assert effectiveness("Fire", []) == 1.0
    assert effectiveness("Bogus", ["Grass"]) == 1.0  # unknown type -> neutral
