# What is Project: DIALOGUE?

Anyone who's played or made a minecraft adventure map, story or even server over the past years in Minecraft will have run into this: talking to users can be quite a hassle. From maps containing images of text in their meta data to massive blocks of repeaters and command blocks, we've seen it all, and luckily for us, Mojang has been dramatically improve the process with every update. However, without the use of mods a.k.a. in vanilla Minecraft it is still a real challenge to make NPC's with a bit of depth, let alone make actual choices.

Dialogue in most adventures is limited to _monologue_, but project: DIALOGUE exists to realise a dream of actual dialogue trees in vanilla Minecraft. You know, like in timeless RPG's like Mass Effect or Skyrim. When I say trees, I mean the branching paths, where an NPC will say a few things, you get a bunch of options, you pick one and the NPC's reply will depend on your choice. Your choice may lead to more choices, and those choices to even more! Some choices may lead to the same outcome, some to drastically new ones.

The project started as a filter for [MCEdit](https://www.mcedit-unified.net/), but as MC 1.13 came around datapacks proved to be just as effective without requiring command blocks in loaded chunks (the MCEdit version can still be found as a legacy release on the [downloads page](https://github.com/Superkebabbie/projectDIALOGUE/releases))

[wiki](https://github.com/Superkebabbie/projectDIALOGUE/wiki)

## Goals for future versions
* Defining some sort of loop environment that allows you to come back to a certain point. (Note that this is possible with some command workaround: `<command scoreboard players set dNewSeg PD N`).
* Rather than one global dialogue, allow multiple players to have different dialogues with different NPC's at the same time.
* Built-in `/playsound` support to make it easier for creators to hook up voice acting to corresponding lines.