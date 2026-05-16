import sys; sys.path.insert(0, "..")
from scoring import calculate_points, calculate_special_points

def test_exact_score_gives_3():
    assert calculate_points(2, 1, 2, 1) == 3

def test_correct_winner_gives_1():
    assert calculate_points(2, 0, 3, 0) == 1

def test_correct_draw_gives_1():
    assert calculate_points(1, 1, 2, 2) == 1

def test_wrong_result_gives_0():
    assert calculate_points(1, 0, 0, 1) == 0

def test_wrong_draw_gives_0():
    assert calculate_points(1, 0, 1, 1) == 0

def test_special_all_correct():
    assert calculate_special_points("Brasil","Argentina","Mbappe","Brasil","Argentina","Mbappe") == (5,3,2)

def test_special_all_wrong():
    assert calculate_special_points("Brasil","Argentina","Mbappe","Francia","España","Haaland") == (0,0,0)
