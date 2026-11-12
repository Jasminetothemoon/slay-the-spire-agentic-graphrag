import copy
import unittest

from sts_advisor.ingest.visible_state import Decision, to_visible


def card(card_id, upgrades=0, uuid="u"):
    return {"id": card_id, "name": card_id, "upgrades": upgrades, "cost": 1, "uuid": uuid}


def combat_state(relic_ids=()):
    return {
        "in_game": True,
        "ready_for_command": True,
        "available_commands": ["play", "end"],
        "game_state": {
            "seed": 123456789,
            "class": "IRONCLAD",
            "floor": 3,
            "screen_type": "NONE",
            "room_phase": "COMBAT",
            "relics": [{"id": r, "name": r, "counter": -1} for r in relic_ids],
            "combat_state": {
                "turn": 1,
                "hand": [card("Strike_R", uuid="h1")],
                "draw_pile": [card("Defend_R", uuid="d1"), card("Bash", uuid="d2"), card("Anger", uuid="d3")],
                "discard_pile": [],
                "exhaust_pile": [],
                "monsters": [
                    {
                        "name": "Jaw Worm",
                        "current_hp": 40,
                        "intent": "ATTACK",
                        "move_id": 1,
                        "move_base_damage": 11,
                        "move_adjusted_damage": 11,
                        "move_hits": 1,
                        "last_move_id": 3,
                    }
                ],
            },
        },
    }


class VisibleStateTest(unittest.TestCase):
    def test_seed_is_removed(self):
        visible = to_visible(combat_state())
        self.assertNotIn("seed", visible.game)
        self.assertIn("seed", visible.filtered)

    def test_input_is_not_mutated(self):
        raw = combat_state()
        snapshot = copy.deepcopy(raw)
        to_visible(raw)
        self.assertEqual(raw, snapshot)

    def test_draw_pile_order_carries_no_information(self):
        raw_a = combat_state()
        raw_b = combat_state()
        raw_b["game_state"]["combat_state"]["draw_pile"].reverse()
        pile_a = to_visible(raw_a).combat["draw_pile"]
        pile_b = to_visible(raw_b).combat["draw_pile"]
        self.assertEqual(pile_a, pile_b)
        self.assertEqual(sorted(c["id"] for c in pile_a), ["Anger", "Bash", "Defend_R"])

    def test_frozen_eye_keeps_draw_order(self):
        raw = combat_state(relic_ids=["Frozen Eye"])
        visible = to_visible(raw)
        self.assertEqual(
            [c["id"] for c in visible.combat["draw_pile"]],
            [c["id"] for c in raw["game_state"]["combat_state"]["draw_pile"]],
        )
        self.assertNotIn("draw_pile_order", visible.filtered)

    def test_runic_dome_hides_intent_but_keeps_history(self):
        monster = to_visible(combat_state(relic_ids=["Runic Dome"])).combat["monsters"][0]
        self.assertEqual(monster["intent"], "UNKNOWN")
        for key in ("move_id", "move_base_damage", "move_adjusted_damage", "move_hits"):
            self.assertNotIn(key, monster)
        self.assertEqual(monster["last_move_id"], 3)

    def test_intent_is_kept_without_runic_dome(self):
        monster = to_visible(combat_state()).combat["monsters"][0]
        self.assertEqual(monster["move_adjusted_damage"], 11)

    def test_decision_combat_turn(self):
        self.assertEqual(to_visible(combat_state()).decision, Decision.COMBAT_TURN)

    def test_decision_in_combat_selection_screen_is_other(self):
        raw = combat_state()
        raw["game_state"]["screen_type"] = "HAND_SELECT"
        self.assertEqual(to_visible(raw).decision, Decision.OTHER)

    def test_decision_card_reward(self):
        raw = {
            "in_game": True,
            "game_state": {"seed": 1, "screen_type": "CARD_REWARD", "room_phase": "COMPLETE", "relics": []},
        }
        self.assertEqual(to_visible(raw).decision, Decision.CARD_REWARD)

    def test_decision_campfire(self):
        raw = {
            "in_game": True,
            "game_state": {"seed": 1, "screen_type": "REST", "room_phase": "INCOMPLETE", "relics": []},
        }
        self.assertEqual(to_visible(raw).decision, Decision.CAMPFIRE)

    def test_not_in_game(self):
        self.assertEqual(to_visible({"in_game": False}).decision, Decision.OTHER)


if __name__ == "__main__":
    unittest.main()
