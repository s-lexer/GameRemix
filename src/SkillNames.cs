using System;
using System.Collections.Generic;

namespace DDFixTool
{
    // English names of Divine Divinity skills (the save stores them in the language of the game it was made in).
    // Translated from the Russian localisation; wording follows the English game as closely as known, unknown names fall back to the stored text.
    static class SkillNames
    {
        static Dictionary<string, string> map;
        const string Pairs =
            "Владение мечом|Sword Mastery;Мастерство атаки|Attack Mastery;Перемещение|Teleport;Демоновы шипы|Demon Thorns;Подлый удар|Backstab;Эльфийское зрение|Elven Sight;" +
            "Волшебное оружие|Magic Weapon;Небесный огонь|Heavenly Fire;Призывание грызунов|Summon Rodents;Взгляд провидца|Seer's Gaze;Опознание|Identify;Искусство торга|Bartering;" +
            "Владение булавой|Mace Mastery;Взлом замков|Lockpicking;Алхимия|Alchemy;Мнимая смерть|Feign Death;Точная стрельба|Accurate Shooting;Ремонт|Repair;Благословение|Blessing;" +
            "Наблюдательность|Observation;Призывание скелетов|Summon Skeletons;Бессилие|Weakness;Молния|Lightning;Смерть с небес|Death from Above;Восстановление|Restoration;Бумеранг|Boomerang;" +
            "Астральная форма|Astral Form;Мудрость|Wisdom;Изучение повадок|Animal Lore;Владение топором|Axe Mastery;Парные стрелы|Double Arrows;Заморозка|Freeze;Паралич|Paralyze;" +
            "Мастерство карманника|Pickpocket Mastery;Похищение жизни|Life Drain;Удушье|Strangulation;Обход ловушек|Avoid Traps;Призрачный воин|Phantom Warrior;Очарование|Charm;" +
            "Мастерство защиты|Defense Mastery;Владение молотом|Hammer Mastery;Пекло|Inferno;Истинное зрение|True Sight;Телекинез|Telekinesis;Мастер-демонолог|Demon Master;Истощение|Drain;" +
            "Стена молний|Wall of Lightning;Отравленные стрелы|Poison Arrows;Астральные стрелы|Astral Arrows;Благословение небес|Heaven's Blessing;Удар стихий|Elemental Strike;" +
            "Волшебный барьер|Magic Barrier;Яд|Poison;Аура защиты|Aura of Protection;Ослепление|Blindness;Смертельный подарочек|Deadly Present;Изгнание|Banish;Диски-убийцы|Killer Discs;" +
            "Владение копьем|Spear Mastery;Астральный урон|Astral Damage;Ядовитая кожа|Poison Skin;Воскрешение|Resurrection;Божественное око|Divine Eye;Превращение|Transformation;" +
            "Волшебная сила|Magic Power;Аура повелителя|Aura of Command;Эльфийская резвость|Elven Agility;Ядовитое облако|Poison Cloud;Владение луком|Bow Mastery;Урон огнем|Fire Damage;" +
            "Отбивание снарядов|Deflect Missiles;Стихийные стрелы|Elemental Arrows;Защита от чар|Spell Protection;Владение арбалетом|Crossbow Mastery;Наставник|Mentor;Слияние с тенью|Shadow Meld;" +
            "Смертельный удар|Deadly Strike;Гнев стихий|Elemental Wrath;Призыв отборных скелетов|Summon Elite Skeletons;Защита от стрел|Arrow Protection;Проклятье|Curse;" +
            "Темпоральный всплеск|Temporal Surge;Небесный дар|Heavenly Gift;Урон молнией|Lightning Damage;Взрывные стрелы|Explosive Arrows;Возврат удара|Return Strike;Удар стихии|Elemental Blast;" +
            "Цепь молний|Chain Lightning;Владение щитом|Shield Mastery;Выпад|Lunge;Отвод глаз|Distraction;Живучесть|Vitality;Призыв нечестивца|Summon Demonic Helper;Одержимость|Possession;" +
            "Адская гончая|Hellhound;Ядовитая смазка|Poison Coating";

        public static string Display(string stored, bool ru)
        {
            if (ru) return stored;
            if (map == null) { map = new Dictionary<string, string>(); foreach (string p in Pairs.Split(';')) { string[] kv = p.Split('|'); map[kv[0]] = kv[1]; } }
            string suffix = "", baseName = stored;
            if (stored.EndsWith(" (без активации)")) { suffix = " (no activation)"; baseName = stored.Substring(0, stored.Length - " (без активации)".Length); }
            else if (stored.EndsWith(" (пассивное)")) { suffix = " (passive)"; baseName = stored.Substring(0, stored.Length - " (пассивное)".Length); }
            string en; return (map.TryGetValue(baseName, out en) ? en : baseName) + suffix;
        }
    }
}
