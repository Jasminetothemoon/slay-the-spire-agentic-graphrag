import unittest

from sts_advisor.knowledge import monsters

ACT1_ELITES_AND_BOSSES = ["GremlinNob", "Hexaghost", "Lagavulin", "Sentry", "SlimeBoss", "TheGuardian"]


class MonsterTableTest(unittest.TestCase):
    def test_covers_act1_elites_and_bosses(self):
        self.assertEqual(monsters.known_ids(), ACT1_ELITES_AND_BOSSES)

    def test_unknown_monster_returns_none(self):
        self.assertIsNone(monsters.lookup("NoSuchMonster"))
        self.assertIsNone(monsters.lookup("_about"))

    def test_about_states_source_and_check(self):
        about = monsters.about()
        for key in ("scope", "source", "checked"):
            self.assertTrue(about[key])

    def test_every_entry_is_complete(self):
        for monster_id in monsters.known_ids():
            with self.subTest(monster_id):
                entry = monsters.lookup(monster_id)
                self.assertEqual(entry["id"], monster_id)
                self.assertIn(entry["kind"], ("elite", "boss"))
                self.assertIn(entry["pattern_type"], ("scripted", "random"))
                low, high = entry["hp"]
                self.assertTrue(0 < low <= high)
                self.assertTrue(entry["pattern"] and entry["warnings"] and entry["moves"])
                for move in entry["moves"]:
                    self.assertTrue(move["name"])
                    # 每个招式要么有伤害，要么有效果说明
                    self.assertTrue("damage" in move or "effect" in move, move)
                    if "damage" in move:
                        self.assertIsInstance(move["damage"], int)
                        self.assertIsInstance(move["hits"], int)

    def test_values_checked_against_source(self):
        """抽查几个对出牌影响最大的数值，防止以后改数据时改错。"""
        nob = monsters.lookup("GremlinNob")
        self.assertEqual({m["name"]: m.get("damage") for m in nob["moves"]}, {"Bellow": None, "Rush": 14, "Skull Bash": 6})

        guardian = {m["name"]: m for m in monsters.lookup("TheGuardian")["moves"]}
        self.assertEqual((guardian["Fierce Bash"]["damage"], guardian["Whirlwind"]["hits"]), (32, 4))

        slime = {m["name"]: m for m in monsters.lookup("SlimeBoss")["moves"]}
        self.assertEqual(slime["Slam"]["damage"], 35)
        self.assertEqual(monsters.lookup("SlimeBoss")["hp"], [140, 140])

    def test_lookup_returns_a_copy(self):
        monsters.lookup("Sentry")["hp"] = None
        self.assertEqual(monsters.lookup("Sentry")["hp"], [38, 42])


if __name__ == "__main__":
    unittest.main()
