"""Conflict heuristic for Russian names (patronymic, maiden surname in brackets).

Pairs taken from live pre-confirm flags of 2026-11-15..21.
"""
import pytest

from browser.smart_matches import _names_conflict

# Same person: the tree only lacks a surname, or the source adds a married/maiden one.
SAME = [
    ("Матрёна Ивановна Попова", "Матрёна Ивановна"),
    ("Миладора Демидовна Стеблинская (Толочко)", "Миладора Демидовна Толочко"),
    ("Мария Николаевна Киреева (Попова) (Фёдорова)", "Мария Николаевна Фёдорова"),
    ("Екатерина Фёдоровна (Ивановна) Толочко (Дыгало?)", "Екатерина Фёдоровна"),
    ("Пелагея Васильевна (Ермолаевна) Пушкарёва", "Пелагея Ермолаевна"),
    ("Мелания Ивановна Поликарпова (Фёдорова)", "Милания Ивановна Фёдорова"),
    ("Татьяна Яковлевна Полищук (Коблик(ова))", "Татьяна Яковлевна Кобликова"),
    ("Ганна Герасімовна Корнієнко (Зозуля)", "Ганна Герасимовна Зозуля"),
]

# Different people: must stay flagged.
DIFFERENT = [
    ("Николай Николаевич Ключко", "Николай Николаевич Глушков"),
    ("Надежда Петровна Наконечная", "Надежда Петровна Большакова"),
    ("Мария Борисовна Стеблинская", "Мария Борисовна Демидюк"),
    ("Анна Семёновна Стеблинская", "Анна Степановна Стеблинская"),
    ("Мария Ивановна", "Анна Ивановна Попова"),
    ("Анна Ивановна Попова", "Анна Петровна"),
    ("Екатерина Федосеевна Майорова", "Екатерина Фёдоровна"),
    ("Федір Корнієнко", "Григорий Корниенко"),
]


@pytest.mark.parametrize(("source", "tree"), SAME)
def test_same_person_is_not_a_conflict(source, tree):
    assert not _names_conflict(source, tree)


@pytest.mark.parametrize(("source", "tree"), DIFFERENT)
def test_different_people_stay_flagged(source, tree):
    assert _names_conflict(source, tree)
