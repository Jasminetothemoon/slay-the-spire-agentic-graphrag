package com.stsagent.bridge;

import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.map.MapEdge;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.monsters.AbstractMonster;
import com.megacrit.cardcrawl.monsters.MonsterGroup;
import com.megacrit.cardcrawl.potions.AbstractPotion;
import com.megacrit.cardcrawl.relics.AbstractRelic;
import com.megacrit.cardcrawl.rewards.RewardItem;
import com.megacrit.cardcrawl.rooms.AbstractRoom;
import com.megacrit.cardcrawl.screens.CardRewardScreen;
import com.megacrit.cardcrawl.shop.ShopScreen;
import com.megacrit.cardcrawl.ui.panels.EnergyPanel;

import java.util.ArrayList;
import java.util.List;

public class GameStateCollector {
    private final BridgeConfig config;

    public GameStateCollector(BridgeConfig config) {
        this.config = config;
    }

    public String collectHeartbeatState() {
        return "{"
            + "\"run_id\":\"" + JsonUtil.escape(config.runId) + "\","
            + "\"source\":\"java_mod_bridge\","
            + "\"character_class\":\"unknown\","
            + "\"act\":1,"
            + "\"current_floor\":0,"
            + "\"current_hp\":0,"
            + "\"max_hp\":0,"
            + "\"gold\":0,"
            + "\"energy\":3,"
            + "\"deck\":[],"
            + "\"relics\":[],"
            + "\"potions\":[]"
            + "}";
    }

    public BridgePayload collect() {
        String stateJson = collectStateJson();
        Decision decision = collectDecision();
        return new BridgePayload(stateJson, decision.queryType, decision.options, decision.userQuery);
    }

    private String collectStateJson() {
        StringBuilder json = new StringBuilder("{");
        json.append("\"run_id\":\"").append(JsonUtil.escape(config.runId)).append("\",");
        json.append("\"source\":\"java_mod_bridge\",");
        json.append("\"character_class\":\"").append(JsonUtil.escape(characterClass())).append("\",");
        json.append("\"ascension_level\":").append(AbstractDungeon.ascensionLevel).append(",");
        json.append("\"act\":").append(AbstractDungeon.actNum).append(",");
        json.append("\"current_floor\":").append(AbstractDungeon.floorNum).append(",");
        json.append("\"current_hp\":").append(AbstractDungeon.player.currentHealth).append(",");
        json.append("\"max_hp\":").append(AbstractDungeon.player.maxHealth).append(",");
        json.append("\"gold\":").append(AbstractDungeon.player.gold).append(",");
        json.append("\"energy\":").append(currentEnergy()).append(",");
        json.append("\"deck\":").append(cards(AbstractDungeon.player.masterDeck == null ? null : AbstractDungeon.player.masterDeck.group)).append(",");
        json.append("\"upgraded_cards\":").append(upgradedCards(AbstractDungeon.player.masterDeck == null ? null : AbstractDungeon.player.masterDeck.group)).append(",");
        json.append("\"relics\":").append(relics()).append(",");
        json.append("\"potions\":").append(potions()).append(",");
        json.append("\"hand_cards\":").append(cards(AbstractDungeon.player.hand == null ? null : AbstractDungeon.player.hand.group)).append(",");
        json.append("\"draw_pile\":").append(cards(AbstractDungeon.player.drawPile == null ? null : AbstractDungeon.player.drawPile.group)).append(",");
        json.append("\"discard_pile\":").append(cards(AbstractDungeon.player.discardPile == null ? null : AbstractDungeon.player.discardPile.group)).append(",");
        json.append("\"enemies\":").append(enemies()).append(",");
        json.append("\"map_options\":").append(mapOptions()).append(",");
        json.append("\"combat_state\":").append(combatState());
        json.append("}");
        return json.toString();
    }

    private Decision collectDecision() {
        if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.CARD_REWARD) {
            CardRewardScreen screen = AbstractDungeon.cardRewardScreen;
            if (screen != null && screen.rewardGroup != null && !screen.rewardGroup.isEmpty()) {
                return new Decision("card_pick", cardNames(screen.rewardGroup), "Card reward from live Java bridge.");
            }
        }

        if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.SHOP) {
            ShopScreen shop = AbstractDungeon.shopScreen;
            List<String> options = new ArrayList<String>();
            if (shop != null) {
                options.addAll(cardNames(shop.coloredCards));
                options.addAll(cardNames(shop.colorlessCards));
                if (shop.purgeAvailable && AbstractDungeon.player != null && AbstractDungeon.player.gold >= ShopScreen.actualPurgeCost) {
                    options.add("Remove a Card");
                }
            }
            if (!options.isEmpty()) {
                return new Decision("shop", options, "Shop choice from live Java bridge.");
            }
        }

        if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.COMBAT_REWARD) {
            List<String> relicOptions = combatRewardRelics();
            if (!relicOptions.isEmpty()) {
                return new Decision("relic_pick", relicOptions, "Relic reward from live Java bridge.");
            }
        }

        if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.BOSS_REWARD) {
            List<String> bossRelicOptions = bossRelics();
            if (!bossRelicOptions.isEmpty()) {
                return new Decision("relic_pick", bossRelicOptions, "Boss relic reward from live Java bridge.");
            }
        }

        if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.MAP) {
            if (!nextMapNodes().isEmpty()) {
                return new Decision("pathing", new ArrayList<String>(), "Map route choice from live Java bridge.");
            }
        }

        AbstractRoom room = currentRoom();
        if (room != null && room.phase == AbstractRoom.RoomPhase.COMBAT && AbstractDungeon.player != null) {
            List<String> hand = cardNames(AbstractDungeon.player.hand == null ? null : AbstractDungeon.player.hand.group);
            if (!hand.isEmpty()) {
                return new Decision("combat", hand, "Current combat turn from live Java bridge.");
            }
        }

        return Decision.none();
    }

    private List<String> combatRewardRelics() {
        List<String> options = new ArrayList<String>();
        try {
            if (AbstractDungeon.combatRewardScreen == null || AbstractDungeon.combatRewardScreen.rewards == null) {
                return options;
            }
            for (RewardItem reward : AbstractDungeon.combatRewardScreen.rewards) {
                if (reward != null && reward.type == RewardItem.RewardType.RELIC && reward.relic != null) {
                    options.add(relicId(reward.relic));
                }
            }
        } catch (Exception ignored) {
        }
        return options;
    }

    private List<String> bossRelics() {
        List<String> options = new ArrayList<String>();
        try {
            if (AbstractDungeon.bossRelicScreen == null || AbstractDungeon.bossRelicScreen.relics == null) {
                return options;
            }
            for (AbstractRelic relic : AbstractDungeon.bossRelicScreen.relics) {
                if (relic != null) {
                    options.add(relicId(relic));
                }
            }
        } catch (Exception ignored) {
        }
        return options;
    }

    private String characterClass() {
        if (AbstractDungeon.player == null || AbstractDungeon.player.chosenClass == null) {
            return "unknown";
        }
        switch (AbstractDungeon.player.chosenClass) {
            case IRONCLAD:
                return "ironclad";
            case THE_SILENT:
                return "silent";
            case DEFECT:
                return "defect";
            case WATCHER:
                return "watcher";
            default:
                return AbstractDungeon.player.chosenClass.name().toLowerCase();
        }
    }

    private int currentEnergy() {
        try {
            return EnergyPanel.getCurrentEnergy();
        } catch (Exception ignored) {
            return 3;
        }
    }

    private String cards(List<AbstractCard> cards) {
        return JsonUtil.stringArray(cardNames(cards));
    }

    private List<String> cardNames(List<AbstractCard> cards) {
        List<String> names = new ArrayList<String>();
        if (cards == null) {
            return names;
        }
        for (AbstractCard card : cards) {
            if (card != null) {
                names.add(card.cardID != null ? card.cardID : card.name);
            }
        }
        return names;
    }

    private String upgradedCards(List<AbstractCard> cards) {
        List<String> names = new ArrayList<String>();
        if (cards != null) {
            for (AbstractCard card : cards) {
                if (card != null && card.upgraded) {
                    names.add(card.cardID != null ? card.cardID : card.name);
                }
            }
        }
        return JsonUtil.stringArray(names);
    }

    private String relics() {
        List<String> names = new ArrayList<String>();
        if (AbstractDungeon.player == null || AbstractDungeon.player.relics == null) {
            return "[]";
        }
        for (AbstractRelic relic : AbstractDungeon.player.relics) {
            if (relic != null) {
                names.add(relic.relicId != null ? relic.relicId : relic.name);
            }
        }
        return JsonUtil.stringArray(names);
    }

    private String relicId(AbstractRelic relic) {
        return relic.relicId != null ? relic.relicId : relic.name;
    }

    private String potions() {
        List<String> names = new ArrayList<String>();
        if (AbstractDungeon.player == null || AbstractDungeon.player.potions == null) {
            return "[]";
        }
        for (AbstractPotion potion : AbstractDungeon.player.potions) {
            if (potion != null && potion.ID != null && !"Potion Slot".equals(potion.name)) {
                names.add(potion.ID);
            }
        }
        return JsonUtil.stringArray(names);
    }

    private String enemies() {
        MonsterGroup monsters = currentMonsters();
        if (monsters == null || monsters.monsters == null) {
            return "[]";
        }
        StringBuilder json = new StringBuilder("[");
        boolean first = true;
        for (AbstractMonster monster : monsters.monsters) {
            if (monster == null || monster.isDeadOrEscaped()) {
                continue;
            }
            if (!first) {
                json.append(",");
            }
            first = false;
            json.append("{");
            json.append("\"name\":\"").append(JsonUtil.escape(monster.name)).append("\",");
            json.append("\"hp\":").append(monster.currentHealth).append(",");
            json.append("\"max_hp\":").append(monster.maxHealth).append(",");
            json.append("\"block\":").append(monster.currentBlock).append(",");
            json.append("\"intent\":\"").append(JsonUtil.escape(intent(monster))).append("\",");
            json.append("\"intent_damage\":").append(intentDamage(monster));
            json.append("}");
        }
        json.append("]");
        return json.toString();
    }

    private String intent(AbstractMonster monster) {
        if (monster.intent == null) {
            return "unknown";
        }
        return monster.intent.name().toLowerCase();
    }

    private int intentDamage(AbstractMonster monster) {
        if (monster.getIntentDmg() > 0) {
            return monster.getIntentDmg();
        }
        return 0;
    }

    private String combatState() {
        return "{\"incoming_damage\":" + incomingDamage() + "}";
    }

    private String mapOptions() {
        List<MapRoomNode> nodes = nextMapNodes();
        StringBuilder json = new StringBuilder("[");
        for (int i = 0; i < nodes.size(); i++) {
            if (i > 0) {
                json.append(",");
            }
            MapRoomNode node = nodes.get(i);
            String nodeType = mapNodeType(node);
            String id = "route_" + node.x + "_" + node.y + "_" + nodeType;
            json.append("{");
            json.append("\"id\":\"").append(JsonUtil.escape(id)).append("\",");
            json.append("\"name\":\"").append(JsonUtil.escape(displayNodeType(nodeType))).append("\",");
            json.append("\"nodes\":[\"").append(JsonUtil.escape(nodeType)).append("\"],");
            json.append("\"floor\":").append(node.y + 1).append(",");
            json.append("\"forced_elites\":").append("elite".equals(nodeType) ? 1 : 0).append(",");
            json.append("\"rest_count\":").append("rest".equals(nodeType) ? 1 : 0).append(",");
            json.append("\"shop_count\":").append("shop".equals(nodeType) ? 1 : 0).append(",");
            json.append("\"treasure_count\":").append("treasure".equals(nodeType) ? 1 : 0);
            json.append("}");
        }
        json.append("]");
        return json.toString();
    }

    private List<MapRoomNode> nextMapNodes() {
        List<MapRoomNode> nodes = new ArrayList<MapRoomNode>();
        try {
            if (AbstractDungeon.map == null || AbstractDungeon.map.isEmpty()) {
                return nodes;
            }
            MapRoomNode current = AbstractDungeon.currMapNode;
            if (current == null) {
                return firstMapRowNodes();
            }
            if (current.getEdges() == null) {
                return nodes;
            }
            for (MapEdge edge : current.getEdges()) {
                if (edge == null || edge.dstY < 0 || edge.dstY >= AbstractDungeon.map.size()) {
                    continue;
                }
                List<MapRoomNode> row = AbstractDungeon.map.get(edge.dstY);
                if (row == null || edge.dstX < 0 || edge.dstX >= row.size()) {
                    continue;
                }
                MapRoomNode node = row.get(edge.dstX);
                if (node != null && node.getRoom() != null) {
                    nodes.add(node);
                }
            }
        } catch (Exception ignored) {
        }
        return nodes;
    }

    private List<MapRoomNode> firstMapRowNodes() {
        List<MapRoomNode> nodes = new ArrayList<MapRoomNode>();
        try {
            if (AbstractDungeon.map == null || AbstractDungeon.map.isEmpty()) {
                return nodes;
            }
            List<MapRoomNode> row = AbstractDungeon.map.get(0);
            if (row == null) {
                return nodes;
            }
            for (MapRoomNode node : row) {
                if (node != null && node.getRoom() != null) {
                    nodes.add(node);
                }
            }
        } catch (Exception ignored) {
        }
        return nodes;
    }

    private String mapNodeType(MapRoomNode node) {
        if (node == null || node.getRoom() == null) {
            return "unknown";
        }
        String className = node.getRoom().getClass().getSimpleName().toLowerCase();
        if (className.contains("elite")) {
            return "elite";
        }
        if (className.contains("rest")) {
            return "rest";
        }
        if (className.contains("shop")) {
            return "shop";
        }
        if (className.contains("treasure")) {
            return "treasure";
        }
        if (className.contains("event")) {
            return "event";
        }
        if (className.contains("boss")) {
            return "boss";
        }
        if (className.contains("monster")) {
            return "monster";
        }
        return "unknown";
    }

    private String displayNodeType(String nodeType) {
        if ("elite".equals(nodeType)) {
            return "Elite";
        }
        if ("rest".equals(nodeType)) {
            return "Rest Site";
        }
        if ("shop".equals(nodeType)) {
            return "Shop";
        }
        if ("treasure".equals(nodeType)) {
            return "Treasure";
        }
        if ("event".equals(nodeType)) {
            return "Event";
        }
        if ("boss".equals(nodeType)) {
            return "Boss";
        }
        if ("monster".equals(nodeType)) {
            return "Monster";
        }
        return "Unknown";
    }

    private int incomingDamage() {
        MonsterGroup monsters = currentMonsters();
        if (monsters == null || monsters.monsters == null) {
            return 0;
        }
        int total = 0;
        for (AbstractMonster monster : monsters.monsters) {
            if (monster != null && !monster.isDeadOrEscaped()) {
                total += intentDamage(monster);
            }
        }
        return total;
    }

    private AbstractRoom currentRoom() {
        try {
            if (AbstractDungeon.currMapNode == null) {
                return null;
            }
            return AbstractDungeon.getCurrRoom();
        } catch (Exception ignored) {
            return null;
        }
    }

    private MonsterGroup currentMonsters() {
        AbstractRoom room = currentRoom();
        if (room == null) {
            return null;
        }
        try {
            return room.monsters;
        } catch (Exception ignored) {
            return null;
        }
    }

    private static class Decision {
        final String queryType;
        final List<String> options;
        final String userQuery;

        Decision(String queryType, List<String> options, String userQuery) {
            this.queryType = queryType;
            this.options = options;
            this.userQuery = userQuery;
        }

        static Decision none() {
            return new Decision("", new ArrayList<String>(), "");
        }
    }
}
